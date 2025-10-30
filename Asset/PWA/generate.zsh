#!/bin/zsh
# --------------------------------------------
# PWAアセット自動生成スクリプト
# 使用: ./generate_pwa_assets.zsh
# --------------------------------------------

# エラー発生時は即停止
set -e

# プロジェクトルートに移動（スクリプト実行位置に依存しないように）
cd "$(dirname "$0")"

# 入力画像・出力ディレクトリ・設定ファイルのパスを定義
INPUT_IMAGE="../../Client/public_html_app/images/polis-icon.png"
OUTPUT_DIR="./output"
MANIFEST_PATH="../../Client/public_html_app/manifest.json"
INDEX_PATH="./index.html"

# 背景色やパディングを統一管理
BACKGROUND_COLOR="#FFFFFF"
PADDING="16%"

# 実行ログを表示
echo "=== Generating PWA assets... ==="

# 実行コマンド
npx pwa-asset-generator \
    "$INPUT_IMAGE" \
    "$OUTPUT_DIR" \
    --background "$BACKGROUND_COLOR" \
    --padding "$PADDING" \
    --manifest "$MANIFEST_PATH" \
    --index "$INDEX_PATH" \
    --dark-mode

echo "✅ PWA assets successfully generated at $OUTPUT_DIR"
