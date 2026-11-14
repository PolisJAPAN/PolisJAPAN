# PolisJAPAN

pol.is を使った日本語の合意形成サービス。静的サイト（LP・WEB アプリ・管理画面）と、API・バッチの Lambda で構成する。`docs/` の文書がこのシステムの正本である。索引は `docs/README.md`、最初に読むのは `docs/サービス概要.md` と `docs/アーキテクチャ.md`。

## 文書の更新（必須）

コードを変えたら、**同じコミットで**対応する文書を更新する。対応は `docs/docmap.json` の `rules` にある。

| 変更したもの | 更新する文書 |
| --- | --- |
| `Client/` の画面・JS・SCSS | `docs/画面仕様書.md`、`docs/クライアント設計.md`。操作やテストに関わるなら `docs/操作ユースケース.md`、`docs/本番定期テストケース.md` も |
| API の入出力 | `docs/API仕様.md` |
| CSV・DynamoDB・ブラウザに保存するデータ | `docs/データ仕様.md` |
| `Server/` の処理、バッチ、Dockerfile | `docs/サーバー設計.md`。運用に関わるなら `docs/運用手順書.md` も |
| `Infra/terraform/` | `docs/インフラ構成.md`、`Infra/terraform/README.md`。手順が変わるなら `docs/運用手順書.md` も |
| `.github/workflows/` | `docs/運用手順書.md` |
| 全体の構成、設計判断 | `docs/アーキテクチャ.md` |

- 作業を終える前に `python3 scripts/check_docs.py` を実行し、OK になることを確認する。
- 文書に影響しない変更は、コミットメッセージに `Docs: 変更不要（理由）` を入れる。理由は具体的に書く。検査を通すためだけに使わない。
- 不具合や未対応の点を見つけたら `docs/改善バックログ.md` に足す。直したら消す。
- `docs/` には現在の状態だけを書く。計画書・検討書・作業記録をコミットしない（作業用のメモは `docs/superpowers/` に置けるが `.gitignore` 対象）。
- 書き方の規則と検査の詳細は `docs/README.md`。

## 本番に関する注意

- `main` への push で本番に自動デプロイされる（`Client/public_html*/**` と `Server/web/**`）。`main` へのマージと `terraform apply` は、ユーザーの指示があってから行う。
- 本番の `/theme/post_draft` にテスト送信しない（実際のテーマが公開される）。
- S3 の `csv/` 配下を同期・上書きしない（バッチが管理する本番データ）。
- 本番の画面で試してよい操作と禁止操作は `docs/本番定期テストケース.md`、手順は `docs/運用手順書.md`。

## 開発

- 環境の準備と変更の流れ: `docs/開発ガイド.md`。画面の確認方法: `docs/クライアント動作確認ガイド.md`。
- サーバーのテスト: `Server/web` で `pytest`。
- 画面のテスト: `tests/e2e` で `npm run test:local`（ローカルの画面を起動しておく）。画面を変えたら `tests/e2e/specs/` と `docs/本番定期テストケース.md` も直す。
- コミット時の検査を有効にする: `git config core.hooksPath .githooks`
