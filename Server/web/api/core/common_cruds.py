from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy import and_
from sqlalchemy import delete as sqlalchemy_delete
from sqlalchemy import or_, select
from sqlalchemy import update as sqlalchemy_update
from sqlalchemy.ext.asyncio import AsyncSession

from api.utils.drivers.database import Base
from api.utils.time import Time as Time

ModelType = TypeVar("ModelType", bound=Base)
"""CRUD対象となるSQLAlchemyモデルの型変数。Base（Declarative Base）として扱う"""

class CommonCruds(Generic[ModelType]):
    """
    任意のモデルに対する非同期CRUD操作を共通提供するクラス。

    継承先で `model` に対象のORMモデル（Declarativeクラス）を設定することで、
    同一インターフェースのCRUDを利用できる。

    Attributes:
        model (Type[ModelType]): 対象とするSQLAlchemyモデルクラス。継承先で上書きする。
    """
    
    model: Type[ModelType]  # 継承先で上書き

    ############################### 
    # 内部基幹メソッド 
    ############################### 

    @classmethod
    async def _insert(cls, db: AsyncSession, obj_in: dict) -> ModelType:
        """
        1件INSERTを実行する。

        未設定の場合は `status=1`, `create_date`, `update_date` を自動補完する。

        Args:
            db (AsyncSession): 非同期DBセッション。
            obj_in (dict): 挿入するカラム名→値の辞書。

        Returns:
            ModelType: 追加されたORMオブジェクト（flush済み）。
        """
        
        if "status" not in obj_in:
            obj_in["status"] = 1
            
        if "create_date" not in obj_in:
            obj_in["create_date"] = Time.now()
            
        if "update_date" not in obj_in:
            obj_in["update_date"] = Time.now()
        
        obj = cls.model(**obj_in)
        db.add(obj)
        await db.flush()
        return obj
    
    @classmethod
    async def _bulk_insert(cls, db: AsyncSession, objs_in: List[dict]) -> List[ModelType]:
        """
        複数レコードを一括INSERTする。

        各レコードに対し、未設定の `status=1`, `create_date`, `update_date` を自動補完する。

        Args:
            db (AsyncSession): 非同期DBセッション。
            objs_in (List[dict]): 複数レコードのカラム名→値の辞書リスト。

        Returns:
            List[ModelType]: 追加されたORMオブジェクトのリスト（flush済み）。
        """
        
        objs_in_temp : List[dict] = []
        for obj_in in objs_in:
            if "status" not in obj_in:
                obj_in["status"] = 1
                
            if "create_date" not in obj_in:
                obj_in["create_date"] = Time.now()
                
            if "update_date" not in obj_in:
                obj_in["update_date"] = Time.now()
            
            objs_in_temp.append(obj_in)
        
        objs = [cls.model(**obj) for obj in objs_in_temp]
        db.add_all(objs)
        await db.flush()
        return objs
    
    @classmethod
    async def _select_all(cls, db: AsyncSession) -> List[ModelType]:
        """
        テーブルの全レコードを取得する（status条件なし）。

        Args:
            db (AsyncSession): 非同期DBセッション。

        Returns:
            List[ModelType]: 全件のORMオブジェクト。
        """
        where = {"status" : 1}
        filters = cls.parse_where(cls.model, where)
        statement = select(cls.model)
        if filters:
            statement = statement.where(*filters)
        result = await db.execute(select(cls.model))
        return list(result.scalars().all())
    
    @classmethod
    async def _select_list(cls, db: AsyncSession, where: Dict[str, Any]) -> List[ModelType]:
        """
        WHERE句を指定して複数件を取得する。

        `status` が未指定の場合、既定で `status=1` を付与する。

        Args:
            db (AsyncSession): 非同期DBセッション。
            where (Dict[str, Any]): 条件辞書。

        Returns:
            List[ModelType]: 該当するORMオブジェクトのリスト。
        """
        
        if "status" not in where:
            where["status"] = 1
        
        filters = cls.parse_where(cls.model, where)
        statement = select(cls.model)
        if filters:
            statement = statement.where(*filters)
        result = await db.execute(statement)
        return list(result.scalars().all())

    @classmethod
    async def _select(cls, db: AsyncSession, where: Dict[str, Any]) -> Optional[ModelType]:
        """
        WHERE句を指定して1件を取得する。

        `status` が未指定の場合、既定で `status=1` を付与する。

        Args:
            db (AsyncSession): 非同期DBセッション。
            where (Dict[str, Any]): 絞り込み用の条件辞書

        Returns:
            Optional[ModelType]: 最初に一致したオブジェクト。存在しなければNone。
        """
        
        if "status" not in where:
            where["status"] = 1
        
        filters = cls.parse_where(cls.model, where)
        statement = select(cls.model)
        if filters:
            statement = statement.where(*filters)
        result = await db.execute(statement)
        return result.scalars().first()

    @classmethod
    async def _update(cls, db: AsyncSession, where: Dict[str, Any], set: dict) -> int:
        """
        WHERE句とSET内容を指定して複数件を更新する。

        `update_date` が未指定の場合、現在時刻を自動付与する。

        Args:
            db (AsyncSession): 非同期DBセッション。
            where (Dict[str, Any]): 更新対象の条件辞書。
            set (dict): 更新するカラム名→値の辞書。

        Returns:
            int: 影響行数（rowcount）。
        """
            
        if "update_date" not in set:
            set["update_date"] = Time.now()
        
        filters = cls.parse_where(cls.model, where)
        statement = sqlalchemy_update(cls.model).where(*filters).values(**set)
        result = await db.execute(statement)
        return result.rowcount

    @classmethod
    async def _delete(cls, db: AsyncSession, where: Dict[str, Any]) -> int:
        """
        WHERE句を指定して複数件を論理削除する。

        実装は UPDATE により `status=0`, `update_date` を更新する。

        Args:
            db (AsyncSession): 非同期DBセッション。
            where (Dict[str, Any]): 削除対象の条件辞書。

        Returns:
            int: 影響行数（rowcount）。
        """
        
        set = {
            "status" : 0,
            "update_date" : Time.now(),
        }
        
        filters = cls.parse_where(cls.model, where)
        statement = sqlalchemy_update(cls.model).where(*filters).values(**set)
        result = await db.execute(statement)
        
        return result.rowcount
    
    @classmethod
    async def _physical_delete(cls, db: AsyncSession, where: Dict[str, Any]) -> int:
        """
        WHERE句を指定して複数件を物理削除する。

        通常は使用せず、完全削除が必要なケースのみで用いる。

        Args:
            db (AsyncSession): 非同期DBセッション。
            where (Dict[str, Any]): 削除対象の条件辞書。

        Returns:
            int: 影響行数（rowcount）。
        """
        filters = cls.parse_where(cls.model, where)
        statement = sqlalchemy_delete(cls.model).where(*filters)
        result = await db.execute(statement)
        return result.rowcount


    ############################### 
    # 内部汎用メソッド 
    ############################### 

    @classmethod
    def parse_where(cls, model, where: Dict[str, Any]):
        """
        条件辞書（where）からSQLAlchemyフィルタ式のリストを生成する。

        サポート仕様:
            - 論理和: {"OR": [cond1, cond2, ...]} 各condはANDで結合され、外側でOR結合。
            - キー側演算子: "name__like" のように "__" で区切り、右側を演算子として解釈。
            - 値側演算子: {"name": ["like", "%foo%"]} のように [op, value] 形式。
            - IN句: {"id": [1, 2, 3]} や set/list による IN。
            - 単純一致: {"status": 1} は `col == 1`。

        Args:
            model: SQLAlchemyのDeclarativeモデル（カラム属性を持つ）。
            where (Dict[str, Any]): 条件辞書。

        Returns:
            list: SQLAlchemyのバイナリ式（ColumnElement）のリスト。
        """
        
        filters = []
        for key, value in where.items():
            if key == "OR" and isinstance(value, list):
                filters.append(or_(*[and_(*cls.parse_where(model, sub)) for sub in value]))
                continue

            # keyから演算子分離(既存方式) 例: "name__like"
            if "__" in key:
                col_name, op = key.split("__", 1)
                col = getattr(model, col_name, None)
                if col is None:
                    continue
                filters.append(cls.build_expr(col, op, value))
                continue

            # 値側がタプルか判定
            col = getattr(model, key, None)
            if col is None:
                continue
            if isinstance(value, (tuple, list)) and len(value) >= 2 and isinstance(value[0], str):
                op = value[0]
                val = value[1]
                filters.append(cls.build_expr(col, op, val))
            elif isinstance(value, (list, set)) and not isinstance(value, str):
                # 単純IN
                filters.append(col.in_(value))
            else:
                filters.append(col == value)
        return filters

    @classmethod
    def build_expr(cls, col, op, value):
        """
        カラム・演算子・値からSQLAlchemyの比較式を生成する。

        サポート演算子（大文字小文字は不問）:
            - 比較: "=", "eq", "!=", "ne", "<>", ">", ">=", "<", "<="
            - 文字列: "like", "ilike"
            - 集合: "in", "not in", "not"（not は IN/≠ を状況に応じて選択）

        Args:
            col: SQLAlchemyのカラム式。
            op (str): 演算子。
            value: 比較対象の値。

        Returns:
            Any: SQLAlchemyの式（BinaryExpression など）。

        Raises:
            ValueError: 未対応の演算子が指定された場合。
        """
        
        op = op.lower()
        if op in ("=", "eq"):
            return col == value
        elif op in ("!=", "ne", "<>"):
            return col != value
        elif op == "not":
            if isinstance(value, (list, tuple, set)):
                return ~col.in_(value)
            else:
                return col != value
        elif op == "not in":
            return ~col.in_(value)
        elif op == "in":
            return col.in_(value)
        elif op == "like":
            return col.like(value)
        elif op == "ilike":
            return col.ilike(value)
        elif op == ">":
            return col > value
        elif op == ">=":
            return col >= value
        elif op == "<":
            return col < value
        elif op == "<=":
            return col <= value
        else:
            raise ValueError(f"未対応の演算子: {op}")

    
    ############################### 
    # 外部参照メソッド 
    ############################### 
    
    @classmethod
    async def select_by_id(cls, db: AsyncSession, id: int) -> Optional[ModelType]:
        """
        主キーIDを指定して、有効（status=1）な1件を取得する。

        Args:
            db (AsyncSession): 非同期DBセッション。
            id (int): 主キーID。

        Returns:
            Optional[ModelType]: 一致したオブジェクト。存在しなければNone。
        """
        
        where = {
            "id" : id,
            "status" : 1
        }
        
        return await cls._select(db, where)
    
    @classmethod
    async def select_all(cls, db: AsyncSession) -> List[ModelType]:
        """
        有効（status=1）な全件を取得する。

        Args:
            db (AsyncSession): 非同期DBセッション。

        Returns:
            List[ModelType]: 取得結果のリスト。
        """
        
        # 有効なレコードのみ全件取得
        where = {
            "status" : 1
        }
        
        return await cls._select_list(db, where)
    
    @classmethod
    async def select_list_by_t_user_id(cls, db: AsyncSession, t_user_id: int) -> List[ModelType]:
        """
        ユーザーIDを指定し、有効（status=1）な複数件を取得する。

        Args:
            db (AsyncSession): 非同期DBセッション。
            t_user_id (int): ユーザーID。

        Returns:
            List[ModelType]: 取得結果のリスト。
        """
        
        where = {
            "t_user_id" : t_user_id,
            "status" : 1
        }
        
        return await cls._select_list(db, where)
    
    @classmethod
    async def select_by_t_user_id(cls, db: AsyncSession, t_user_id: int) -> Optional[ModelType]:
        """
        ユーザーIDを指定し、有効（status=1）な1件を取得する。

        Args:
            db (AsyncSession): 非同期DBセッション。
            t_user_id (int): ユーザーID。

        Returns:
            Optional[ModelType]: 一致したオブジェクト。存在しなければNone。
        """
        
        where = {
            "t_user_id" : t_user_id,
            "status" : 1
        }
        
        return await cls._select(db, where)
    
    @classmethod
    async def delete_by_id(cls, db: AsyncSession, id: int) -> int:
        """
        主キーIDを指定して論理削除（status=0, update_date更新）を行う。

        Args:
            db (AsyncSession): 非同期DBセッション。
            id (int): 主キーID。

        Returns:
            int: 影響行数（rowcount）。
        """
        
        where = {
            "id" : id,
            "status" : 1
        }
        
        return await cls._delete(db, where)
    
    @classmethod
    async def update(cls, db: AsyncSession, target: ModelType, set: dict) -> Optional[ModelType]:
        """
        1件のオブジェクトを更新する（DB更新後、ローカルインスタンスにも反映）。

        Args:
            db (AsyncSession): 非同期DBセッション。
            target (ModelType): 更新対象の既存オブジェクト（id必須）。
            set (dict): 更新するカラム名→値の辞書。

        Returns:
            Optional[ModelType]: 更新後のオブジェクト（ローカル反映済み）。対象が無い場合はNone。
        """

        # idで WHERE 句を構築
        where = {"id" : target.id}

        # 更新処理を実行
        result = await cls._update(db, where, set)
        
        # ローカルにも反映
        for key, value in set.items():
            setattr(target, key, value)

        return target

    @classmethod
    async def _update_list(cls, db: AsyncSession, target_list: List[ModelType], set: dict) -> List[ModelType]:
        """
        複数オブジェクトを一括更新（DB・ローカル両方）する。

        内部では `id IN (...)` の更新を行うため、対象件数が極端に多い場合は
        トランザクション設計・バッチサイズ等に留意すること。

        Args:
            db (AsyncSession): 非同期DBセッション。
            target_list (List[ModelType]): 更新対象のオブジェクト一覧（id必須）。
            set (dict): 更新するカラム名→値の辞書。

        Returns:
            List[ModelType]: 更新後のオブジェクト一覧（ローカル反映済み）。空入力時は空リスト。
        """

        if not target_list:
            return []

        # idで WHERE 句を構築
        ids = [target.id for target in target_list]
        where = {"id" : ids}

        # 更新処理を実行
        result = await cls._update(db, where, set)

        # ローカルに反映
        for target in target_list:
            for key, value in set.items():
                setattr(target, key, value)

        return target_list
