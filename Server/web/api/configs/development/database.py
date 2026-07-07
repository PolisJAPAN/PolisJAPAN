# データベースの接続情報を定義
import os

DB_HOST = os.environ.get("DB_HOST", "db")
"""データベースホスト"""

DB_NAME = os.environ.get("DB_NAME", "app_db")
"""データベース名"""

DB_USER = os.environ.get("DB_USER", "app_user")
"""データユーザー名"""

DB_PORT = os.environ.get("DB_PORT", "3306")
"""データベースポート番号"""

DB_PASSWORD = os.environ.get("DB_PASSWORD", "app_password")
"""データベースパスワード（docker-compose.yml の MYSQL_PASSWORD と一致させる）"""
