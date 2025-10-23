from typing import Dict, Optional

import httpx
from fastapi import HTTPException


class WebLoaderHttpx:
    """
    httpx を使用してHTTP経由でページを取得するユーティリティクラス。

    高速で非同期なHTTPリクエストを行い、指定したURLからHTMLなどの
    テキストレスポンスを安全に取得する機能を提供する。
    """

    _default_timeout = httpx.Timeout(10.0, connect=5.0)
    """デフォルトの通信タイムアウト設定。全体10秒、接続5秒。"""
    
    _default_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,"
            "application/signed-exchange;v=b3;q=0.7"
        ),
        "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document",
    }
    """一般的なブラウザアクセスを模倣するHTTPヘッダーのデフォルトセット。"""
    
    _default_follow_redirects = True
    """HTTPリダイレクトを自動追跡するかどうかのデフォルト設定。"""

    @classmethod
    async def fetch_url(
        cls,
        url: str,
        timeout: Optional[httpx.Timeout] = None,
        headers: Optional[Dict[str, str]] = None,
        follow_redirects: Optional[bool] = None,
    ) -> str:
        """
        指定されたURLからページを非同期で取得する。

        `httpx.AsyncClient` を使用し、指定URLにGETリクエストを送信する。
        ヘッダーやタイムアウトなどのオプションを必要に応じて上書きできる。

        Args:
            url (str): 取得対象のURL。
            timeout (Optional[httpx.Timeout]): 通信タイムアウト設定。未指定時は `_default_timeout` を使用。
            headers (Optional[Dict[str, str]]): 追加または上書きするHTTPヘッダー。
            follow_redirects (Optional[bool]): リダイレクト追従の有無。未指定時は `_default_follow_redirects` を使用。

        Returns:
            str: レスポンス本文（HTMLやテキストなど）。

        Raises:
            HTTPException: 通信エラーまたはHTTPエラー発生時（status_code=502）。
        """
        
        timeout = timeout or cls._default_timeout
        # 渡された headers がある場合はデフォルトに上書きマージ
        merged_headers = cls._default_headers.copy()
        if headers:
            merged_headers.update(headers)

        follow_redirects = follow_redirects if follow_redirects is not None else cls._default_follow_redirects

        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                headers=merged_headers,
                follow_redirects=follow_redirects,
            ) as client:
                r = await client.get(url)
                r.raise_for_status()
                return r.text
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"URL の取得に失敗しました: {e}")