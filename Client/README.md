# HTML 開発環境

## 概要
- dockerコンテナで、HTML公開サーバと、SCSSビルドコンテナを作成し、ローカルで確認できるようにしています。
- 開発時はdockerを起動してください。
- 静的ファイルを配信するWEBサーバーとしては非効率な仕組みですので、本番公開時はpublic_html内をファイルストレージにアップして公開してください。

## SCSSについて
- `scss/` フォルダで SCSS を分割管理します（`_variables.scss` など）。
- `style.scss` でサブscssを読み込み、最終的に CSS にコンパイルします。
- コンパイル後の CSS は、3 サイトそれぞれの `style.css`（`public_html/`・`public_html_app/`・`public_html_admin/`）に出力されます。
- HTML 側は各サイトの `style.css` を読み込みます。

## 注意事項
- style.scss以外のscssは「_header.scss」のように先頭にアンダーバーを付けてください。

---

## 使うコマンド

### ローカル環境実行
```
docker-compose up
```
### S3アップロード
> **通常は手動アップロード不要です。** mainブランチへのpushでGitHub Actions（`.github/workflows/deploy-client.yml`）が自動的にS3同期とCloudFront無効化を行います。以下はActions障害時などのフォールバック手順です。
```
aws s3 sync ./public_html_app/ s3://app.pol-is.jp/ --exclude ".DS_Store"  --exclude "*/.DS_Store" --exclude "csv/*"  --delete --dryrun
aws s3 sync ./public_html_app/ s3://app.pol-is.jp/ --exclude ".DS_Store"  --exclude "*/.DS_Store" --exclude "csv/*"  --delete
aws cloudfront create-invalidation --distribution-id E1VDGUET2Z2OBX --paths "/*"

aws s3 sync ./public_html/ s3://pol-is.jp/ --exclude ".DS_Store" --exclude "*/.DS_Store" --exclude "csv/*"  --delete --dryrun
aws s3 sync ./public_html/ s3://pol-is.jp/ --exclude ".DS_Store" --exclude "*/.DS_Store" --exclude "csv/*"  --delete
aws cloudfront create-invalidation --distribution-id E1L9GH70CTWAY6 --paths "/*"

aws s3 sync ./public_html_admin/ s3://admin.pol-is.jp/ --exclude ".DS_Store" --exclude "*/.DS_Store" --delete --dryrun
aws s3 sync ./public_html_admin/ s3://admin.pol-is.jp/ --exclude ".DS_Store" --exclude "*/.DS_Store" --delete
aws cloudfront create-invalidation --distribution-id E2D8XIPYTKLR5Z --paths "/*"
```

> 注意: 自動デプロイは HTML 内の `?v=__ASSET_VERSION__` をコミット SHA に置き換え、HTML を `no-cache` で配信します。手動で同期するとこの置き換えが行われないため、利用者のブラウザに古い CSS・JS が残ることがあります。

```
aws s3 sync s3://app.pol-is.jp/csv/ ./public_html_app/csv/ --exclude ".DS_Store"  --exclude "*/.DS_Store" --delete --dryrun
aws s3 sync s3://app.pol-is.jp/csv/ ./public_html_app/csv/ --exclude ".DS_Store"  --exclude "*/.DS_Store" --delete
```

