# テーマ日時記録と更新順ソート Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** themes.csv に `created_at`/`commented_at`/`updated_at` を記録し、ホーム画面に意見順(デフォルト)・更新順ソートとカード左下の日時表示を追加する（仕様: `docs/superpowers/specs/2026-07-08-theme-timestamps-design.md`）

**Architecture:** サーバー側はbatch.pyの変化検知を「投票または意見の変化」に拡張して3列をスタンプ、CSV書き込みは既存の `utils.CSV.to_csv`（不足キー→空文字）が旧データの空白を自動処理。クライアント側はDOMソート方式を踏襲し `data-commented`/`data-updated` 属性で並べ替える。

**Tech Stack:** Python(FastAPI/pytest, Dockerで実行) / 素のJS / SCSS

**制約: 本番に影響する操作は行わない**（マージ・デプロイ・S3書き込みなし。検証はpytestとlocalhost:8081のみ）

**前提知識:**
- `THEME_HEADERS` は `Server/web/api/services/batch.py:23`。`utils.CSV.to_csv` は不足キーを `''` で出力（旧行の空白はこれで実現）
- `utils.Time.now()` は Asia/Tokyo（`Server/web/api/utils/time.py`）
- テスト実行: `cd Server && PROJECT_NAME=PolisJAPAN docker compose run --rm --no-deps --entrypoint python web -m pytest tests -q`
- クライアントのソートはDOM並べ替え（`home.js:391 sortArticles`）、カードは `buildTopicInnerHTML` のテンプレート literal、デフォルトは `home.js:163 currentSort = "new"`

---

### Task 1: サーバー — 3列の記録とテスト

**Files:**
- Modify: `Server/web/api/utils/time.py`
- Modify: `Server/web/api/services/batch.py`
- Test: `Server/web/tests/test_batch_service.py`

- [ ] **Step 1: `utils/time.py` に分単位フォーマットを追加**

`FILENAME_FORMAT` 定数の直後に定数を追加:

```python
    MINUTE_DATETIME_FORMAT = "%Y-%m-%d %H:%M"
    """分単位の日時形式（例: 2025-01-15 13:45）。themes.csvの日時列で使用。"""
```

`to_mysql_datetime_str` メソッドの直後にメソッドを追加:

```python
    @classmethod
    def to_minute_datetime_str(cls, datetime_instance: datetime) -> str:
        """
        datetime を分単位の日時文字列に変換する。

        フォーマット: `%Y-%m-%d %H:%M`（表示にそのまま使え、文字列比較でソート可能）

        Args:
            datetime_instance (datetime): 対象の日時。

        Returns:
            str: 分単位の日時文字列。
        """
        return datetime_instance.strftime(cls.MINUTE_DATETIME_FORMAT)
```

- [ ] **Step 2: `batch.py` の `THEME_HEADERS` に3列追加**

```python
THEME_HEADERS = ["id", "category", "title", "description", "conversation_id", "report_id", "votes", "comments", "create_date", "created_at", "commented_at", "updated_at"]
```

- [ ] **Step 3: `update_themes` の変化検知と時刻記録**

`update_themes` 内のループ本体（`total_votes` 集計〜`update_comment_csv[...] = report_csv_str` まで）を以下に置き換える:

```python
            # コメント数、投票数を集計
            total_comments = len(comments)
            total_votes = sum(int(comment["total-votes"]) for comment in comments)

            prev_votes = int(theme["votes"])
            prev_comments = int(theme["comments"])
            votes_changed = prev_votes != total_votes
            comments_changed = prev_comments != total_comments

            Logger.debug(f"{theme['title']} votes {prev_votes} -> {total_votes} / comments {prev_comments} -> {total_comments} (Refresh -> {votes_changed or comments_changed})")

            # 現在S3に保存済みの集計CSVと比較（投票または意見の変化で更新）
            if votes_changed or comments_changed:
                now_str = utils.Time.to_minute_datetime_str(utils.Time.now())

                # 変更があった場合は、取得したファイルを設置用に配列に格納
                update_row = theme.copy()
                update_row["votes"] = str(total_votes)
                update_row["comments"] = str(total_comments)
                # 投票または意見が増えた日時
                update_row["updated_at"] = now_str
                # 新しい意見（コメント）が投稿された日時（増加時のみ）
                if total_comments > prev_comments:
                    update_row["commented_at"] = now_str
                update_themes.append(update_row)

                # S3にアップするリストにCSVを追加
                update_comment_csv[theme["conversation_id"]] = report_csv_str
```

（旧形式CSVの行は `created_at`/`commented_at` キーを持たないが、`to_csv` が空文字で出力するため追加処理は不要）

- [ ] **Step 4: テーマ作成時の3列初期化**

`theme_info["create_date"] = utils.Time.to_mysql_datetime_str(utils.Time.now())` の直後に追加:

```python
        # 作成・更新日時（themes.csvの新列。分単位・JST）。新規テーマはどのソートでも先頭に来るよう3列とも作成時刻で初期化する
        now_minute_str = utils.Time.to_minute_datetime_str(utils.Time.now())
        theme_info["created_at"] = now_minute_str
        theme_info["commented_at"] = now_minute_str
        theme_info["updated_at"] = now_minute_str
```

- [ ] **Step 5: テストを追加**

`Server/web/tests/test_batch_service.py` に以下を追加する。時刻固定は `patch.object(utils.Time, "now", classmethod(lambda cls: fixed_now))` 方式:

```python
FIXED_NOW = utils.Time.from_mysql_datetime_str("2026-07-08 12:34:56", utils.Time.TZ_TOKYO)
FIXED_MINUTE = "2026-07-08 12:34"


def _written_themes_rows(service):
    """write_themes_csv がアップロードした themes.csv をパースして id→行 の辞書で返す。"""
    call = service.s3.upload_bytes.call_args_list[-1]
    assert call.args[0] == "csv/themes.csv"
    return {r["id"]: r for r in utils.CSV.parse_csv(call.args[1].decode("utf-8"))}


async def test_update_themes_stamps_updated_at_on_vote_only_change():
    service = _service()
    with patch.object(utils.Time, "now", classmethod(lambda cls: FIXED_NOW)), \
         patch.object(BatchService, "get_theme_csv", AsyncMock(return_value=("raw", [t.copy() for t in THEMES]))), \
         patch.object(BatchService, "get_report_csv", AsyncMock(side_effect=[
             ("csv1", _report([6, 6])),  # c1: 12票/2コメント → 票のみ変化
             ("csv2", _report([5])),     # c2: 5票/1コメント → 変化なし
         ])):
        count = await service.update_themes()

    assert count == 1
    rows = _written_themes_rows(service)
    assert rows["1"]["updated_at"] == FIXED_MINUTE
    assert rows["1"]["commented_at"] == ""  # コメント数は増えていない
    assert rows["1"]["created_at"] == ""    # 旧データは空白のまま
    assert rows["2"]["updated_at"] == ""    # 変化なしの行は空白のまま


async def test_update_themes_stamps_both_on_comment_increase():
    service = _service()
    with patch.object(utils.Time, "now", classmethod(lambda cls: FIXED_NOW)), \
         patch.object(BatchService, "get_theme_csv", AsyncMock(return_value=("raw", [t.copy() for t in THEMES]))), \
         patch.object(BatchService, "get_report_csv", AsyncMock(side_effect=[
             ("csv1", _report([5, 5])),      # c1: 10票/2コメント → 変化なし
             ("csv2", _report([3, 2])),      # c2: 5票/2コメント → コメント増（票は同数）
         ])):
        count = await service.update_themes()

    assert count == 1
    rows = _written_themes_rows(service)
    assert rows["2"]["commented_at"] == FIXED_MINUTE
    assert rows["2"]["updated_at"] == FIXED_MINUTE


async def test_update_themes_comment_only_change_is_detected():
    """現行の「投票数のみ」検知では拾えなかった、コメント数だけの変化も更新対象になる。"""
    service = _service()
    with patch.object(BatchService, "get_theme_csv", AsyncMock(return_value=("raw", [t.copy() for t in THEMES]))), \
         patch.object(BatchService, "get_report_csv", AsyncMock(side_effect=[
             ("csv1", _report([10, 0, 0])),  # c1: 10票/3コメント → コメントのみ増
             ("csv2", _report([5])),         # c2: 変化なし
         ])):
        count = await service.update_themes()

    assert count == 1
```

さらに、既存の `test_publish_approved_drafts_limit_1` に「新規テーマ行の3列が作成時刻で初期化される」ことのアサーションを追加する（既存テストの構造を読み、時刻を `FIXED_NOW` で固定した上で、書き込まれたthemes.csvの新規行について `created_at == commented_at == updated_at == FIXED_MINUTE` を検証する。既存アサーションは維持）。

- [ ] **Step 6: テスト実行**

Run:
```bash
cd /Users/koyakawahara/Documents/Repository/PolisJAPAN/Server && PROJECT_NAME=PolisJAPAN docker compose run --rm --no-deps --entrypoint python web -m pytest tests -q
```
Expected: 全件PASS（既存38件+新規3件以上）

- [ ] **Step 7: Commit**

```bash
git add Server/web/api/utils/time.py Server/web/api/services/batch.py Server/web/tests/test_batch_service.py
git commit -m "feat: テーマの作成・更新日時をthemes.csvに記録（投票/意見の変化検知を拡張）

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: クライアント — ソート追加・デフォルト変更・カード日時表示

**Files:**
- Modify: `Client/public_html_app/index.html`（ソート選択肢）
- Modify: `Client/public_html_app/javascript/home.js`
- Modify: `Client/scss/pages/home/_app.scss`

- [ ] **Step 1: ソート選択肢を追加（index.html）**

`.select-floating` 内を以下にする（意見順・更新順を先頭に追加）:

```html
                        <div class="select-floating">
                            <div class="select-element" data-value="commented">意見順</div>
                            <div class="select-element" data-value="updated">更新順</div>
                            <div class="select-element" data-value="new">新着準</div>
                            <div class="select-element" data-value="old">古い順</div>
                            <div class="select-element" data-value="popular">人気順</div>
                        </div>
```
（既存の「新着準」の表記はそのまま維持する）

- [ ] **Step 2: デフォルトソートの変更（home.js）**

```js
let currentSort = "new";
```
を
```js
let currentSort = "commented";
```
に変更（コメント行があれば合わせて更新）。

- [ ] **Step 3: カードに日時属性と左下表示を追加（home.js `buildTopicInnerHTML`）**

`const votes = item.votes;` の直後に追加:

```js
        // 日時列（旧データは未定義→空文字。空白は表示しない）
        const createdAt = item.created_at ?? '';
        const commentedAt = item.commented_at ?? '';
        const updatedAt = item.updated_at ?? '';
```

テンプレートの `<button class="article-item" ...>` 開始タグを以下に変更（data属性2つ追加。値に空白を含むためクォート必須）:

```js
        <button class="article-item" href="/detail/?conversation_id=${conversationId}" data-category=${esc(categoryId)} data-id=${uniqueId} data-population=${votes} data-commented="${esc(commentedAt)}" data-updated="${esc(updatedAt)}">
```

`<div class="article-footer">` の直後（`.article-opinion-group` の前）に追加:

```js
                    ${createdAt || updatedAt ? `
                    <div class="article-dates">
                        ${createdAt ? `<div class="date-row">作成 ${esc(createdAt)}</div>` : ''}
                        ${updatedAt ? `<div class="date-row">更新 ${esc(updatedAt)}</div>` : ''}
                    </div>` : ''}
```

- [ ] **Step 4: ソート処理を追加（home.js `sortArticles`）**

`} else if (type === "popular") {` ブロックの後に追加:

```js
    } else if (type === "commented" || type === "updated") {
        // 意見順/更新順 → 日時文字列(YYYY-MM-DD HH:MM)の降順。空白は末尾、同値はid降順
        sorted = articles.sort((a, b) => {
            const va = a.dataset[type] || "";
            const vb = b.dataset[type] || "";
            if (va !== vb) {
                if (!va) return 1;
                if (!vb) return -1;
                return vb.localeCompare(va);
            }
            return b.dataset.id - a.dataset.id;
        });
    }
```

- [ ] **Step 5: 日時表示のスタイル（_app.scss）**

`.article-footer {` ブロック内、`.article-opinion-group` ルールの直前に追加（フッターは右寄せflexのため、`margin-right: auto` で日時だけ左端へ寄せる）:

```scss
                    .article-dates {
                        margin-right: auto;

                        display: flex;
                        flex-direction: column;
                        align-items: flex-start;
                        gap: 2px;

                        .date-row {
                            font-size: var(--font-size-11px);
                            color: var(--color-font-light);
                            opacity: 0.85;
                            white-space: nowrap;
                        }
                    }
```

- [ ] **Step 6: 検証**

```bash
cd /Users/koyakawahara/Documents/Repository/PolisJAPAN
node --check Client/public_html_app/javascript/home.js && echo JS-OK
cd Client && docker compose run --rm sass sh -lc 'npx --yes sass@1.79.5 --no-source-map /src/style.scss /tmp/check.css && grep -c article-dates /tmp/check.css'
curl -s http://localhost:8081/ | grep -c 'data-value="commented"'
```
Expected: `JS-OK` / 1以上 / `1`

- [ ] **Step 7: Commit**

```bash
git add Client/public_html_app/index.html Client/public_html_app/javascript/home.js Client/scss/pages/home/_app.scss
git commit -m "feat: テーマ一覧に意見順(デフォルト)・更新順ソートとカード日時表示を追加

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: ブラウザ総合検証（コントローラー自身が実施）

**Files:** なし（検証 + style.css再生成コミット）

- [ ] **Step 1: 本番CSV（旧形式）での確認** — localhost:8081 をそのまま開き、日時が一切表示されず、デフォルト（意見順）でも表示が破綻しない（全行空白→id降順=新着順相当）こと

- [ ] **Step 2: 新形式CSVでの確認** — puppeteerの `page.setRequestInterception` で `/csv/themes.csv` への応答をテストフィクスチャ（新3列入り・空白混在・日時バラバラ）に差し替え、以下を確認:
  1. デフォルトが意見順（commented_at降順、空白は末尾）
  2. 更新順・新着順・古い順・人気順の切り替え
  3. カード左下に「作成/更新」表示、空白項目の非表示、両方空白の行なし
  4. モバイル390px・デスクトップ幅でのレイアウト（右下の意見/投票と重ならない）
  5. スクリーンショット目視

- [ ] **Step 3: style.css再生成をコミットし、完了報告**（マージ・本番反映はユーザー承認後）

---

## 備考

- 旧クライアント+新CSV / 新クライアント+旧CSV のどちらも安全（余分な列は無視・欠落列は空白扱い）のため、デプロイ順序の制約なし
- batch-updateがthemes.csvを書き込むのは変化検知時のみ。マージ後、最初に変化があったタイミングで新ヘッダーに移行する
