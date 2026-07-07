# お知らせ機能 設計書

| 項目 | 内容 |
| --- | --- |
| 作成日 | 2026-07-08 |
| 改訂 | 2026-07-08 v2 — CSV+Markdown方式を廃止し、HTMLファイル読み込み方式へ変更（ユーザー判断: 表現力優先） |
| 対象 | WEBアプリ ホーム画面（`Client/public_html_app/`） |
| 目的 | 運営からのお知らせを表示する。ハンバーガーメニュー初の「住人」 |

## 決定事項

1. **入口はハンバーガーメニュー**: 「✉お問い合わせ」の上に「🔔お知らせ」を追加。タップでメニューを閉じてモーダルを開く
2. **お知らせ本文は個別HTMLファイル**（`Client/public_html_app/notice/*.html`、リポジトリ管理）。`notice.js` 内の**配列レジストリ**に `{id, date, title, path}` を羅列し、一覧はレジストリから、本文は該当HTMLをfetchして表示（v1のCSV+Markdown方式は表現力不足のため廃止）
3. **お知らせの追加手順** = HTMLファイルを作成 + レジストリに1エントリ追記 → mainマージで自動デプロイ（S3手動アップロード不要。deploy-client.ymlが全ファイル同期+CloudFront無効化）
4. **新着の自動表示**: Cookie `notice_last_seen_id` に既読の最大IDを保存。レジストリの最大ID > Cookie値なら読み込み時に自動でモーダルを開く
5. **UIはテーマ作成と同じスライドモーダル**（`.slide-modal.full-screen-modal` + `ModalManager` 流用）。アコーディオンのリスト表示、**最新1件のみ初期展開**
6. **本文用の既製スタイルを用意**: `_notice.scss` にお知らせHTML内でよく使う表示（見出し・リスト・画像・囲みボックス・ボタン風リンク等）を定義し、素のHTMLタグ+少数のクラスで整った見た目になるようにする

## データ仕様

### レジストリ（`notice.js` 冒頭の配列）

```js
/**
 * お知らせ一覧（新しいものを上に追加していく）。
 * id: 増分整数（既読判定に使用。過去より大きい値を振ること）
 * path: 本文HTML（フラグメント）のパス
 */
const NOTICES = [
    { id: 1, date: "2026-07-08", title: "お知らせ機能を追加しました", path: "./notice/001-release.html" },
];
```

- 表示は **id降順**（配列順に依存しない）
- ファイル名は `<id 3桁>-<slug>.html` 規約（例 `002-maintenance.html`）

### 本文HTML（`Client/public_html_app/notice/*.html`）

- **フラグメント**（`<!DOCTYPE>`や`<html>`なし）。`.notice-body-inner` に `innerHTML` で挿入される
- リポジトリ管理の第一者コンテンツなのでサニタイズはしない（CSV時代のXSS対策は不要になった）
- fetchには `?v=<id>` のキャッシュバスターを付与（idを変えれば内容更新も確実に反映）

### 本文で使える既製スタイル（`_notice.scss` が提供）

| 書き方 | 表示 |
| --- | --- |
| `<h3>見出し</h3>` | セクション見出し（太字・上マージン） |
| `<p>段落</p>` | 標準段落（行間1.7） |
| `<ul><li>` / `<ol><li>` | 箇条書き |
| `<a href>` | リンク色+下線（外部は `target="_blank"` を書く） |
| `<strong>` | 太字強調 |
| `<img>` | 幅100%・角丸16px |
| `<div class="notice-box">` | 補足・注意用の囲みボックス（グレー背景・角丸） |
| `<a class="notice-button" href>` | ボタン風リンク（既存 `.button.secondary` と同トーンのピル） |

## UI仕様

- `#notice-modal`: テーマ作成モーダルと同じ構造（`.label-group`（タイトル「お知らせ」+ 閉じるボタン）+ `.modal-window` > `.modal-scroll-area` > `.modal-content` > `.notice-list`）
- リスト: `.notice-item`（アコーディオン）を id降順に描画
  - ヘッダー: 日付（小さくグレー）+ タイトル（太字）+ シェブロン（`bi-chevron-down`、開時180度回転）
  - 本文開閉: `grid-template-rows 0fr/1fr` トランジション
  - **最新（先頭）の1件だけ初期展開**
  - ヘッダーは `<button aria-expanded aria-controls>`
- 本文HTMLは**モーダルを開いたときに全件並列fetch**（お知らせは少数想定。取得失敗した項目は本文に「読み込めませんでした」を表示）
- ハンバーガーメニュー項目: `bi-bell` +「お知らせ」（`button.menu-item`、お問い合わせの上）

## 新着の自動表示

1. レジストリはJS内なのでfetch不要。`DOMContentLoaded` 後、チュートリアル自動表示（800ms）とのマージンを取って2秒後に判定
2. `maxId = NOTICES の最大id`、`seen = Cookie notice_last_seen_id（未設定は0）`
3. `maxId > seen` かつ チュートリアル非表示（`#tutorial.show` が無い）なら自動でモーダルを開く
4. モーダルを開いたとき（自動・手動とも）に Cookie を `maxId` へ更新（365日）

## エラー処理

- レジストリが空: メニューから開くと「お知らせはありません」
- 本文HTMLのfetch失敗: 該当アコーディオンの本文に「読み込めませんでした」を表示（他の項目は正常表示）

## 実装ファイル

| ファイル | 変更 |
| --- | --- |
| `Client/public_html_app/javascript/notice.js` | レジストリ・描画・アコーディオン・本文fetch・自動表示（Markdown/CSV処理は削除） |
| `Client/public_html_app/notice/001-release.html` | 初回お知らせ（機能リリース告知。既製スタイルの実例を兼ねる） |
| `Client/public_html_app/index.html` | 実装済み（モーダル・メニュー項目・scriptタグ） |
| `Client/scss/pages/home/_notice.scss` | アコーディオン（実装済み）+ 本文用既製スタイルを追加 |

※ v1で計画していた nginx の notices.csv ローカル経路は不要（HTMLはリポジトリ内のためローカル配信がそのまま動く）

## 動作確認

1. localhost:8081 で: アコーディオン開閉／先頭初期展開／既製スタイルの見た目／自動表示とCookie更新／チュートリアル併存時のスキップ／fetch失敗経路（存在しないpathの一時エントリ）
2. ブラウザ実測でのセルフレビュー（スクリーンショット+座標、モバイル/デスクトップ幅）
3. 本番リリース: mainマージのみ（データもコードも一緒にデプロイされる）

## スコープ外

- 管理画面からのお知らせ編集
- 未読バッジ表示（自動表示で代替）
- テーマ詳細画面への展開
