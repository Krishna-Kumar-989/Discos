import contextvars
import logging
import datetime
from typing import Any, Dict, List, Optional, Tuple, Type, Union
from contextlib import asynccontextmanager

from DataDb.base import BaseDatabaseProvider
from DataDb.models.base import BaseEntity

logger = logging.getLogger("DataDb.sql")

class SQLProvider(BaseDatabaseProvider):
    """
    SQL Database Provider implementation using SQLAlchemy Core.
    Supports SQLite, PostgreSQL, and MySQL.
    """
    
    def __init__(self, connection_url: str, required_driver: str):
        self.connection_url = connection_url
        self.required_driver = required_driver
        self.engine = None
        self.session_maker = None
        self._session_var = contextvars.ContextVar("sql_session", default=None)
        
        try:
            import sqlalchemy as sa
            from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
        except ImportError:
            raise ImportError("SQLAlchemy is not installed. Please run 'pip install SQLAlchemy'.")
            
        try:
            if required_driver == "aiosqlite":
                import aiosqlite
            elif required_driver == "asyncpg":
                import asyncpg
            elif required_driver == "aiomysql":
                import aiomysql
        except ImportError:
            raise ImportError(f"Database driver '{required_driver}' is not installed. Please pip install it.")
            
        self._sa = sa
        self._metadata = sa.MetaData()
        self._table_cache = {}

    async def connect(self) -> None:
        if self.engine is None:
            try:
                from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
                self.engine = create_async_engine(self.connection_url, echo=False, future=True)
                self.session_maker = async_sessionmaker(self.engine, expire_on_commit=False)
                logger.info("SQL database engine initialized.")
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                raise e

    async def disconnect(self) -> None:
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.session_maker = None
            logger.info("SQL database disconnected.")

    async def health_check(self) -> bool:
        if not self.engine:
            await self.connect()
        try:
            from sqlalchemy.sql import text
            session = await self._get_session()
            result = await session.execute(text("SELECT 1"))
            result.scalar() # Synchronous call on Result - no await
            if not self._session_var.get():
                await session.close()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def initialize_db(self) -> None:
        if not self.engine:
            await self.connect()
            
        from DataDb.models.base import BaseEntity
        
        def _subclasses(cls):
            subs = cls.__subclasses__()
            res = list(subs)
            for s in subs:
                res.extend(_subclasses(s))
            return res
            
        entities = _subclasses(BaseEntity)
        for entity_cls in entities:
            self.get_table(entity_cls)
            
        async with self.engine.begin() as conn:
            await conn.run_sync(self._metadata.create_all)
        logger.info(f"Database schema initialized for {len(entities)} entities.")

    def get_table(self, model_cls: Type[BaseEntity]):
        table_name = getattr(model_cls, "__tablename__", None) or model_cls.__name__.lower()
        if table_name in self._table_cache:
            return self._table_cache[table_name]
            
        columns = []
        for field_name, field in model_cls.model_fields.items():
            is_pk = False
            extra = field.json_schema_extra or {}
            if extra.get("primary_key") or field_name == "id":
                is_pk = True
                
            annotation = field.annotation
            sa_type = self._resolve_sa_type(annotation)
            
            is_nullable = True
            if field.is_required():
                is_nullable = False
                
            columns.append(self._sa.Column(field_name, sa_type, primary_key=is_pk, nullable=is_nullable))
            
        table = self._sa.Table(table_name, self._metadata, *columns)
        self._table_cache[table_name] = table
        return table

    def _resolve_sa_type(self, py_type) -> Any:
        origin = getattr(py_type, "__origin__", None)
        if origin is Union:
            args = py_type.__args__
            args = [a for a in args if a is not type(None)]
            if len(args) == 1:
                py_type = args[0]
            else:
                return self._sa.JSON
        # Extract origin of type to support generic lists and dicts
        type_origin = getattr(py_type, "__origin__", None) or py_type
        
        if py_type is int:
            return self._sa.Integer
        elif py_type is float:
            return self._sa.Float
        elif py_type is str:
            return self._sa.String(255)
        elif py_type is bool:
            return self._sa.Boolean
        elif py_type is datetime.datetime:
            return self._sa.DateTime
        elif py_type is datetime.date:
            return self._sa.Date
        elif type_origin in (dict, list, Dict, List):
            return self._sa.JSON
        else:
            return self._sa.JSON if hasattr(py_type, "model_fields") else self._sa.Text

    async def _get_session(self):
        current_session = self._session_var.get()
        if current_session is not None:
            return current_session
            
        if self.session_maker is None:
            await self.connect()
            
        return self.session_maker()

    def _apply_filters(self, stmt, table, filters: Optional[Dict[str, Any]]):
        if not filters:
            return stmt
            
        for key, val in filters.items():
            if "__" in key:
                col_name, op = key.split("__", 1)
            else:
                col_name, op = key, "eq"
                
            if col_name in table.columns:
                col = table.columns[col_name]
                if op == "eq":
                    stmt = stmt.where(col == val)
                elif op == "ne":
                    stmt = stmt.where(col != val)
                elif op == "gt":
                    stmt = stmt.where(col > val)
                elif op == "gte":
                    stmt = stmt.where(col >= val)
                elif op == "lt":
                    stmt = stmt.where(col < val)
                elif op == "lte":
                    stmt = stmt.where(col <= val)
                elif op == "in":
                    stmt = stmt.where(col.in_(val))
                elif op == "like":
                    stmt = stmt.where(col.like(val))
                elif op == "ilike":
                    stmt = stmt.where(col.ilike(val))
        return stmt

    async def insert(self, model_cls: Type[BaseEntity], data: Dict[str, Any]) -> Any:
        session = await self._get_session()
        table = self.get_table(model_cls)
        
        # Populate defaults and validate using Pydantic model
        instance = model_cls(**data)
        dumped_data = instance.model_dump()
        cleaned_data = {k: v for k, v in dumped_data.items() if k in table.columns}
        
        stmt = self._sa.insert(table).values(**cleaned_data)
        result = await session.execute(stmt)
        
        if not self._session_var.get():
            await session.commit()
            await session.close()
            
        return result.inserted_primary_key[0] if result.inserted_primary_key else None

    async def find(
        self,
        model_cls: Type[BaseEntity],
        filters: Optional[Dict[str, Any]] = None,
        sort: Optional[List[Tuple[str, str]]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[BaseEntity]:
        session = await self._get_session()
        table = self.get_table(model_cls)
        stmt = self._sa.select(table)
        
        stmt = self._apply_filters(stmt, table, filters)
        
        if sort:
            for col_name, order in sort:
                if col_name in table.columns:
                    col = table.columns[col_name]
                    stmt = stmt.order_by(col.desc() if order.lower() == "desc" else col.asc())
                    
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
            
        result = await session.execute(stmt)
        rows = result.fetchall()
        
        if not self._session_var.get():
            await session.close()
            
        return [model_cls(**dict(row._mapping)) for row in rows]

    async def update(self, model_cls: Type[BaseEntity], filters: Dict[str, Any], data: Dict[str, Any]) -> int:
        session = await self._get_session()
        table = self.get_table(model_cls)
        stmt = self._sa.update(table)
        
        stmt = self._apply_filters(stmt, table, filters)
        cleaned_data = {k: v for k, v in data.items() if k in table.columns}
        stmt = stmt.values(**cleaned_data)
        
        result = await session.execute(stmt)
        
        if not self._session_var.get():
            await session.commit()
            await session.close()
            
        return result.rowcount

    async def delete(self, model_cls: Type[BaseEntity], filters: Dict[str, Any]) -> int:
        session = await self._get_session()
        table = self.get_table(model_cls)
        stmt = self._sa.delete(table)
        
        stmt = self._apply_filters(stmt, table, filters)
        result = await session.execute(stmt)
        
        if not self._session_var.get():
            await session.commit()
            await session.close()
            
        return result.rowcount

    async def count(self, model_cls: Type[BaseEntity], filters: Optional[Dict[str, Any]] = None) -> int:
        session = await self._get_session()
        table = self.get_table(model_cls)
        stmt = self._sa.select(self._sa.func.count()).select_from(table)
        
        stmt = self._apply_filters(stmt, table, filters)
        result = await session.execute(stmt)
        val = result.scalar()
        
        if not self._session_var.get():
            await session.close()
            
        return val or 0

    async def bulk_insert(self, model_cls: Type[BaseEntity], items: List[Dict[str, Any]]) -> List[Any]:
        if not items:
            return []
        session = await self._get_session()
        table = self.get_table(model_cls)
        
        cleaned_items = []
        for item in items:
            instance = model_cls(**item)
            dumped = instance.model_dump()
            cleaned_items.append({k: v for k, v in dumped.items() if k in table.columns})
            
        stmt = self._sa.insert(table).values(cleaned_items)
        result = await session.execute(stmt)
        
        if not self._session_var.get():
            await session.commit()
            await session.close()
            
        return []

    async def bulk_update(self, model_cls: Type[BaseEntity], items: List[Dict[str, Any]], key_field: str = "id") -> int:
        if not items:
            return 0
        session = await self._get_session()
        table = self.get_table(model_cls)
        
        updated_count = 0
        for item in items:
            if key_field in item:
                key_val = item[key_field]
                cleaned_data = {k: v for k, v in item.items() if k in table.columns and k != key_field}
                stmt = (
                    self._sa.update(table)
                    .where(table.columns[key_field] == key_val)
                    .values(**cleaned_data)
                )
                res = await session.execute(stmt)
                updated_count += res.rowcount
                
        if not self._session_var.get():
            await session.commit()
            await session.close()
            
        return updated_count

    async def bulk_delete(self, model_cls: Type[BaseEntity], filters: Dict[str, Any]) -> int:
        return await self.delete(model_cls, filters)

    @asynccontextmanager
    async def transaction(self):
        if self.session_maker is None:
            await self.connect()
            
        session = self.session_maker()
        token = self._session_var.set(session)
        try:
            async with session.begin():
                yield session
        except Exception as e:
            logger.error(f"Transaction rolled back: {e}")
            raise e
        finally:
            await session.close()
            self._session_var.reset(token)
