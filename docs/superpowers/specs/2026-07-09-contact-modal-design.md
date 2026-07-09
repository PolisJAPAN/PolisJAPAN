# アプリ内お問い合わせモーダル 設計書

日付: 2026-07-09
状態: ユーザー承認済み（会話上で設計合意）

## 背景・目的

アプリ（app.pol-is.jp）のハンバーガーメニュー「お問い合わせ」は現在LPの
`https://pol-is.jp/contact/` へ遷移しており、別サイトへ飛ぶため戻る導線が壊れている。
アプリ内で完結する、下からスライドするカード形式のお問い合わせフォームに置き換える。

要件（ユーザー指定）:
- 下からスライドするカード形式で表示し、画面遷移せずに入力できる
- 未送信の入力内容を localStorage で保持する
- フローはLPと同じ3ステップ（入力→確認→送信→完了）

## 現状の調査結果

- LPフォームの送信先: `POST https://contact.pol-is.jp/contact`、JSONボディ
  `{ mail, name, content }`（`Client/public_html/javascript/contact.js`）
- CORS: `access-control-allow-origin: *`（OPTIONS実測済み）。
  app.pol-is.jp からも localhost からも直接POST可能。**バックエンド変更不要**
- LP版の既知問題: `requestContactAPI()` の結果を待たずに完了画面を表示する
  （送信失敗でも完了に見える）。アプリ版では改善する
- アプリ既存部品: `slide-modal full-screen-modal`（テーマ作成 `#theme-create-modal`）、
  `ModalManager`（common.js:734）、`setGrobalLoading`

## UI設計

### モーダル

`Client/public_html_app/index.html` に `#contact-modal` を追加する。
構造はテーマ作成モーダルに準拠:

```html
<div id="contact-modal" class="slide-modal full-screen-modal">
    <div class="label-group">
        <div class="label-header">
            <button class="modal-close-button"><i class="bi bi-x"></i></button>
            <div class="modal-title">お問い合わせ</div>
        </div>
        <div class="modal-text">返信が必要な内容にはメールアドレス宛にご連絡します</div>
    </div>
    <div class="modal-window">
        <div class="modal-scroll-area">
            <div class="modal-content">
                <!-- 入力 / 確認 / 完了 の3ラッパーを .show で切替 -->
            </div>
        </div>
    </div>
</div>
```

3画面はラッパーdivの `.show` 付け外しで切り替える（LP版と同じ方式）:

1. **入力** `.contact-form-wrapper`
   - メールアドレス `<input type="email">`（説明: お問い合わせへの返信に使用します）
   - お名前 `<input type="text">`（任意）
   - お問い合わせ内容 `<textarea rows="6">`
   - エラーメッセージ表示欄 `.contact-error`（通常時非表示）
   - 「確認する」ボタン（`.button.secondary`）
2. **確認** `.contact-confirm-wrapper`
   - 3項目を `textContent` で転記表示（XSS対策。改行は `white-space: pre-wrap`）
   - 「送信する」ボタン（`.button.secondary`）/「戻る」ボタン（`.button.secondary-border`）
   - エラーメッセージ表示欄（送信失敗時にここに表示）
3. **完了** `.contact-complete-wrapper`
   - 送信完了メッセージと「閉じる」ボタン

### メニュー項目の変更

ハンバーガーメニューの「お問い合わせ」を
`<a href="https://pol-is.jp/contact/">` から
`<button id="contact-menu-button" class="menu-item" type="button">` に変更。
クリックでメニューを閉じてモーダルを開く（`#notice-menu-button` と同じ方式）。

### 表示状態のリセット

モーダルを開くたびに入力画面から始める（確認・完了状態は残さない）。
完了画面を出した後に再度開いた場合も入力画面（下書きはクリア済みなので空）。

## 送信

- `POST https://contact.pol-is.jp/contact`
  ヘッダ `Content-Type: application/json`、ボディ `{ mail, name, content }`（LPと同一）
- 「送信する」押下で: ボタンをdisabled+ラベル「送信中…」→ fetch を await
  - 成功（2xx）: 下書きクリア → 完了画面
  - 失敗（非2xx・ネットワークエラー）: 確認画面に留まり、エラーメッセージ
    「送信に失敗しました。時間をおいて再度お試しください。」を表示。
    入力値・下書きは保持。ボタンを再度有効化
- 二重送信防止: disabled中は再クリック無効

## バリデーション（「確認する」押下時）

- お問い合わせ内容: 必須（trim後に空なら「お問い合わせ内容を入力してください」）
- メールアドレス: 必須+簡易形式チェック（`@`を含む。厳密なRFC検証はしない。
  不正なら「メールアドレスを入力してください」）
- お名前: 任意
- エラー時は確認画面に進まず、入力画面のエラー欄にメッセージ表示

## 下書き保持（localStorage）

- キー: `contact_draft`、値: `{ mail, name, content }` のJSON
- 保存タイミング: 3フィールドの `input` イベント（300msデバウンス）
- 復元タイミング: ページ読込時のバインド時に1回（モーダルを開く前でも値はセット済みでよい）
- クリア: 送信成功時のみ（フィールドと localStorage の両方）
- localStorage が使えない環境（プライベートブラウズ等）は try/catch で握り、
  下書きなしで通常動作（favorites.js と同じ方針）

## ファイル構成

| ファイル | 変更 |
|---|---|
| `Client/public_html_app/index.html` | `#contact-modal` DOM追加、メニュー項目変更、`contact.js` の script タグ追加（`?v=__ASSET_VERSION__`） |
| `Client/public_html_app/javascript/contact.js` | 新規。モーダル制御・バリデーション・下書き・送信 |
| `Client/scss/pages/home/_contact.scss` | 新規。フォーム・確認・完了画面のスタイル（アプリのトーン） |
| `Client/scss/pages/home/_index.scss` | `_contact.scss` の forward 追加 |

contact.js の主な関数:

- `initializeContactModal()` — ModalManager生成、メニュー項目バインド、下書き復元
- `openContactModal()` — 状態リセット（入力画面表示）+ showModal
- `bindContactForm()` — 確認/戻る/送信/完了閉じるの各ボタン、inputの下書き保存
- `validateContactInput()` — 上記バリデーション。エラー文字列 or null を返す
- `submitContact(payload)` — fetch実行。成否を返す（例外は握って失敗扱い）
- `saveContactDraft()` / `restoreContactDraft()` / `clearContactDraft()` — localStorage入出力

## スタイル方針

- 入力欄はテーマ作成モーダルの入力欄トーンに合わせる（背景 `--color-bg-gray` 系、
  角丸、フォーカス時ボーダー）
- ラベルは `.modal-section-title` 相当、説明文は `.modal-description` 相当を流用
- エラーメッセージは赤系（`--color-alert` があればそれ、なければ `#d33`）
- 完了画面はチェックアイコン+メッセージを中央配置

## テスト（puppeteer・localhost:8081）

実送信はしない。`page.setRequestInterception(true)` で
`contact.pol-is.jp/contact` へのPOSTをモックする。

1. メニュー→お問い合わせでモーダルが下からスライド表示（`location.href` 不変）
2. バリデーション: 空のまま確認→エラー表示・画面遷移しない
3. 入力→確認画面に値が転記される（改行含む）
4. 送信成功モック→完了画面・localStorage `contact_draft` が消える
5. 送信失敗モック→確認画面に留まりエラー表示・下書き保持
6. 下書き: 入力→リロード→値が復元されている
7. 回帰: テーマ作成・お知らせ・お気に入りのモーダルが従来どおり動く

## スコープ外

- LP側フォームの改修（失敗でも完了表示になる問題はLP側では既知のまま）
- 詳細ページへのお問い合わせ導線追加（メニューはホームのみ）
- 送信内容の文字数制限・レート制限（バックエンド仕様に従う。クライアントでは設けない）
