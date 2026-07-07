"""
serverless環境ではOPENAI_API_KEY等はLambdaの環境変数として直接注入されるため、
os.environへの再設定は不要。既存 configs/__init__.py のループ互換のため空dictを置く。
"""
ENVBIRONMENT_VALIABLES: dict[str, str] = {}
