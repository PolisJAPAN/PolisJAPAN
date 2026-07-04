"""
serverless環境のDB設定。DynamoDB移行完了後は未使用となるが、
既存コード（drivers/database.py）のimport互換のため環境変数から読む。
"""
import os

DB_HOST = os.environ.get("DB_HOST", "")
DB_NAME = os.environ.get("DB_NAME", "")
DB_USER = os.environ.get("DB_USER", "")
DB_PORT = os.environ.get("DB_PORT", "3306")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")
