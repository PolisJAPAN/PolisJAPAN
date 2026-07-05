"""
投票情報自動更新バッチのLambdaエントリポイント。

EventBridge Scheduler から5分間隔で直接起動される。
起動経路がIAMで保護されるため、HTTP経由(routers/batch.py)と異なりアクセスキー検証は行わない。
APP_ENV=serverless 前提（DraftStoreはDynamoDB、RDB接続なし）。
"""
import asyncio

from api.logger import Logger
from api.repositories import create_draft_store
from api.services.batch import BatchService


async def _run() -> dict:
    service = BatchService()
    await service.initialize_utils()
    service.db_session = None
    service.draft_store = create_draft_store(None)
    try:
        updated = await service.update_themes()
        return {"is_success": True, "updated": updated}
    finally:
        s3 = getattr(service, "s3", None)
        if s3 is not None:
            await s3.close()


def handler(event, context):
    result = asyncio.run(_run())
    Logger.info(f"batch_update result: {result}")
    return result
