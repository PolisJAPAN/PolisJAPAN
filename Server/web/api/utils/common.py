from datetime import datetime

class Common():
    @classmethod
    def merge_lists(cls, base_list: list[dict], update_list: list[dict]) -> list[dict]:
        """
        2つの辞書リストをマージし、同一IDを持つ要素は上書きして結合する。

        Args:
            base_list (list[dict]): 元となるリスト。
            update_list (list[dict]): 追加・更新対象のリスト。
                同じ "id" を持つ要素がある場合、base_list 内の該当要素を上書きする。

        Returns:
            list[dict]: マージ後の新しいリスト。
        """
        # 元のリストを {id: dict} 形式に変換
        merged = {item["id"]: item.copy() for item in base_list}

        # 更新リストを反映（同一idなら上書き）
        for item in update_list:
            merged[item["id"]] = item.copy()

        # 辞書をリストに戻して返す
        return list(merged.values())
    
    @classmethod
    def sort_list(cls, list_data: list[dict], key: str, reverse: bool = False) -> list[dict]:
        """
        辞書リストを指定キーでソートする。

        int / float / datetime / 日付文字列 / 文字列 に対応しており、
        reverse=True の場合は降順でソートする。

        Args:
            list_data (list[dict]): ソート対象の辞書リスト。
            key (str): ソート基準となるキー名。
            reverse (bool, optional): 降順にソートする場合は True。デフォルトは False。

        Returns:
            list[dict]: ソート後の辞書リスト。
        """
        def sort_key(item):
            value = item.get(key, "")

            if value is None:
                return ""  # None対策

            # 1. 数値そのもの
            if isinstance(value, (int, float)):
                return value

            # 2. datetime型そのもの
            if isinstance(value, datetime):
                return value

            # 3. 数値文字列（例: "123", "3.14"）
            if isinstance(value, str):
                if value.replace(".", "", 1).isdigit():
                    try:
                        return float(value) if "." in value else int(value)
                    except ValueError:
                        pass

            # 4. 日付文字列（複数形式対応）
            if isinstance(value, str):
                for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(value, fmt)
                    except ValueError:
                        continue

            # 5. それ以外は文字列比較
            return str(value)

        return sorted(list_data, key=sort_key, reverse=reverse)