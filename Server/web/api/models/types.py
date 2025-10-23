from enum import Enum

class PostStatus(Enum):
    """
        ポスト状態を管理するステート
        0 : 生成済
        1 : 承認済 
        2 : 投稿済 
        101 : 却下済
    """
    SUGGESTED = 0
    GENERATED = 1
    APPROVED = 2
    POSTED = 3
    REJECTED = 101

class LogLevel:
    """
        ログレベルを管理するステート
    """
    DEBUG = 100
    DEBUG_FOCUSED = 200
    INFO = 300
    WARNING = 400
    ERROR = 500
    CRITICAL = 600