import os

ENVBIRONMENT_VALIABLES: dict = {
    "OPENAI_API_KEY" : os.environ.get("OPENAI_API_KEY", ""),
    "LANGCHAIN_TRACING_V2" : os.environ.get("LANGCHAIN_TRACING_V2", "true"),
    "LANGCHAIN_PROJECT" : "PolisJAPAN",
    "LANGCHAIN_ENDPOINT" : "https://api.smith.langchain.com",
    "LANGCHAIN_API_KEY" : os.environ.get("LANGCHAIN_API_KEY", ""),
    "AWS_ACCESS_KEY_ID" : os.environ.get("AWS_ACCESS_KEY_ID", ""),
    "AWS_SECRET_ACCESS_KEY" : os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
    "AWS_DEFAULT_REGION" : os.environ.get("AWS_DEFAULT_REGION", "ap-northeast-3"),
    "CLOUDFRONT_DISTRIBUTION" : os.environ.get("CLOUDFRONT_DISTRIBUTION", "E1VDGUET2Z2OBX"),
}
"""環境変数に自動セットする値（シークレットの実値はコードに置かず Server/web/.env で設定する）"""
