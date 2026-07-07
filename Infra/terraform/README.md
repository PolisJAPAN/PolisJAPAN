# PolisJAPAN Terraform

サーバーレス移行（`docs/サーバーレス移行設計書.md`）の新環境をコード管理するTerraform構成。

## 方針

- **新規リソースの作成のみ**を行う。稼働中の既存リソース（EC2・既存CloudFront/S3・Route53の既存レコード）には一切触れない
- Route53には「追加」だけ行う（ACM検証用CNAME、新設の admin.pol-is.jp）。`api.pol-is.jp` の切り替えはカットオーバーRunbookで手動実施
- EventBridge Schedulerは `scheduler_state = "DISABLED"`（デフォルト）で作成し、旧cronとの二重実行（pol.isへのテーマ二重投稿）を防ぐ。カットオーバー時にENABLEDへ変更する

## 構成

```
environments/production/   # 実行単位（変数・モジュール接続）
modules/
├── data/        # DynamoDB(drafts) / アーカイブS3 / ECR / SSMパラメータ
├── api/         # Lambda(api) + API Gateway + ACM + カスタムドメイン
├── batch/       # Lambda(batch-update/create) + EventBridge Scheduler
├── admin-site/  # admin.pol-is.jp: S3 + CloudFront + CF Function(IP制限)
└── monitoring/  # Route53ヘルスチェック + アラーム + SNSメール通知
```

## Bootstrap（初回のみ）

tfstate用バケットを手動作成する:

```sh
aws s3 mb s3://polisjapan-tfstate --region ap-northeast-3 --profile terraform
aws s3api put-bucket-versioning --bucket polisjapan-tfstate \
  --versioning-configuration Status=Enabled --profile terraform
aws s3api put-public-access-block --bucket polisjapan-tfstate \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true \
  --profile terraform
```

## 段階的なapply手順

Lambdaはコンテナイメージが先にECRに存在しないと作成できないため、2段階でapplyする。

```sh
cd Infra/terraform/environments/production
cp terraform.tfvars.example terraform.tfvars   # 値を編集（.gitignore対象）
terraform init

# --- 第1段階: データ層・管理画面・監視（イメージ不要のリソース） ---
terraform apply
# → 出力された ECRリポジトリURL にイメージをpushする（手順は移行プラン参照）

# --- シークレットの投入（初回のみ・値はCHANGEMEで作成されている） ---
aws ssm put-parameter --name /polisjapan/openai-api-key --type SecureString --value '...' --overwrite --profile terraform
# 同様に: langsmith-api-key / batch-access-key / user-access-key / encrypt-salt /
#         polis-login-user / polis-login-password

# --- 第2段階: Lambda・API GW・スケジューラ ---
# terraform.tfvars に api_image_uri / batch_create_image_uri を設定して
terraform apply
```

## カットオーバー時の操作

1. `docs/サーバーレス移行設計書.md` §5 Runbook に従う
2. Route53 の `api.pol-is.jp` を、出力 `api_custom_domain_target` のエイリアスへ手動で切り替える
3. `scheduler_state = "ENABLED"` にして `terraform apply`（旧cron停止後に実施）

## 管理対象（2026-07-06 既存リソース取り込み完了・計115リソース）

新環境一式（Lambda/API GW/DynamoDB/EventBridge/SSM/ECR/監視/admin-site）に加え、既存リソースもすべてimport済み:
S3（pol-is.jp / app.pol-is.jp とサブ設定）、CloudFront×4、ACM×6、Route53ゾーン+全レコード、
contact/share Lambda + API Gateway本体/ステージ、SES（ドメインID/DKIM/MAIL FROM）。

**意図的に管理外のもの**:
- tfstateバケット `polisjapan-tfstate`（自己参照になるため手動管理）
- contact/share の **Lambdaコード**（ignore_changes。コンソールデプロイのまま）と **API GWメソッド/統合定義・IAMサービスロール**（凍結済みレガシー。`body`を指定していないためTerraformが子リソースに触れることはない）
- SESのメールアドレスID（個人アドレスをコードに残さない）
- IAMユーザー（terraform-deploy等。自己権限の管理事故防止）
- 旧EC2・EIP・SG・VPC・旧SNS・cw-syn-resultsバケット・e2e-sandbox（Phase 5で削除予定のため取り込まない）

**データ保護**: S3バケット（lp/app/archive）・Route53ゾーン・DynamoDBに `prevent_destroy` を設定済み。
取り込み前の全データバックアップは `s3://polisjapan-archive/pre-import-backup/` とローカルに保全。

## セキュリティ注記

- SSMパラメータの値はTerraformでは管理しない（`ignore_changes`）。ただしLambda環境変数への注入のため **tfstateには復号値が含まれる**。tfstateバケットは非公開・暗号化・バージョニングを必須とし、terraform-deployユーザー以外にアクセス権を与えないこと
- `terraform.tfvars` はIP許可リスト等を含むため `.gitignore` 対象
- ~~既知の残タスク: `services/batch.py` の pol.is ログイン情報ハードコード~~ → 解消済み（2026-07-07 環境変数化・フォールバック実値も削除）。**過去コミットに実値が残っているため pol.is パスワードのローテーションは必要**（Phase 5）

## GitHub Actions による自動デプロイ（2026-07-07〜）

クライアント・サーバーのデプロイはGitHub Actionsが行う（`.github/workflows/deploy-client.yml` / `deploy-server.yml`）。

- 認証は **OIDCフェデレーション**（`github_actions.tf`）。長期アクセスキーをGitHubに置かない。Assumeできるのは本リポジトリ `main` ブランチのワークフローのみ
- IAMロール: `polisjapan-gha-deploy-client`（S3同期 + CloudFront無効化のみ。`app.pol-is.jp/csv/*` への書き込みは明示Deny）/ `polisjapan-gha-deploy-server`（ECR push + 3関数の `UpdateFunctionCode` のみ）
- **Lambdaの `image_uri` は `ignore_changes`**: イメージ更新はCI（コミットSHAタグ）、インフラ定義はTerraformの役割分担。tfvarsの `api_image_uri` / `batch_create_image_uri` は初回作成時のみ使用される
