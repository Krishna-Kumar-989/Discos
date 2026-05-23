import contextvars
import logging
from typing import Any, Dict, List, Optional, Tuple, Type
from contextlib import asynccontextmanager

from DataDb.base import BaseDatabaseProvider
from DataDb.models.base import BaseEntity
from DataDb.config import DBConfig

logger = logging.getLogger("DataDb.mongodb")

class MongoDBProvider(BaseDatabaseProvider):
    """
    MongoDB Database Provider using the Motor driver.
    """

    def __init__(self):
        self.uri = DBConfig.MONGODB_URI
        self.db_name = DBConfig.MONGODB_DB
        self.client = None
        self.db = None
        self._session_var = contextvars.ContextVar("mongo_session", default=None)

        try:
            import motor.motor_asyncio
            from pymongo import UpdateOne
        except ImportError:
            raise ImportError("MongoDB driver 'motor' is not installed. Please pip install it.")
            
        self._motor = motor
        self._UpdateOne = UpdateOne

    async def connect(self) -> None:
        if self.client is None:
            try:
                self.client = self._motor.motor_asyncio.AsyncIOMotorClient(self.uri)
                self.db = self.client[self.db_name]
                logger.info(f"Connected to MongoDB at {self.uri.split('@')[-1]} (DB: {self.db_name})")
            except Exception as e:
                logger.error(f"Failed to connect to MongoDB: {e}")
                raise e

    async def disconnect(self) -> None:
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            logger.info("MongoDB client connection closed.")

    async def health_check(self) -> bool:
        if not self.client:
            await self.connect()
        try:
            await self.client.admin.command('ping')
            return True
        except Exception as e:
            logger.error(f"MongoDB health check failed: {e}")
            return False

    async def initialize_db(self) -> None:
        await self.health_check()
        logger.info("MongoDB initialization complete.")

    def get_collection(self, model_cls: Type[BaseEntity]):
        if not self.db:
            raise RuntimeError("Database not connected. Call connect() first.")
        name = getattr(model_cls, "__collectionname__", None) or model_cls.__name__.lower()
        return self.db[name]

    def parse_filters(self, filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not filters:
            return {}
            
        mongo_filters = {}
        for key, val in filters.items():
            if "__" in key:
                col_name, op = key.split("__", 1)
            else:
                col_name, op = key, "eq"
                
            field = "_id" if col_name == "id" else col_name
            
            if op == "eq":
                mongo_filters[field] = val
            elif op == "ne":
                mongo_filters[field] = {"$ne": val}
            elif op == "gt":
                mongo_filters[field] = {"$gt": val}
            elif op == "gte":
                mongo_filters[field] = {"$gte": val}
            elif op == "lt":
                mongo_filters[field] = {"$lt": val}
            elif op == "lte":
                mongo_filters[field] = {"$lte": val}
            elif op == "in":
                mongo_filters[field] = {"$in": val}
            elif op in ("like", "ilike"):
                import re
                escaped = re.escape(str(val)).replace(r"\%", ".*")
                mongo_filters[field] = {
                    "$regex": escaped,
                    "$options": "i" if op == "ilike" else ""
                }
                
        return mongo_filters

    async def insert(self, model_cls: Type[BaseEntity], data: Dict[str, Any]) -> Any:
        if not self.db:
            await self.connect()
        coll = self.get_collection(model_cls)
        
        # Populate defaults and validate using Pydantic model
        instance = model_cls(**data)
        dumped_data = instance.model_dump()
        
        if "id" in dumped_data:
            dumped_data["_id"] = dumped_data.pop("id")
            
        session = self._session_var.get()
        res = await coll.insert_one(dumped_data, session=session)
        return res.inserted_id

    async def find(
        self,
        model_cls: Type[BaseEntity],
        filters: Optional[Dict[str, Any]] = None,
        sort: Optional[List[Tuple[str, str]]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[BaseEntity]:
        if not self.db:
            await self.connect()
        coll = self.get_collection(model_cls)
        mongo_filters = self.parse_filters(filters)
        
        session = self._session_var.get()
        cursor = coll.find(mongo_filters, session=session)
        
        if sort:
            mongo_sort = []
            for col_name, order in sort:
                field = "_id" if col_name == "id" else col_name
                direction = 1 if order.lower() == "asc" else -1
                mongo_sort.append((field, direction))
            cursor = cursor.sort(mongo_sort)
            
        if offset is not None:
            cursor = cursor.skip(offset)
        if limit is not None:
            cursor = cursor.limit(limit)
            
        results = []
        async for doc in cursor:
            if "_id" in doc:
                doc["id"] = doc.pop("_id")
            results.append(model_cls(**doc))
            
        return results

    async def update(self, model_cls: Type[BaseEntity], filters: Dict[str, Any], data: Dict[str, Any]) -> int:
        if not self.db:
            await self.connect()
        coll = self.get_collection(model_cls)
        mongo_filters = self.parse_filters(filters)
        
        cleaned_data = dict(data)
        cleaned_data.pop("_id", None)
        cleaned_data.pop("id", None)
        
        session = self._session_var.get()
        res = await coll.update_many(mongo_filters, {"$set": cleaned_data}, session=session)
        return res.modified_count

    async def delete(self, model_cls: Type[BaseEntity], filters: Dict[str, Any]) -> int:
        if not self.db:
            await self.connect()
        coll = self.get_collection(model_cls)
        mongo_filters = self.parse_filters(filters)
        
        session = self._session_var.get()
        res = await coll.delete_many(mongo_filters, session=session)
        return res.deleted_count

    async def count(self, model_cls: Type[BaseEntity], filters: Optional[Dict[str, Any]] = None) -> int:
        if not self.db:
            await self.connect()
        coll = self.get_collection(model_cls)
        mongo_filters = self.parse_filters(filters)
        
        session = self._session_var.get()
        return await coll.count_documents(mongo_filters, session=session)

    async def bulk_insert(self, model_cls: Type[BaseEntity], items: List[Dict[str, Any]]) -> List[Any]:
        if not items:
            return []
        if not self.db:
            await self.connect()
        coll = self.get_collection(model_cls)
        
        cleaned_items = []
        for item in items:
            instance = model_cls(**item)
            dumped = instance.model_dump()
            if "id" in dumped:
                dumped["_id"] = dumped.pop("id")
            cleaned_items.append(dumped)
            
        session = self._session_var.get()
        res = await coll.insert_many(cleaned_items, session=session)
        return res.inserted_ids

    async def bulk_update(self, model_cls: Type[BaseEntity], items: List[Dict[str, Any]], key_field: str = "id") -> int:
        if not items:
            return 0
        if not self.db:
            await self.connect()
        coll = self.get_collection(model_cls)
        
        requests = []
        for item in items:
            if key_field not in item:
                continue
            key_val = item[key_field]
            match_field = "_id" if key_field == "id" else key_field
            cleaned_data = {k: v for k, v in item.items() if k != key_field}
            
            requests.append(self._UpdateOne({match_field: key_val}, {"$set": cleaned_data}))
            
        if not requests:
            return 0
            
        session = self._session_var.get()
        res = await coll.bulk_write(requests, session=session)
        return res.modified_count

    async def bulk_delete(self, model_cls: Type[BaseEntity], filters: Dict[str, Any]) -> int:
        return await self.delete(model_cls, filters)

    @asynccontextmanager
    async def transaction(self):
        if not self.client:
            await self.connect()
            
        try:
            async with await self.client.start_session() as session:
                async with session.start_transaction():
                    token = self._session_var.set(session)
                    try:
                        yield session
                    finally:
                        self._session_var.reset(token)
        except Exception as e:
            logger.warning(f"Transactions not supported by this MongoDB setup: {e}. Falling back to transaction-less execution.")
            yield None
