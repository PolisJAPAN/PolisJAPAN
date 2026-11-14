"""AI 出力の評価を実行する

テーマ作成の AI 生成（立場 → 意見 → 説明）を評価用のテーマで実際に動かし、
基準ごとの合格率を合格ラインと比べる。OpenAI・LangSmith・DuckDuckGo を実際に呼ぶ。

使い方（Server/web で。ローカルのコンテナの中でも同じ）:
    python -m evals.run                       # 全ケースを 1 回ずつ
    python -m evals.run --repeat 3            # 各ケースを 3 回
    python -m evals.run --limit 3 --no-judge  # 先頭 3 ケース、モデルによる判定なし
    python -m evals.run --light-model <名前>   # 軽量モデルを差し替えて試す

終了コードは、すべての基準が合格ライン以上なら 0、そうでなければ 1。
"""
import argparse
import asyncio
import json
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import api.configs as configs
from api.logger import Logger
from api.services.theme import ThemeService
from evals import graders
from evals.judge import judge

EVALS_DIR = Path(__file__).parent


async def _timed(coroutine) -> tuple[object, float]:
    started = time.monotonic()
    value = await coroutine
    return value, time.monotonic() - started


async def run_case(case: dict, trial: int, use_judge: bool) -> dict:
    """1 ケースを生成して判定する。途中で失敗したら、以降の基準は不合格にする"""
    theme = case["theme"]
    service = ThemeService()
    record: dict = {"id": case["id"], "trial": trial, "theme": theme, "grades": {}, "errors": []}
    axis_list: list[str] = []
    comments: list[str] = []
    description = ""

    try:
        result, seconds = await _timed(service.generate_axis(theme))
        axis_list = result["axis_list"]
        record["axis"], record["axis_seconds"] = axis_list, round(seconds, 1)
    except Exception as error:  # 生成の失敗も評価の結果として記録する
        seconds = None
        record["errors"].append(f"axis: {error!r}")
    record["grades"] |= graders.grade_axis(axis_list) | graders.grade_latency("axis", seconds)

    try:
        if not axis_list:
            raise RuntimeError("立場が無いため生成しない")
        comments, seconds = await _timed(service.generate_comments_for_axes(theme, axis_list))
        record["comments"], record["comments_seconds"] = comments, round(seconds, 1)
    except Exception as error:
        seconds = None
        record["errors"].append(f"comments: {error!r}")
    record["grades"] |= graders.grade_comments(comments, len(axis_list)) | graders.grade_latency("comments", seconds)

    try:
        if not comments:
            raise RuntimeError("意見が無いため生成しない")
        result, seconds = await _timed(service.generate_description(theme, axis_list, comments))
        description = result if isinstance(result, str) else result["description"]
        record["description"], record["description_seconds"] = description, round(seconds, 1)
    except Exception as error:
        seconds = None
        record["errors"].append(f"description: {error!r}")
    record["grades"] |= graders.grade_description(description) | graders.grade_latency("description", seconds)

    if use_judge:
        try:
            if not (axis_list and comments and description):
                raise RuntimeError("生成結果がそろっていないため判定しない")
            grades, reason = await judge(theme, axis_list, comments, description)
            record["judge_reason"] = reason
        except Exception as error:
            grades = {key: False for key in graders.THRESHOLDS if key.startswith("judge_")}
            record["errors"].append(f"judge: {error!r}")
        record["grades"] |= grades

    failed = [key for key, passed in record["grades"].items() if not passed]
    print(f"  {case['id']}#{trial}: {'OK' if not failed else 'NG ' + ', '.join(failed)}", flush=True)
    return record


async def main() -> int:
    parser = argparse.ArgumentParser(description="AI 出力の評価")
    parser.add_argument("--repeat", type=int, default=1, help="各ケースを実行する回数")
    parser.add_argument("--limit", type=int, default=None, help="先頭から何ケース実行するか")
    parser.add_argument("--concurrency", type=int, default=3, help="同時に実行するケースの数")
    parser.add_argument("--light-model", default=None, help="OPENAI_MODEL_LIGHT を差し替える")
    parser.add_argument("--no-judge", action="store_true", help="モデルによる判定をしない")
    args = parser.parse_args()

    if args.light_model:
        configs.constants.OPENAI_MODEL_LIGHT = args.light_model
    warnings.filterwarnings("ignore", message="Pydantic serializer warnings")  # 構造化出力の既知の警告
    Logger.debug = staticmethod(lambda *a, **k: None)  # 生成結果の全文がログに出るのを止める

    cases = json.loads((EVALS_DIR / "cases.json").read_text(encoding="utf-8"))[: args.limit]
    print(f"軽量モデル: {configs.constants.OPENAI_MODEL_LIGHT} / 判定モデル: "
          f"{'なし' if args.no_judge else configs.constants.OPENAI_MODEL_STANDARD} / "
          f"{len(cases)} ケース × {args.repeat} 回", flush=True)

    semaphore = asyncio.Semaphore(args.concurrency)

    async def guarded(case: dict, trial: int) -> dict:
        async with semaphore:
            return await run_case(case, trial, not args.no_judge)

    records = await asyncio.gather(*[
        guarded(case, trial) for case in cases for trial in range(1, args.repeat + 1)
    ])

    summary = graders.summarize([record["grades"] for record in records])
    print("\n基準                          合格    合格率  合格ライン  判定")
    for row in summary:
        print(f"{row['id']:<28} {row['passed']:>3}/{row['total']:<3} {row['rate']:>7.0%} {row['threshold']:>9.0%}   "
              f"{'OK' if row['ok'] else 'NG'}")
    passed = all(row["ok"] for row in summary)
    print(f"\n結果: {'合格' if passed else '不合格'}")

    results_dir = EVALS_DIR / "results"
    results_dir.mkdir(exist_ok=True)
    path = results_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{configs.constants.OPENAI_MODEL_LIGHT}.json"
    path.write_text(json.dumps({
        "light_model": configs.constants.OPENAI_MODEL_LIGHT,
        "judge_model": None if args.no_judge else configs.constants.OPENAI_MODEL_STANDARD,
        "passed": passed,
        "summary": summary,
        "records": records,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"詳細: {path}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
