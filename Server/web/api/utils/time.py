from datetime import datetime, tzinfo
from typing import Optional

import pytz

class Time():
    """
    日時操作を統一的に扱うユーティリティクラス。

    主に Asia/Tokyo タイムゾーンを基準とし、ISO形式・MySQL形式・
    ファイル名形式など、用途に応じたフォーマット変換メソッドを提供する。

    全メソッドはクラスメソッドとして実装されており、インスタンス化せずに利用可能。
    """
    
    # ------------------------------
    # 定数
    # ------------------------------
    TZ_TOKYO = pytz.timezone("Asia/Tokyo")
    """Asia/Tokyo タイムゾーンオブジェクト。"""
    
    MYSQL_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    """MySQL DATETIME 形式（例: 2025-01-15 13:45:30）。"""
    
    FILENAME_FORMAT = "%Y%m%d_%H:%M:%S"
    """ファイル名で使用可能な日時形式（例: 20250115_134530）。"""
    
    DATE_FORMAT = "%Y-%m-%d"
    """年月日のみを表す日付フォーマット（例: 2025-01-15）。"""

    @classmethod
    def now(cls) -> datetime:
        """
        現在時刻を Asia/Tokyo タイムゾーンで取得する。

        Returns:
            datetime: タイムゾーン付きの現在日時。
        """
        return datetime.now(cls.TZ_TOKYO)

    @classmethod
    def to_isoformat(cls, datetime_instance: datetime) -> str:
        """
        datetime を ISO8601 フォーマット文字列に変換する。

        Args:
            datetime_instance (datetime): 対象の日時。

        Returns:
            str: ISO8601形式文字列（例: "2025-01-15T13:45:30+09:00"）。
        """
        return datetime_instance.isoformat()

    @classmethod
    def to_mysql_datetime_str(cls, datetime_instance: datetime) -> str:
        """
        datetime を MySQL DATETIME 形式文字列に変換する。

        フォーマット: `%Y-%m-%d %H:%M:%S`

        Args:
            datetime_instance (datetime): 対象の日時。

        Returns:
            str: MySQL互換の日時文字列。
        """
        return datetime_instance.strftime(cls.MYSQL_DATETIME_FORMAT)
    
    @classmethod
    def to_filename_format(cls, datetime_instance: datetime) -> str:
        """
        datetime をファイル名として使用できる安全な形式に変換する。

        フォーマット: `%Y%m%d_%H:%M:%S`

        Args:
            datetime_instance (datetime): 対象の日時。

        Returns:
            str: ファイル名で使用できる日時文字列。
        """
        return datetime_instance.strftime(cls.FILENAME_FORMAT)
    
    @classmethod
    def to_date_format(cls, datetime_instance: datetime) -> str:
        """
        datetime を日付（年月日）形式の文字列に変換する。

        Args:
            datetime_instance (datetime): 対象の日時。

        Returns:
            str: `YYYY-MM-DD` 形式の日付文字列。
        """
        return datetime_instance.strftime(cls.DATE_FORMAT)

    @classmethod
    def from_isoformat(cls, iso_str: str) -> datetime:
        """
        ISOフォーマット文字列から datetime に変換する。

        Args:
            iso_str (str): ISO8601形式の日時文字列。

        Returns:
            datetime: 対応する datetime オブジェクト。
        """
        return datetime.fromisoformat(iso_str)

    @classmethod
    def from_mysql_datetime_str(cls, mysql_str: str, tzinfo: Optional[tzinfo]=None) -> datetime:
        """
        MySQL DATETIME 形式の文字列から datetime に変換する。

        文字列にはタイムゾーン情報が含まれないため、
        必要に応じて `tzinfo` を指定して補う。

        Args:
            mysql_str (str): MySQL DATETIME形式文字列（例: "2025-01-15 13:45:30"）。
            tzinfo (Optional[tzinfo]): タイムゾーン情報。省略時はNone（naive datetime）。

        Returns:
            datetime: タイムゾーンを含む、または含まない datetime オブジェクト。
        """
        datetime_instance = datetime.strptime(mysql_str, cls.MYSQL_DATETIME_FORMAT)
        if tzinfo:
            datetime_instance = datetime_instance.replace(tzinfo=tzinfo)
        return datetime_instance