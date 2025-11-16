from __future__ import annotations

import os
from dataclasses import dataclass
import time
from typing import Any, Mapping, Optional, Sequence

import aioboto3
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError


class StorageS3Error(RuntimeError):
    """S3操作中の例外を包括するアプリ固有の例外。"""


@dataclass(frozen=True)
class StorageS3Options:
    """
    S3クライアントの接続設定を保持するデータクラス。

    Attributes:
        region_name (Optional[str]): 接続対象のAWSリージョン名（例: "ap-northeast-1"）。
        connect_timeout (int): 接続タイムアウト秒数。
        read_timeout (int): 読み取りタイムアウト秒数。
        max_attempts (int): リトライ回数（botocoreの標準リトライ設定を利用）。
    """
    region_name: Optional[str] = None
    connect_timeout: int = 5
    read_timeout: int = 30
    max_attempts: int = 5


class StorageS3:
    """
    非同期S3クライアント（aioboto3ベース）を管理するクラス。

    明示的な `open()` / `close()` によるライフサイクル管理を採用し、
    非同期処理中に安全かつ効率的なS3アクセスを提供する。

    環境変数 `APP_ENV` に応じて資格情報を自動切り替え。
    （例: localhost 環境では明示的に固定キーを使用）
    """
    
    def __init__(self, bucket: str, base_prefix: str | None = None, *, options: StorageS3Options | None = None) -> None:
        """
        S3ストレージクライアントを初期化。

        Args:
            bucket (str): 対象のS3バケット名。
            base_prefix (Optional[str]): バケット内で共通的に付与するパスプレフィックス。
            options (Optional[StorageS3Options]): 接続・リトライなどの設定オプション。
        """
        
        self.bucket = bucket
        self.base_prefix = (base_prefix or "").lstrip("/")
        self._opts = options or StorageS3Options()
        
        # 環境変数を読み込み
        APP_ENV = os.getenv("APP_ENV", "")

        # 環境別の変数を読み込み
        if APP_ENV == "localhost":
            # localhostではサーバーへ権限付与できないため短期キーを使用
            self._session = aioboto3.Session(
                aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID", ""),
                aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", ""),
                region_name = os.getenv("AWS_DEFAULT_REGION", "")
            )
        else:
            # 本番ではIAMロールの権限付与で自動認証　
            self._session = aioboto3.Session()
        
        self._client = None

        self._config = Config(
            region_name=self._opts.region_name,
            read_timeout=self._opts.read_timeout,
            connect_timeout=self._opts.connect_timeout,
            retries={"max_attempts": self._opts.max_attempts, "mode": "standard"},
        )

    # ---- lifecycle ----
    async def open(self) -> None:
        """
        S3クライアントを初期化し、非同期セッションを開始する。

        Notes:
            - `close()` が呼ばれるまでクライアントを保持する。
            - 再呼び出し時は無視される（複数回openしても問題なし）。
        """
        if self._client is None:
            self._client = await self._session.client("s3", config=self._config).__aenter__()

    async def close(self) -> None:
        """
        S3クライアントを明示的に破棄し、セッションを終了する。

        Notes:
            - `open()` に対応する明示的な終了処理。
            - 破棄済みの場合は何もしない。
        """
        if self._client is not None:
            await self._client.__aexit__(None, None, None)
            self._client = None

    def _exist_client(self):
        """
        現在のS3クライアントインスタンスを返す。

        Raises:
            StorageS3Error: `open()` が呼ばれていない状態でアクセスした場合。
        """
        if self._client is None:
            raise StorageS3Error("S3 client not opened. Call await s3.open() first.")
        return self._client

    # ---- methods ----
    async def exists(self, key: str) -> bool:
        """
        指定キーのオブジェクトが S3 バケットに存在するかを確認する。

        Args:
            key (str): 存在確認対象のオブジェクトキー（prefixを除いた相対パス）。

        Returns:
            bool: 存在する場合は True、存在しない場合は False。

        Raises:
            StorageS3Error: 通信エラー、ネットワーク障害など（404 以外の場合）。
        """
        full_object_key = self._full_key(key)

        try:
            await self._exist_client().head_object(
                Bucket=self.bucket,
                Key=full_object_key
            )
            return True

        except ClientError as e:
            # オブジェクトが存在しない場合
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ("404", "NoSuchKey", "NotFound"):
                return False

            # その他の ClientError はエラーとして扱う
            raise StorageS3Error(f"exists failed: {e}") from e

        except BotoCoreError as e:
            raise StorageS3Error(f"exists failed: {e}") from e
    
    async def get_bytes(self, key: str) -> bytes:
        """
        指定キーのオブジェクトをバイト列として取得する。

        Args:
            key (str): 取得対象のオブジェクトキー（prefixを除いた相対パス）。

        Returns:
            bytes: オブジェクトデータ。

        Raises:
            StorageS3Error: 通信エラー、アクセス権エラー、ネットワーク障害など。
        """
        k = self._full_key(key)
        try:
            resp = await self._exist_client().get_object(Bucket=self.bucket, Key=k)
            body = resp["Body"]
            data = await body.read()
            body.close()
            return data
        except (BotoCoreError, ClientError) as e:
            raise StorageS3Error(f"get_bytes failed: {e}") from e

    async def upload_bytes(
        self,
        key: str,
        data: bytes,
        *,
        content_type: Optional[str] = None,
        extra_put_args: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """
        指定キーにバイト列データをアップロードする。

        Args:
            key (str): アップロード先のオブジェクトキー（prefixを除いた相対パス）。
            data (bytes): アップロードするデータ。
            content_type (Optional[str]): Content-Type ヘッダ（例: "text/plain"）。
            extra_put_args (Optional[Mapping[str, Any]]): put_object に渡す追加パラメータ。

        Raises:
            StorageS3Error: S3通信エラーや認証エラーなど。
        """
        k = self._full_key(key)
        put_args: dict[str, Any] = {"Bucket": self.bucket, "Key": k, "Body": data}
        if content_type:
            put_args["ContentType"] = content_type
        if extra_put_args:
            put_args.update(extra_put_args)

        try:
            await self._exist_client().put_object(**put_args)
        except (BotoCoreError, ClientError) as e:
            raise StorageS3Error(f"upload_bytes failed: {e}") from e

    # ---- helper ----
    def _full_key(self, key: str) -> str:
        """
        ベースプレフィックスを考慮した完全なS3キーを生成する。

        例:
            base_prefix="uploads/"
            key="image/test.png"
            → 結果: "uploads/image/test.png"

        Args:
            key (str): 相対パス形式のS3キー。

        Returns:
            str: ベースプレフィックスを含む完全なS3オブジェクトキー。
        """
        key = key.lstrip("/")
        if not self.base_prefix:
            return key
        return f"{self.base_prefix.rstrip('/')}/{key}"

    async def delete_object(self, key: str) -> None:
        """
        指定キーのオブジェクトを削除する。

        Args:
            key (str): 削除対象のオブジェクトキー（prefixを除いた相対パス）。

        Raises:
            StorageS3Error: 通信エラー、アクセス権エラー、ネットワーク障害など。
        """
        full_object_key = self._full_key(key)

        try:
            await self._exist_client().delete_object(
                Bucket=self.bucket,
                Key=full_object_key
            )
        except (BotoCoreError, ClientError) as e:
            raise StorageS3Error(f"delete_object failed: {e}") from e
        
    async def clear_cache(self, distribution_id: str, paths: Sequence[str]):
        """
        aioboto3 を使用して CloudFront のキャッシュ無効化を非同期で実行する。

        :param distribution_id: CloudFront ディストリビューション ID
        :param paths: 無効化したいパスのリスト（例：['/index.html', '/static/*']）
        """

        # CallerReference は一意である必要があるため timestamp を利用
        caller_reference = f"invalidation-{int(time.time())}"

        async with self._session.client("cloudfront") as client:
            response = await client.create_invalidation(
                DistributionId=distribution_id,
                InvalidationBatch={
                    "Paths": {
                        "Quantity": len(paths),
                        "Items": list(paths),
                    },
                    "CallerReference": caller_reference,
                },
            )

        return response