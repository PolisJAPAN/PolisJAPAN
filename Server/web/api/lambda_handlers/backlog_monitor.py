"""
投稿バッチ(batch-create)の滞留監視。

毎回の起動の最後に下書きの滞留状況をCloudWatchメトリクスとして出力し、
1日1回、投稿失敗(FAILED)の下書きが残っていればSNSでリマインドを送る。

背景: 2026-10の障害では、失敗した下書きがFAILEDに隔離された後は
「処理0件で正常終了」になるためLambdaのErrorsアラームがすぐOKに戻り、
約4週間・45件の滞留に気づけなかった。状態が解消するまでALARMのままになる
「件数ベース」の監視に切り替える。

メトリクスはEmbedded Metric Format(EMF)で標準出力に書くだけで、CloudWatch Logsが
自動抽出する（PutMetricData APIもIAM権限も不要）。アラーム定義は
Infra/terraform/modules/monitoring にある。
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any, Optional

import boto3

import api.models.types as types
from api.logger import Logger
from api.utils.time import Time

METRIC_NAMESPACE = "PolisJAPAN/Batch"
METRIC_FUNCTION_NAME = "polisjapan-batch-create"

REMINDER_HOUR_JST = 9
"""リマインド送信時刻(JST)。スケジュールは15分間隔のため、この時の最初の15分間に入る1回だけが送信する"""
REMINDER_WINDOW_MINUTES = 15
REMINDER_MAX_TITLES = 20


async def collect_backlog(draft_store: Any) -> dict[str, Any]:
    """投稿待ち(APPROVED)と投稿失敗(FAILED)の下書きを数える。"""
    failed = await draft_store.select_by_post_status(types.PostStatus.FAILED.value)
    pending = await draft_store.select_by_post_status(types.PostStatus.APPROVED.value)
    return {
        "failed": len(failed),
        "pending": len(pending),
        "failed_titles": [str(d.theme_name).strip() for d in failed],
    }


def emit_metrics(failed: int, pending: int, published: int) -> None:
    """滞留状況をEMF形式で標準出力へ書き出す（Loggerは色コードを付けるため使わない）。"""
    print(json.dumps({
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [{
                "Namespace": METRIC_NAMESPACE,
                "Dimensions": [["FunctionName"]],
                "Metrics": [
                    {"Name": "FailedDrafts", "Unit": "Count"},
                    {"Name": "PendingDrafts", "Unit": "Count"},
                    {"Name": "PublishedDrafts", "Unit": "Count"},
                ],
            }],
        },
        "FunctionName": METRIC_FUNCTION_NAME,
        "FailedDrafts": failed,
        "PendingDrafts": pending,
        "PublishedDrafts": published,
    }, ensure_ascii=False), flush=True)


def is_reminder_window(now: datetime) -> bool:
    """1日1回のリマインド送信枠（JST 9:00〜9:14）に入っているか。"""
    return now.hour == REMINDER_HOUR_JST and now.minute < REMINDER_WINDOW_MINUTES


def build_reminder(failed_titles: list[str]) -> tuple[str, str]:
    """リマインドメールの件名と本文を作る。"""
    count = len(failed_titles)
    subject = f"[PolisJAPAN] 投稿失敗の下書きが{count}件残っています"
    lines = [
        f"Polisへの投稿に失敗して隔離された下書きが {count} 件あります。",
        "このままでは投稿されません。解消するまで毎朝この通知を送ります。",
        "",
        "■ 対象",
    ]
    lines += [f"・{title}" for title in failed_titles[:REMINDER_MAX_TITLES]]
    if count > REMINDER_MAX_TITLES:
        lines.append(f"…ほか {count - REMINDER_MAX_TITLES} 件")
    lines += [
        "",
        "■ 対応",
        "1. CloudWatch Logs の /aws/lambda/polisjapan-batch-create で失敗原因を確認する",
        "2. 原因を解消したら、管理画面(admin.pol-is.jp)で FAILED の下書きを再承認する",
        "   （不要な下書きは却下する）",
    ]
    return subject, "\n".join(lines)


def send_reminder(failed_titles: list[str], topic_arn: str) -> None:
    subject, message = build_reminder(failed_titles)
    boto3.client("sns").publish(TopicArn=topic_arn, Subject=subject, Message=message)


async def report(draft_store: Any, published: int, started_at: Optional[datetime] = None) -> None:
    """
    滞留状況のメトリクス出力と、必要ならリマインド送信を行う。

    監視の失敗で投稿バッチ本体を失敗させないため、例外はログに残して握りつぶす
    （メトリクスが途絶えた場合は「報告なし」アラームで検知される）。

    Args:
        draft_store: 下書きストア
        published: 今回の起動で投稿できた件数（失敗時は0）
        started_at: 起動時刻(JST)。リマインド送信枠の判定に使う（処理時間で枠を跨がないよう起動時点で判定）
    """
    try:
        backlog = await collect_backlog(draft_store)
        emit_metrics(backlog["failed"], backlog["pending"], published)

        topic_arn = os.environ.get("ALERTS_TOPIC_ARN", "")
        if backlog["failed"] > 0 and topic_arn and is_reminder_window(started_at or Time.now()):
            send_reminder(backlog["failed_titles"], topic_arn)
    except Exception as e:
        Logger.error(f"滞留監視の報告に失敗しました: {type(e).__name__}: {e}")
