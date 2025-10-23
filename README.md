# PolisJAPAN
[PolisJAPAN](https://pol-is.jp/) の開発用リポジトリです。

## ユーザーの方へ

こちらは開発用のページになります。サービス利用に関しては[WEBアプリ版PolisJAPAN](https://app.pol-is.jp/)をご覧ください。

## 開発のための準備

開発環境アプリケーションはすべて[Docker](https://www.docker.com/ja-jp/products/docker-desktop/)上で動作します。
Docker をインストール後、このリポジトリを Fork して `git clone` してください。

## サーバーサイド開発用環境
### コンテナの実行
リポジトリのルートにて、下記コマンドを実行することで開発用環境が立ち上がります。

```sh
cd Server
docker-compose build
docker-compose up
```

### API実行
[SwaggerDocument](http://localhost:80/docs)にアクセスして、実際のAPIをテストすることができます。


## クライアントサイド開発用環境
### コンテナの実行
リポジトリのルートにて、下記コマンドを実行することで開発用環境が立ち上がります。

```sh
cd Client
docker-compose build
docker-compose up
```

### HTML表示
コンテナが立ち上がったら、下記ポートにアクセスしてHTMLを確認することができます、
[LP](http://localhost:8080/)
[WEBアプリケーション](http://localhost:8081/)
[管理画面](http://localhost:8082/)

## ライセンス
[Polisライセンス規約](https://compdemocracy.org/FAQ/)に従い、AGPL-3.0 licenseでの提供を行っています。