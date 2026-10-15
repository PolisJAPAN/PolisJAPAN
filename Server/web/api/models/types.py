from enum import Enum

class PostStatus(Enum):
    """
        ポスト状態を管理するステート
        0 : 提案済 (SUGGESTED)
        1 : 生成済 (GENERATED)
        2 : 承認済 (APPROVED)
        3 : 投稿済 (POSTED)
        101 : 却下済 (REJECTED)
        102 : 投稿失敗 (FAILED。リトライ上限到達で隔離。再承認で再投稿可能)
    """
    SUGGESTED = 0
    GENERATED = 1
    APPROVED = 2
    POSTED = 3
    REJECTED = 101
    FAILED = 102

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