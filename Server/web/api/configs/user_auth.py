
from typing import Optional, Union
from fastapi import Header

USER_AUTH_EXCLUDE_LIST: dict[str, Union[str, list]] = {
    "admin" : "ALL",
    "batch" : "ALL",
    "theme" : "ALL",
    "user" : [
        "mail_check",
        "create",
        "login",   
    ]
}
"""
ユーザー認証通信をバイパス（除外）するAPI一覧。

構造:
    - キー: コントローラー名（例: "user", "admin"）
    - 値:
        - "ALL" : 該当コントローラー配下の全APIを除外
        - list[str]: 特定のAPI名のみ除外対象とする

例:
    USER_AUTH_EXCLUDE_LIST = {
        "user": ["login", "create"],
        "admin": "ALL"
    }
"""

def is_user_auth_api(controller_name, api_name):
    """
    ユーザー認証通信を実施するAPIかどうかを判定する。

    除外リスト（USER_AUTH_EXCLUDE_LIST）に該当しないAPIは認証対象とする。

    Args:
        controller_name (str): コントローラー名（例: "user", "admin"）
        api_name (str): API名（例: "login", "update"）

    Returns:
        bool: True の場合は認証が必要なAPI、False の場合は除外（認証不要）。
    """
    
    # コントローラー名が除外リストに含まれていない場合
    if controller_name not in USER_AUTH_EXCLUDE_LIST:
        return True
    
    # コントローラー名が一括除外の場合
    if  type(USER_AUTH_EXCLUDE_LIST[controller_name]) is str and USER_AUTH_EXCLUDE_LIST[controller_name] == "ALL":
        return False
    
    # コントローラー名が除外リストに含まれる場合
    if type(USER_AUTH_EXCLUDE_LIST[controller_name]) is list and api_name in USER_AUTH_EXCLUDE_LIST[controller_name]:
        return False
    
    # その他、条件に合致しない場合は認証通信とする
    return True
