# PolisJAPAN-Contact Lambda

お問い合わせフォーム（LP `pol-is.jp/contact` / アプリ内モーダル）の送信先。
`POST https://contact.pol-is.jp/contact` → API Gateway (REST, ID: 7r1e9gjfmk) → この Lambda。
受信内容を SES で管理者(info.polis.japan@gmail.com)へ転送し、入力されたメールアドレスへ自動返信する。

- リージョン: **us-east-1**（関数名: `PolisJAPAN-Contact`）
- ランタイム: Python 3.14 / ハンドラ: `lambda_function.lambda_handler`
- Terraform: `Infra/terraform/environments/production/contact_share.tf`
  （インフラ属性のみ管理。コードは ignore_changes のため、このディレクトリが正）

## デプロイ手順（手動）

```bash
cd Server/lambda/contact
zip -j /tmp/contact-lambda.zip lambda_function.py
aws lambda update-function-code \
  --function-name PolisJAPAN-Contact \
  --zip-file fileb:///tmp/contact-lambda.zip \
  --profile terraform --region us-east-1
```

## 注意

- レスポンスの `Access-Control-Allow-Origin: *` は必須（Lambdaプロキシ統合のため、
  プリフライトとは別に**実レスポンス側**にも必要。2026-07-09にUIが失敗表示になる
  障害の修正として追加）。削除するとブラウザから結果が読めなくなる
- 有効なPOSTを送ると実メールが2通飛ぶ（管理者転送+自動返信）。
  疎通確認は不正JSONボディ（例: `-d 'x'`）で行うと、例外経路のためメールは飛ばない
