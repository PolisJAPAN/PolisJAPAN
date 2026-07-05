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

## セキュリティ注記

- SSMパラメータの値はTerraformでは管理しない（`ignore_changes`）。ただしLambda環境変数への注入のため **tfstateには復号値が含まれる**。tfstateバケットは非公開・暗号化・バージョニングを必須とし、terraform-deployユーザー以外にアクセス権を与えないこと
- `terraform.tfvars` はIP許可リスト等を含むため `.gitignore` 対象
- 既知の残タスク: `services/batch.py` の pol.is ログイン情報ハードコードを環境変数（POLIS_LOGIN_USER / POLIS_LOGIN_PASSWORD、Terraformが注入済み）から読むようにするコード修正が必要（カットオーバー前に実施）
