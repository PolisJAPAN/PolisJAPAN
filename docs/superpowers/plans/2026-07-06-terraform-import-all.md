# 既存リソースのTerraform一括管理化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Terraform管理外で稼働している既存AWSリソース（S3・CloudFront・Route53・contact/share系Lambda・ACM・SES）をすべて `import` で管理下に取り込み、インフラ全体を単一のTerraform構成で一括管理できる状態にする。

**Architecture:** Terraform 1.5+の `import` ブロック方式。各グループごとに「①現設定をコード化 → ②plan で `N to import / 0 to destroy`（変更はタグのみ許容）を確認 → ③apply」を繰り返す。app.pol-is.jp CloudFrontで実証済みの手順（cloudfront_app.tf, f92e258）の横展開。

**安全原則（ユーザー要求: データ消失ゼロ／短時間の不通は許容）:**
1. **着手前に全データをローカル+アーカイブS3へバックアップ**（S3全オブジェクト・Route53ゾーン・CloudFront/Lambda/SES設定・DynamoDBエクスポート・tfstate）
2. **importは非破壊** — 取り込むだけで実リソースに変更を加えない。危険は「コードと実物の差分」なので、**applyゲート = plan出力に `0 to destroy` かつ 変更(~)がタグのみ** をタスクごとに徹底する
3. **データを持つリソースには `lifecycle { prevent_destroy = true }`** を付与（S3バケット・Route53ゾーン・DynamoDB）。将来の誤destroy/構成削除をTerraform自身が拒否する
4. **各applyの直前に `terraform state pull` でstateのローカルスナップショット**を取る（tfstateバケット自体もバージョニング済み）
5. 失敗時の切り戻し: `terraform state rm <resource>` でimportを取り消せば管理外に戻るだけで、実リソースは無傷

---

## 対象と対象外

### 取り込む（8グループ・約35リソース）

| グループ | リソース |
| --- | --- |
| A. S3静的サイト | バケット `pol-is.jp` / `app.pol-is.jp` + 各サブリソース（website設定・バケットポリシー・public access block・バージョニング・ライフサイクル） |
| B. ACM (us-east-1) | 証明書×4（pol-is.jp / app.pol-is.jp / share / contact） |
| C. CloudFront | LP `E1L9GH70CTWAY6` / share `E2VD4O5M17XG0X` / contact `E2X1TX47YAAO8F`（appは取込済み） |
| D. Route53 | ホストゾーン `pol-is.jp` + 全レコード（api/app/LP/share/contactのAエイリアス、MX/TXT/DKIM×3、旧ACM検証CNAME×4。admin系・api/admin検証CNAMEは管理済み） |
| E. Lambda (us-east-1) | `PolisJAPAN-Contact` / `PolisJAPAN-GetOGP` + 実行ロール + ロググループ |
| F. API Gateway (us-east-1) | REST API `7r1e9gjfmk`(contact) / `jh9u2wjvea`(share) + リソース/メソッド/デプロイ/ステージ |
| G. SES (us-east-1) | ドメインID `pol-is.jp`・DKIM・MAIL FROM・メールアドレスID |
| H. ガードレール | 上記+既存管理分（DynamoDB・アーカイブS3等）への prevent_destroy 付与 |

### 取り込まない（理由つき）

| リソース | 理由 |
| --- | --- |
| tfstateバケット `polisjapan-tfstate` | 自己参照（stateを保存する箱をstateで管理する循環）。慣例通り管理外・手動管理 |
| 旧EC2・EIP・SG・VPC・IGW | Phase 5で削除予定。消すものを取り込まない |
| `cw-syn-results-*` バケット・旧SNSトピック | 同上（削除候補） |
| `polisjapan-e2e-sandbox` | 一時リソース。Phase 5で削除 |
| IAMユーザー（terraform-deploy等） | 自己権限の管理は事故時に身動きが取れなくなるため手動管理を維持 |

---

## Task 0: 全量バックアップ（データ消失対策の本丸）

**Files:** なし（ローカル `~/PolisJAPAN-backup-<date>/` と `s3://polisjapan-archive/pre-import-backup/` へ）

- [ ] S3全オブジェクトをローカルへ: `aws s3 sync s3://pol-is.jp ./pol-is.jp/` と `app.pol-is.jp`（csv含む全て、計約10MB）
- [ ] Route53ゾーン全レコードをJSONエクスポート
- [ ] CloudFront×3・Lambda×2（コードzip含む）・API GW×2・SES・ACMの設定JSONエクスポート
- [ ] DynamoDB `polisjapan-drafts` 全件をJSONエクスポート（約400行）
- [ ] `terraform state pull > state-backup.json`
- [ ] 上記一式を `s3://polisjapan-archive/pre-import-backup/<date>/` にも同期
- [ ] **検証**: ローカルバックアップのファイル数・サイズがS3実物と一致すること（`aws s3 ls --summarize` と `du` の突合）

## Task 1: ガードレール先行導入

**Files:** Modify: `Infra/terraform/modules/data/main.tf`, `environments/production/cloudfront_app.tf`

- [ ] 既存管理分のデータ保有リソースに `lifecycle { prevent_destroy = true }` を追加: DynamoDB `drafts`・S3 `archive`・（cloudfront_appは配信のみなので対象外）
- [ ] `terraform plan` → **No changes**（lifecycleはplanに現れない）を確認して apply（stateのみ更新）

## Task 2: グループA — S3静的サイト2バケット

**Files:** Create: `environments/production/s3_static.tf`

- [ ] 現設定を取得（get-bucket-website / policy / versioning / lifecycle / public-access-block）しコード化。`prevent_destroy = true` を両バケットに付与
- [ ] importブロック: `aws_s3_bucket` ×2 + サブリソース（website×2, policy×2, versioning×2, public_access_block×2, lifecycle×1(appのみ)）
- [ ] `terraform plan` → **11 to import / 0 add / 0 destroy、変更はタグのみ** を確認
- [ ] apply → 直後に `curl -I https://pol-is.jp/` `https://app.pol-is.jp/` が200であること、`aws s3api get-bucket-policy` が変わっていないことを確認

## Task 3: グループB — ACM証明書×4（最低リスク・ウォームアップ）

**Files:** Create: `environments/production/acm_legacy.tf`

- [ ] 4証明書をコード化（domain_name/validation_method のみのシンプルなリソース）+ import
- [ ] plan → 4 to import / 0 destroy → apply
- [ ] 注意: `create_before_destroy` lifecycleを付与（将来の更新時にCloudFrontから参照中の証明書を先に消さないため）

## Task 4: グループC — CloudFront×3

**Files:** Create: `environments/production/cloudfront_lp.tf`, `cloudfront_share_contact.tf`

- [ ] app実績と同じ手順: get-distribution-config → コード化 → import → plan差分（タグのみ）確認 → apply
- [ ] share/contactはオリジンがAPI GW（`/Production`・`/production` のstage pathの大文字小文字が異なる点に注意。実物に合わせる）
- [ ] apply後: `curl -I` で LP/share/contact 3ドメインの応答が変わらないこと

## Task 5: グループD — Route53ゾーンと全レコード

**Files:** Create: `environments/production/route53.tf`。Modify: `main.tf`（`data.aws_route53_zone` → 管理リソース参照に切替）

- [ ] `aws_route53_zone` + レコード全件（約12件）をコード化。ゾーンに `prevent_destroy = true`
- [ ] **api.pol-is.jp のAエイリアス**はカットオーバーで手動変更したものを取り込み、`module.api[0].custom_domain_target` 参照で記述（手動管理の解消）
- [ ] importレコードのID形式は `<zone_id>_<name>_<type>`
- [ ] plan → 全件 import / **0 destroy・0 replace** を厳格確認（レコードのreplaceはDNS瞬断になるため、出たら原因を直してからapply）
- [ ] apply後: `dig` で api/app/LP/share/contact/admin の解決結果が適用前と同一であること

## Task 6: グループE+F — contact/share Lambda・API Gateway（us-east-1）

**Files:** Create: `environments/production/contact_share.tf`

- [ ] Lambda×2（zipはS3経由でなく現デプロイ済みコードを維持: `ignore_changes = [filename, source_code_hash]` で「コードはTerraform管理外・インフラのみ管理」とする — 消失リスクなし）
- [ ] 実行ロール・ポリシー・ロググループ・REST API・リソース/POSTメソッド/統合・ステージをimport
- [ ] plan → 0 destroy確認 → apply
- [ ] apply後: LPのお問い合わせフォームE2E（テスト送信1通）とshareリンクの動作確認

## Task 7: グループG — SES

**Files:** Create: `environments/production/ses.tf`

- [ ] `aws_ses_domain_identity` / `aws_ses_domain_dkim` / `aws_ses_domain_mail_from` / `aws_ses_email_identity` をimport
- [ ] plan → 0 destroy → apply（SESは設定のみでデータなし・低リスク）

## Task 8: 総仕上げ

- [ ] `terraform plan` 全体で **No changes** を確認（全リソースがコード=実物）
- [ ] `Infra/terraform/README.md` に「管理対象一覧と対象外リスト（理由つき）」を追記
- [ ] コミット（タスクごとに分割コミット済みのはず）+ メモリ更新

---

## リスクと対応

| リスク | 対応 |
| --- | --- |
| コード化ミスでapply時に意図しない変更 | タスクごとの「0 destroy・変更はタグのみ」ゲート。疑わしい差分が出たらapplyせずコードを実物に合わせる |
| Route53レコードのreplaceによるDNS瞬断 | Task 5でreplace検出時はapply中止。エイリアス→エイリアスのin-place更新のみ許容 |
| S3バケットポリシー/公開設定の意図しない変更でサイト不通 | 「短時間の不通は許容」の範囲だが、apply直後のcurl確認+バックアップからの即復元手順あり |
| 将来の誤destroy | prevent_destroy + S3は非空バケット削除をAWS自体が拒否（force_destroy=false維持） |
| state破損 | tfstateバケットのバージョニング + 各apply前の `state pull` ローカル保存 |

**所要見積**: Task 0が15分、Task 2〜7が各15〜30分（plan差分の消し込み次第）。合計2〜3時間。途中で中断しても、完了済みタスクだけが管理下に入った健全な状態で止まる。
