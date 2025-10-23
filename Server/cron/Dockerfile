FROM alpine:3.20

# curl と cron を使用
RUN apk add --no-cache curl

# crontab をコピー
COPY crontab.txt /etc/crontabs/root

# cronをフォアグラウンドで実行し、ログをstdoutに流す
CMD ["crond", "-f", "-l", "2"]
