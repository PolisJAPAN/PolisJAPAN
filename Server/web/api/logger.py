import os
import sys
from datetime import datetime
import api.configs as configs
from api.models.types import LogLevel
from api.utils.time import Time as Time

class Logger:
    """
    レベル別の着色済み整形ログを標準出力/標準エラーへ出力するユーティリティ。

    Notes:
        - `ENABLE_FLAGS` によりログレベル別の ON/OFF を制御可能。
    """
    
    # 1) HEXで定義（自由に変更）
    COLORS_HEX = {
        LogLevel.DEBUG:         "#74b5a6",  # Cyan系
        LogLevel.DEBUG_FOCUSED: "#46cab4",  # 強調したいシアン
        LogLevel.INFO:          "#ffffff",  # Green
        LogLevel.WARNING:       "#f1c40f",  # Yellow
        LogLevel.ERROR:         "#e74c3c",  # Red
        LogLevel.CRITICAL:      "#9b59b6",  # Magenta
    }

    # 2) 実際に使うANSI（起動時に _build_palette で上書き）
    COLORS = {}

    RESET = "\x1b[0m"
    ENABLE_FLAGS = configs.constants.LOG_ENABLE_FLAGS  # レベル別ON/OFF

    # ========== ロギング基盤 ==========
    @classmethod
    def _should_log(cls, level: int) -> bool:
        """
        指定レベルのログを出力すべきかを判定する。

        Args:
            level (int): ログレベル（`api.models.types.LogLevel` を想定）。

        Returns:
            bool: 出力可能なら True、抑制対象なら False。
        """
        return cls.ENABLE_FLAGS.get(level, True)

    @classmethod
    def _log(cls, level: int, label: str, message):
        """
        ログメッセージを整形し、レベルに応じて stdout/stderr に出力する。

        フォーマット:
            `[YYYY-MM-DD HH:MM:SS] [LABEL] message`

        Args:
            level (int): ログレベル（`LogLevel` を想定）。
            label (str): ログ行に付与するラベル（例: "INFO", "ERROR"）。
            message (Any): 出力するメッセージ（`str` 化可能なオブジェクト）。

        Returns:
            None
        """
        
        if not cls._should_log(level):
            return
        
        color = cls.COLORS.get(level, "")
        now = Time.to_mysql_datetime_str(Time.now())
        reset = cls.RESET if color else ""
        formatted = f"{color}[{now}] [{label}] {message}{reset}"
        stream = sys.stderr if level >= LogLevel.ERROR else sys.stdout
        print(formatted, file=stream)

    # ========== レベル別API ==========
    @classmethod
    def debug(cls, message):
        """
        デバッグレベルのログを出力する。

        Args:
            message (Any): 出力メッセージ。

        Returns:
            None
        """
        cls._log(LogLevel.DEBUG, "DEBUG", message)

    @classmethod
    def debug_focused(cls, message):
        """
        フォーカスしたいデバッグログ（強調表示）を出力する。

        Args:
            message (Any): 出力メッセージ。

        Returns:
            None
        """
        cls._log(LogLevel.DEBUG_FOCUSED, "DEBUG*", message)  # ← 修正

    @classmethod
    def info(cls, message):
        """
        インフォレベルのログを出力する。

        Args:
            message (Any): 出力メッセージ。

        Returns:
            None
        """
        cls._log(LogLevel.INFO, "INFO", message)

    @classmethod
    def warning(cls, message):
        """
        警告レベルのログを出力する。

        Args:
            message (Any): 出力メッセージ。

        Returns:
            None
        """
        cls._log(LogLevel.WARNING, "WARNING", message)

    @classmethod
    def error(cls, message):
        """
        エラーレベルのログを出力する（stderr）。

        Args:
            message (Any): 出力メッセージ。

        Returns:
            None
        """
        cls._log(LogLevel.ERROR, "ERROR", message)

    @classmethod
    def critical(cls, message):
        """
        重大レベルのログを出力する（stderr）。

        Args:
            message (Any): 出力メッセージ。

        Returns:
            None
        """
        cls._log(LogLevel.CRITICAL, "CRITICAL", message)
    
    
    
    
    # ========== カラーパレット管理 ==========
    class ColorPaletteManager:
        """
        端末の色表現能力を判定し、HEXカラーを適切な ANSI エスケープに変換する管理クラス。
        
        Notes:
            - `COLORS_HEX` に #RRGGBB 形式で色を定義。
            - 起動時（クラスロード時）に `ColorPaletteManager._build_palette()` を用いて
            - 実行環境の能力に合わせた ANSI エスケープ表現へ変換し、`COLORS` に保存する。
        """
        @staticmethod
        def _supports_truecolor() -> bool:
            """
            端末が TrueColor（24bitカラー）をサポートしているかを判定する。

            Returns:
                bool: TrueColor 対応なら True、それ以外は False。
            """
            # 代表的な判定。必要なら環境に合わせて拡張
            colorterm = os.environ.get("COLORTERM", "").lower()
            term = os.environ.get("TERM", "").lower()
            return ("truecolor" in colorterm) or ("24bit" in colorterm) or ("direct" in term)

        @staticmethod
        def _hex_to_rgb(hexstr: str) -> tuple[int, int, int]:
            """
            `#RRGGBB` または `#RGB` を (R, G, B) の整数タプルへ変換する。

            Args:
                hexstr (str): 先頭に `#` を含む HEX カラー文字列。

            Returns:
                tuple[int, int, int]: (R, G, B) 各 0–255 の整数値。
            """
            s = hexstr.lstrip("#")
            if len(s) == 3:
                s = "".join(ch * 2 for ch in s)  # #abc -> #aabbcc
            r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
            return r, g, b

        @staticmethod
        def _rgb_to_ansi_truecolor(r: int, g: int, b: int, bg: bool = False) -> str:
            """
            RGB 値を TrueColor(24bit) の ANSI エスケープ文字列に変換する。

            Args:
                r (int): 赤（0–255）。
                g (int): 緑（0–255）。
                b (int): 青（0–255）。
                bg (bool): 背景色かどうか。True の場合は背景色。既定 False（前景色）。

            Returns:
                str: ANSI エスケープシーケンス（例: `\\x1b[38;2;R;G;B m`）。
            """
            return f"\x1b[{48 if bg else 38};2;{r};{g};{b}m"

        @staticmethod
        def _rgb_to_ansi_256(r: int, g: int, b: int, bg: bool = False) -> str:
            """
            RGB 値を 256 色の ANSI エスケープ文字列に変換する。

            近似 6x6x6 カラーマップ（16–231）へ量子化してマッピングする。

            Args:
                r (int): 赤（0–255）。
                g (int): 緑（0–255）。
                b (int): 青（0–255）。
                bg (bool): 背景色かどうか。True の場合は背景色。既定 False（前景色）。

            Returns:
                str: ANSI エスケープシーケンス（例: `\\x1b[38;5;{n}m`）。
            """
            
            # 256色のうちカラーマップ(16–231)へ丸め
            def quant(x: int) -> int:
                # 0–255 -> 0–5
                return int(round(x / 255 * 5))
            ri, gi, bi = quant(r), quant(g), quant(b)
            idx = 16 + 36 * ri + 6 * gi + bi
            return f"\x1b[{48 if bg else 38};5;{idx}m"

        @classmethod
        def _build_palette(cls, COLORS_HEX:dict) -> dict:
            """
            HEX カラーパレットを実行環境に応じた ANSI カラーへ変換して返す。

            TrueColor 対応端末では 24bit（`38;2`）を、非対応端末では 256 色（`38;5`）を使用する。

            Args:
                COLORS_HEX (dict): ログレベルをキー、HEX 文字列を値とする辞書。

            Returns:
                dict: ログレベルをキー、ANSI エスケープ文字列を値とする辞書。
            """
            use_truecolor = cls._supports_truecolor()
            built = {}
            for lvl, hexstr in COLORS_HEX.items():
                r, g, b = cls._hex_to_rgb(hexstr)
                if use_truecolor:
                    built[lvl] = cls._rgb_to_ansi_truecolor(r, g, b, bg=False)
                else:
                    built[lvl] = cls._rgb_to_ansi_256(r, g, b, bg=False)
            return built

    # 起動時に一度だけパレット構築
    COLORS = ColorPaletteManager._build_palette(COLORS_HEX)
