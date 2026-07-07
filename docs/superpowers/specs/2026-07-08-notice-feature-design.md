# お知らせ機能 設計書

| 項目 | 内容 |
| --- | --- |
| 作成日 | 2026-07-08 |
| 対象 | WEBアプリ ホーム画面（`Client/public_html_app/`） |
| 目的 | 運営からのお知らせをCSV駆動で表示する。ハンバーガーメニュー初の「住人」 |

## 決定事項

1. **入口はハンバーガーメニュー**: 「✉お問い合わせ」の上に「🔔お知らせ」を追加。タップでメニューを閉じてモーダルを開く
2. **データはS3の `csv/notices.csv`**（手動アップロード運用）: `themes.csv` と同じ配信経路（CloudFront + 5分キャッシュバスター `loadCsvAsJson`）
3. **新着の自動表示**: Cookie `notice_last_seen_id` に既読の最大IDを保存。最大ID > Cookie値なら読み込み時に自動でモーダルを開く
4. **本文はMarkdownサブセット + URL自動リンク**（自前実装・ライブラリなし）
5. **UIはテーマ作成と同じスライドモーダル**（`.slide-modal.full-screen-modal` + `ModalManager` 流用）。アコーディオンのリスト表示、**最新1件のみ初期展開**

## データ仕様 — `csv/notices.csv`

UTF-8、ヘッダーあり。既存 `parseCSV` は引用符内の改行・カンマ・`""` エスケープに対応済み。

| カラム | 型 | 内容 |
| --- | --- | --- |
| `id` | 整数 | 大きいほど新しい。既読判定・ソートに使用（**表示はid降順**。CSVの行順に依存しない） |
| `date` | 文字列 | 表示用日付（例 `2026-07-10`。そのまま表示、パースしない） |
| `title` | 文字列 | アコーディオンのヘッダー |
| `body` | 文字列 | Markdownサブセット。引用符で囲めば複数行可 |

```csv
id,date,title,body
2,2026-07-10,新機能のお知らせ,"メニューから**お知らせ**が見られるようになりました。
- 詳細は[こちら](https://pol-is.jp/)"
1,2026-07-01,サイト公開,Polis JAPANを公開しました
```

- idが整数でない行・必須カラム欠落行はスキップ（console.warnのみ）

## Markdownサブセット仕様（安全設計）

**先に本文全体をHTMLエスケープしてから**、以下の記法だけをタグへ変換する（エスケープ済みテキストへの正規表現変換のため、任意HTML注入が構造的に不可能）:

| 記法 | 変換 |
| --- | --- |
| `## テキスト`（行頭） | `<strong class="notice-heading">`（見出し風・hタグは使わない） |
| `**テキスト**` | `<strong>` |
| `[テキスト](URL)` | `<a href="URL" target="_blank" rel="noopener noreferrer">`（URLは http/https のみ許可） |
| `- テキスト`（行頭） | `<ul><li>`（連続行をまとめる） |
| 裸のURL（http/https） | 自動で `<a>` 化（リンク記法変換後の残りに適用） |
| 改行 | `<br>`（リスト内は除く） |

## UI仕様

- `#notice-modal`: テーマ作成モーダルと同じ構造（`.slide-modal.full-screen-modal` > `.label-group`（タイトル「お知らせ」+ 閉じるボタン）+ `.modal-window` > `.modal-scroll-area`）
- リスト: `.notice-item`（アコーディオン）を **id降順** に描画
  - ヘッダー: 日付（小さくグレー）+ タイトル（太字）+ 開閉シェブロン（`bi-chevron-down`、開時は回転）
  - 本文: 開閉は `max-height` トランジション（またはgrid-rows。実装時に選択）
  - **最新（先頭）の1件だけ初期展開**、他は畳んだ状態
  - ヘッダーは `<button aria-expanded>`、本文領域と `aria-controls` で関連付け
- ハンバーガーメニュー項目: `🔔`（`bi-bell`）+「お知らせ」を `.menu-item` として「お問い合わせ」の上に追加

## 新着の自動表示

1. `DOMContentLoaded` 後に `loadCsvAsJson("/csv/themes.csv")` とは独立に `notices.csv` を取得（記事描画をブロックしない）
2. `maxId = 取得できた最大id`、`seen = Cookie notice_last_seen_id（未設定は0）`
3. `maxId > seen` かつ **チュートリアルが表示中でない**（`#tutorial.show` が無い）場合に自動でモーダルを開く
4. モーダルを開いたとき（自動・メニューからの手動とも）に Cookie を `maxId` に更新（有効期限365日、`setCookie` 流用）

## エラー処理

- 取得失敗・404（CSV未設置）: 自動表示しない。メニューから開いた場合は「お知らせを読み込めませんでした」を表示
- 0件（ヘッダーのみ）: 「お知らせはありません」を表示
- 本番へCSVを置くまで機能は静かに眠る（安全なロールアウト）

## 実装ファイル

| ファイル | 変更 |
| --- | --- |
| `Client/public_html_app/javascript/notice.js` | 新規: 取得・描画・アコーディオン・自動表示・Markdownサブセット |
| `Client/public_html_app/index.html` | `#notice-modal` 追加、ハンバーガーメニューに項目追加、`notice.js` 読み込み |
| `Client/scss/pages/home/_notice.scss` | 新規（+ `home/_index.scss` に forward 追加） |
| `Client/nginx_app/default.conf` | ローカル検証用: `location = /csv/notices.csv` はローカルファイル優先・無ければ本番へプロキシ（テストCSVを置いて検証できる） |

## 動作確認

1. ローカルの `public_html_app/csv/notices.csv` にテストデータを置き、localhost:8081 で確認（アコーディオン開閉／初期展開／Markdown変換／自動表示とCookie更新／チュートリアル併存時のスキップ／XSS: `<script>` を含む本文が無害化されること）
2. テストCSVを消して404経路（自動表示なし・手動でエラーメッセージ）を確認
3. ブラウザ実測でのセルフレビュー（スクリーンショット+座標、モバイル/デスクトップ幅）
4. 本番リリース: mainマージ（コード）→ `aws s3 cp notices.csv s3://app.pol-is.jp/csv/` で初回データ投入（この順なら安全）

## スコープ外

- 管理画面からのお知らせ編集（CSV手動運用で開始）
- 未読バッジ表示（自動表示で代替。必要になれば追加）
- テーマ詳細画面への展開
