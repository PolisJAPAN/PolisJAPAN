# テーマ作成時の文字数バリデーション 設計書

日付: 2026-07-10
状態: ユーザー承認済み（会話上で設計合意。カウンターの見た目はローカル確認で最終判断）

## 要件

- テーマ作成時に **タイトル80文字・説明200文字** の上限バリデーションを行う
- **既存データは許容**（公開済みthemes.csv・admin編集・表示系には一切影響させない。
  バリデーションは新規投稿経路 = post_draft のみ）
- クライアント+サーバー両方で実施（2026-07-10ユーザー選択）

## 文字数の数え方

コードポイント数（JS: `[...str].length`、Python/pydantic: `len(str)` 相当）。
絵文字等のサロゲートペアも1文字と数え、クライアント・サーバーで一致させる。
`maxlength` 属性はUTF-16単位のため厳密には異なるが、最終チェックが
コードポイント基準のため実害なし。

## クライアント（Client/public_html_app/javascript/create.js + scss/pages/home/_create.scss）

上限定数: `THEME_TITLE_MAX = 80` / `THEME_DESCRIPTION_MAX = 200`

1. **maxlength属性**: タイトル `#theme-title-textarea` に `maxlength="80"`、
   説明 `#description-textarea` に `maxlength="200"` を付与（通常入力の抑止）
2. **文字数カウンター**: 両textareaの下に「45/80」形式で常時表示。
   `input` イベントで更新。**上限到達（残0）で赤色**（`.over` クラス）。
   AIアシスト・下書き復元などJS代入経路の直後も更新する
3. **ステップ進行時チェック**: 「次へ」押下時に超過していたら
   エラーメッセージを表示して進めない
   - タイトル: 「タイトルは80文字以内で入力してください」
   - 説明: 「説明は200文字以内で入力してください」
   - AIアシストが200字超の説明を生成した場合もここで捕捉される
     （maxlengthはJSの `.value` 代入に効かない）。自動切り捨てはしない
     （ユーザーが編集して収める）
4. **投稿前チェック**: `requestThemePostDraftAPI` 呼び出し前にも同チェック（保険）。
   超過時は投稿せずエラー表示

## サーバー（Server/web/api/schemas/theme.py）

`ThemePostDraftRequest` のみ変更:

```python
theme: str = Field(max_length=80, description="テーマ(ユーザー設定)")
description: str = Field(max_length=200, description="説明(ユーザー設定)")
```

- 超過時はFastAPI/pydanticの422（クライアントは投稿失敗の既存エラー処理経路に乗る）
- generate系API（generate_axis / generate_comments / generate_descriptions）は変更しない
  （クライアントで先にタイトルが80字以内に抑えられるため）

## スコープ外

- 既存データの修正・移行
- コメント（意見）入力の文字数制限
- admin画面のバリデーション
- generate系APIの入力制限

## テスト

**サーバー（pytest）**: post_draftに対し
- theme 80文字ちょうど → 受理 / 81文字 → 422
- description 200文字ちょうど → 受理 / 201文字 → 422
- 既存のpost_draftテストが引き続き通ること

**クライアント（puppeteer・localhost:8081、post_draftはモック）**
- カウンターが「0/80」「0/200」で表示され、入力で増える・上限で赤色
- maxlengthにより81文字目が入らない
- JSで201文字を説明に代入（AI生成の再現）→「次へ」でエラー表示・進まない
- 上限内の入力では従来どおりステップが進み、投稿（モック）まで通る
- 回帰: AIアシスト/マニュアル切替・下書き復元でカウンターが正しく追従

## 影響範囲・デプロイ

| ファイル | 変更 |
|---|---|
| `Client/public_html_app/javascript/create.js` | 定数・maxlength・カウンター・チェック |
| `Client/scss/pages/home/_create.scss` | カウンターのスタイル |
| `Server/web/api/schemas/theme.py` | Fieldに max_length 2箇所 |

デプロイ時は deploy-client / deploy-server の両ワークフローが走る。
