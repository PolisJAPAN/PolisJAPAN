
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

PUBLISH_RETRY_LIMIT = 5
"""Polis投稿(batch-create)のリトライ上限。到達した下書きはFAILEDに隔離し後続を塞がない。
Lambdaの非同期リトライ(1サイクル3試行)を踏まえ、2サイクル目まで一過性エラーを許容する値"""
