# PolisJAPAN Terraform

PolisJAPAN の本番環境（フルサーバーレス構成）をコード管理する Terraform 構成。変更の手順と障害対応は `docs/運用手順書.md`、システムの仕様は `docs/仕様書.md` を参照。

## 構成

```
environments/production/   # 実行単位（変数・モジュール接続）と、静的サイト・DNS などの定義
├── main.tf                # モジュールの接続、Lambda の環境変数
├── route53.tf / s3_static.tf / cloudfront_app.tf / cloudfront_legacy.tf / acm_legacy.tf
├── contact_share.tf / ses.tf
└── github_actions.tf      # GitHub Actions 用の OIDC と IAM ロール
modules/
├── data/        # DynamoDB(drafts) / アーカイブS3 / ECR / SSMパラメータ
├── api/         # Lambda(api) + API Gateway + ACM + カスタムドメイン
├── batch/       # Lambda(batch-update/create) + EventBridge Scheduler
├── admin-site/  # admin.pol-is.jp: S3 + CloudFront + CF Function(IP制限)
└── monitoring/  # Route53ヘルスチェック + アラーム（Lambda Errors・投稿滞留）+ SNSメール通知
```

- tfstate は `s3://polisjapan-tfstate`（キー `production/terraform.tfstate`、バージョニングと暗号化あり）。ロックは S3 のロックファイルで行う
- 実行には AWS CLI のプロファイル `terraform` を使う（backend とプロバイダに指定済み）
- プロバイダは大阪（ap-northeast-3）と、エイリアス `us_east_1` の 2 つ。CloudFront 用の証明書、ヘルスチェックのアラーム、contact/share Lambda が us-east-1 にある
- 必要なバージョンは `Infra/terraform/environments/production/versions.tf` を参照

## 変更の手順

```sh
cd Infra/terraform/environments/production
terraform plan
terraform apply
```

`terraform.tfvars`（IP 許可リスト、通知先メールなど）は `.gitignore` 対象。雛形は `terraform.tfvars.example`。

管理しているリソースの一覧は `terraform state list` で確認する。

## 管理対象

- サーバーレス一式: Lambda / API Gateway / DynamoDB / EventBridge Scheduler / SSM パラメータ / ECR / 監視 / 管理画面サイト
- 静的サイト: S3（`pol-is.jp` / `app.pol-is.jp`）、CloudFront、ACM
- Route53 のゾーンと全レコード
- contact/share の Lambda と API Gateway の本体・ステージ、SES（ドメイン ID / DKIM / MAIL FROM）
- GitHub Actions 用の OIDC プロバイダと IAM ロール

**意図的に管理外のもの**:

- tfstate バケット `polisjapan-tfstate`（自己参照になるため手動管理）
- contact/share の **Lambda コード**（`ignore_changes`。コンソールからデプロイする）と、**API Gateway のメソッド・統合定義、IAM サービスロール**（`body` を指定していないため、Terraform が子リソースに触れることはない）
- SES のメールアドレス ID（個人のアドレスをコードに残さない）
- IAM ユーザー（`terraform-deploy` など。自分の権限を自分で壊す事故を防ぐ）

**データ保護**: S3 バケット（lp / app / archive）、Route53 ゾーン、DynamoDB に `prevent_destroy` を設定している。

## Lambda のイメージと Terraform の分担

- Lambda の `image_uri` は `ignore_changes`。イメージの更新は CI（タグはコミット SHA）、インフラの定義は Terraform が受け持つ。tfvars の `api_image_uri` / `batch_create_image_uri` は、関数を最初に作るときだけ使われる
- GitHub Actions の認証は OIDC フェデレーション（`github_actions.tf`）。ロールを使えるのは本リポジトリの `main` ブランチのワークフローだけ
  - `polisjapan-gha-deploy-client`: S3 同期と CloudFront 無効化のみ。`app.pol-is.jp/csv/*` への書き込みは明示的に拒否
  - `polisjapan-gha-deploy-server`: ECR への push と、3 関数の `UpdateFunctionCode` のみ

## シークレット

- SSM パラメータ（SecureString）は、Terraform が器だけを作り、値の変更は無視する（`ignore_changes`）。値は `aws ssm put-parameter` で入れる
- Terraform は apply のときに SSM の値を読み、Lambda の環境変数へ入れる。値を変えたら `terraform apply` が必要（手順は `docs/運用手順書.md` §5.5）
- そのため **tfstate には復号した値が含まれる**。tfstate バケットは非公開・暗号化・バージョニングを保ち、`terraform-deploy` ユーザー以外にアクセス権を与えない
