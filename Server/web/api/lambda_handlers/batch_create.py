"""
テーマ作成バッチのLambdaエントリポイント。

EventBridge Scheduler から15分間隔で直接起動され、承認済み下書きを1件だけ処理する
（Lambdaの15分制限内に確実に収め、失敗時の影響を1件に限定するため。残件は次回起動で処理）。
起動経路がIAMで保護されるため、アクセスキー検証は行わない。
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
        processed = await service.publish_approved_drafts(limit=1)
        return {"is_success": True, "processed": processed}
    finally:
        s3 = getattr(service, "s3", None)
        if s3 is not None:
            await s3.close()


def handler(event, context):
    result = asyncio.run(_run())
    Logger.info(f"batch_create result: {result}")
    return result
