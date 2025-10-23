import hashlib
from ipaddress import ip_address, ip_network
from typing import Iterable

from api.configs import constants

class Security():
    """
    セキュリティ関連の汎用処理を管理するクラス
    """
    
    @classmethod
    def hash_password(cls, password: str) -> str:
        """
        パスワードをサーバー側ソルトと結合し、SHA256でハッシュ化する。

        Args:
            password (str): ハッシュ化対象のプレーンパスワード。

        Returns:
            str: ソルト付きSHA256ハッシュの16進文字列。
        """
        
        # ソルト＋パスワードを結合
        salted = constants.ENCRYPT_SALT + password
        # SHA256でハッシュ化
        hash_obj = hashlib.sha256(salted.encode('utf-8'))
        return hash_obj.hexdigest()

    @classmethod
    def verify_password(cls, plain_password: str, hashed_password: str) -> bool:
        """
        入力パスワードをハッシュ化し、保存済みハッシュと一致するかを検証する。

        Args:
            plain_password (str): 入力された生パスワード。
            hashed_password (str): DBなどに保存されたハッシュ済みパスワード。

        Returns:
            bool: 一致すれば True、不一致なら False。
        """
        
        return cls.hash_password(plain_password) == hashed_password
    
    @classmethod
    def is_allowed_ip(cls, remote_ip: str, allowlist: Iterable[str]) -> bool:
        """
        指定されたIPが許可リスト内に含まれているかを判定
        CIDR表記・単一IPどちらも対応

        Args:
            remote_ip (str): 実際のアクセス元IP（例: "203.0.113.5"）
            allowlist (Iterable[str]): 許可するIPまたはCIDR範囲のリスト

        Returns:
            bool: 許可されていれば True、そうでなければ False
        """
        try:
            client_ip = ip_address(remote_ip)
        except ValueError:
            # IPとして不正な形式
            return False

        for allowed in allowlist:
            try:
                if client_ip in ip_network(allowed, strict=False):
                    return True
            except ValueError:
                # CIDRとして不正ならスキップ
                continue

        return False