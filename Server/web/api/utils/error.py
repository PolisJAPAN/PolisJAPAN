import hashlib
import secrets

from api.utils.time import Time

class Error():
    """
    アプリケーション共通のエラー関連ユーティリティクラス。
    """
    
    @staticmethod
    def generate_trace_id() -> str:
        """
        一意なトレースID（trace-id）を生成する。

        現在時刻（マイクロ秒単位）とランダムソルトを組み合わせてSHA-256でハッシュ化し、
        さらにランダム値を付与して衝突リスクを極小化した一意IDを返す。

        Returns:
            str: 生成されたトレースID（形式: `<16桁ハッシュ>-<32桁ランダム文字列>`）。
        """
        
        # 現在時刻をISOフォーマット文字列で取得
        now_str = Time.now().isoformat(timespec="microseconds")
        # 追加でランダム値も組み合わせてより一意性を高める
        salt = secrets.token_hex(8)  # 16文字相当の乱数をソルトとして付与
        hash_src = f"{now_str}-{salt}"
        # SHA256でハッシュ化（先頭16文字だけ利用：短縮も可）
        time_hash = hashlib.sha256(hash_src.encode("utf-8")).hexdigest()[:16]
        # ランダム32文字
        random_str = secrets.token_hex(16)
        # trace-id生成
        return f"{time_hash}-{random_str}"