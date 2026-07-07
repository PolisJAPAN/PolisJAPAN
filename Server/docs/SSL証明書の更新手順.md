# SSL証明書（Let's Encrypt）の更新手順

ドメイン: **api.pol-is.jp**  
証明書は約90日で期限切れになるため、期限前に更新してください。

---

## 前提

- 本番サーバーで `Server/` をカレントに作業する
- `docker compose` はベースの `docker-compose.yml` と本番用 `docker-compose.prd.yml` をマージして使う想定

---

## 手順1: 本番環境でコンテナを起動

```bash
cd Server
docker compose -f docker-compose.yml -f docker-compose.prd.yml up -d
```

**重要**: nginx が起動している必要があります。  
certbot の HTTP-01 チャレンジは、80番で `/.well-known/acme-challenge/` にアクセスされるため、nginx が稼働していないと更新できません。

---

## 手順2: certbot で証明書を更新

次のいずれかを実行します。

### 方法A: 更新のみ（既に証明書がある場合・推奨）

```bash
docker compose -f docker-compose.yml -f docker-compose.prd.yml run --rm certbot renew
```

- 有効期限が近い証明書だけ更新されます。
- 更新後、nginx に新しい証明書を読み込ませるため、手順3で nginx をリロードします。

### 方法B: 期限切れなどで「更新」が通らない場合（再発行）

既に期限切れで `renew` がうまくいかない場合は、同じ webroot で再発行します。

```bash
docker compose -f docker-compose.yml -f docker-compose.prd.yml run --rm certbot certonly \
  --webroot \
  -w /var/www/certbot \
  -d api.pol-is.jp \
  --email あなたのメールアドレス@example.com \
  --agree-tos \
  --force-renewal
```

- `--force-renewal` で既存証明書を強制的に更新します。
- 初回発行時は `--agree-tos` と `--email` が必須です。更新のみのときは省略できることが多いです。

---

## 手順3: nginx に証明書の再読み込みをさせる

証明書が更新されたら、nginx をリロードします。

```bash
docker compose -f docker-compose.yml -f docker-compose.prd.yml exec nginx nginx -s reload
```

**注意**: 本番サーバーではコンテナがプロジェクト名 `PolisJAPAN` で起動されているため、上記の `exec` は `service "nginx" is not running` になります。その場合はコンテナ名を直接指定してください。

```bash
docker exec PolisJAPAN_nginx nginx -s reload
```

`exec` が使えない環境の場合は、nginx コンテナの再起動でも構いません。

```bash
docker compose -f docker-compose.yml -f docker-compose.prd.yml restart nginx
```

---

## 手順4: 動作確認

- ブラウザで `https://api.pol-is.jp` にアクセスし、証明書の有効期限が延びていることを確認する。
- 必要に応じて:  
  `openssl s_client -connect api.pol-is.jp:443 -servername api.pol-is.jp < /dev/null 2>/dev/null | openssl x509 -noout -dates`

---

## 定期更新（自動化）

**本番サーバーには設定済み（2026-07-04〜）**: Amazon Linux 2023 には cron が無いため、systemd timer で自動更新を構成済みです。

- ユニット: `/etc/systemd/system/certbot-renew.service`（certbot renew → `docker exec PolisJAPAN_nginx nginx -s reload`）
- タイマー: `/etc/systemd/system/certbot-renew.timer`（毎月1日・15日 03:00、`Persistent=true`）
- 状態確認: `systemctl list-timers certbot-renew*` ／ ログ: `sudo journalctl -u certbot-renew.service`

以下は cron が使える環境向けの参考例です。

```bash
# 毎月1日 午前3時に更新試行 & nginx リロード（例）
0 3 1 * * cd /path/to/Server && docker compose -f docker-compose.yml -f docker-compose.prd.yml run --rm certbot renew && docker compose -f docker-compose.yml -f docker-compose.prd.yml exec nginx nginx -s reload
```

- `run --rm certbot renew` は「更新が必要な証明書だけ」更新するので、毎月実行しても問題ありません。
- 証明書の置き場所は `./certs`（コンテナ内の `/etc/letsencrypt`）で、nginx は同じパスを参照しているため、更新後に reload すれば反映されます。

---

## トラブルシュート

| 現象 | 確認・対処 |
|------|-------------|
| `renew` でエラー | 手順2の方法Bで `--force-renewal` を付けて再発行を試す。 |
| チャレンジが通らない | 80番がファイアウォールで開いているか、nginx が起動しているか確認。`curl http://api.pol-is.jp/.well-known/acme-challenge/` でアクセスできるか確認。 |
| nginx が古い証明書のまま | 手順3の `nginx -s reload` または `restart nginx` を実行したか確認。 |
| 証明書の場所 | ホストの `Server/certs/` がコンテナの `/etc/letsencrypt` にマウントされているか確認。 |

---

## 参考

- 証明書の実体: `Server/certs/live/api.pol-is.jp/`（fullchain.pem, privkey.pem 等）
- ACME チャレンジ用: `Server/webroot/` → nginx の `/.well-known/acme-challenge/` で配信
