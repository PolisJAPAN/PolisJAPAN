
TINYINT_MAX         = 127
"""TINYINTの最大値"""
SMALLINT_MAX        = 32767
"""SMALLINTの最大値"""
MEDIUMINT_MAX   	= 8388607
"""MEDIUMINTの最大値"""
INT_MAX   	        = 2147483647
"""INTの最大値"""
BIGINT_MAX   	    = 9223372036854775807
"""BIGINT_MAXの最大値"""

TINYINT_U_MAX       = 255
"""TINYINT(符号なし)の最大値"""
SMALLINT_U_MAX      = 65535
"""SMALLINT(符号なし)の最大値"""
MEDIUMINT_U_MAX   	= 16777215
"""MEDIUMINT(符号なし)の最大値"""
INT_U_MAX   	    = 4294967295
"""TINT(符号なし)の最大値"""
BIGINT_U_MAX   	    = 18446744073709551615
"""BIGINT_MAX(符号なし)の最大値"""

SPLITTER = "###br###"

DATA_BACKEND = "mysql"
"""下書きデータの保存先: mysql | dynamodb。serverless環境のみdynamodbに上書きされる"""

PUBLISH_RETRY_LIMIT = 9
"""Polis投稿(batch-create)のリトライ上限。到達した下書きはFAILEDに隔離し後続を塞がない。
実測ではスケジュール1サイクル(15分)あたり3試行（EventBridge Schedulerのretry_policyは0だが、
Lambda非同期呼び出し既定の2回リトライが生きている）。9回=3サイクル≒30分強なので、
pol.is側の30分未満の一過性障害では健全な下書きを誤隔離しない。
誤隔離されても管理画面の再承認1クリックで復帰できる（アラームメールが失敗ごとに飛ぶ）"""
