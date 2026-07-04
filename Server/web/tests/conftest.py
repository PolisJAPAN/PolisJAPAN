import os
import sys

# api パッケージを import 可能にする（tests/ は Server/web/ 直下）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# configs は import 時に APP_ENV で分岐するため、テストでは localhost を使う
os.environ.setdefault("APP_ENV", "localhost")
