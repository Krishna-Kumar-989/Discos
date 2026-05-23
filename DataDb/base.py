from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Type
from contextlib import asynccontextmanager
from DataDb.models.base import BaseEntity

class BaseDatabaseProvider(ABC):
    """Abstract base class representing a provider-agnostic database client."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish database connection pool/client."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close database connection pool/client."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify the database connection is active."""
        pass

    @abstractmethod
    async def initialize_db(self) -> None:
        """Create tables or initialize schema/collections."""
        pass

    @abstractmethod
    async def insert(self, model_cls: Type[BaseEntity], data: Dict[str, Any]) -> Any:
        """Insert a single record. Returns the primary key of the inserted item."""
        pass

    @abstractmethod
    async def find(
        self,
        model_cls: Type[BaseEntity],
        filters: Optional[Dict[str, Any]] = None,
        sort: Optional[List[Tuple[str, str]]] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[BaseEntity]:
        """Find records matching the filters, with optional sorting and pagination."""
        pass

    @abstractmethod
    async def update(self, model_cls: Type[BaseEntity], filters: Dict[str, Any], data: Dict[str, Any]) -> int:
        """Update records matching the filters. Returns the number of affected rows."""
        pass

    @abstractmethod
    async def delete(self, model_cls: Type[BaseEntity], filters: Dict[str, Any]) -> int:
        """Delete records matching the filters. Returns the number of affected rows."""
        pass

    @abstractmethod
    async def count(self, model_cls: Type[BaseEntity], filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records matching the filters."""
        pass

    @abstractmethod
    async def bulk_insert(self, model_cls: Type[BaseEntity], items: List[Dict[str, Any]]) -> List[Any]:
        """Insert multiple records in bulk. Returns the primary keys of inserted items if possible."""
        pass

    @abstractmethod
    async def bulk_update(self, model_cls: Type[BaseEntity], items: List[Dict[str, Any]], key_field: str = "id") -> int:
        """Update multiple records in bulk by matching key_field. Returns the number of updated records."""
        pass

    @abstractmethod
    async def bulk_delete(self, model_cls: Type[BaseEntity], filters: Dict[str, Any]) -> int:
        """Delete multiple records in bulk matching filters. Returns the number of deleted records."""
        pass

    @abstractmethod
    @asynccontextmanager
    async def transaction(self):
        """Async context manager to execute block inside a transaction."""
        pass

    async def paginate(
        self,
        model_cls: Type[BaseEntity],
        page: int = 1,
        page_size: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        sort: Optional[List[Tuple[str, str]]] = None
    ) -> Dict[str, Any]:
        """Paginate records of a model."""
        total = await self.count(model_cls, filters)
        offset = (page - 1) * page_size
        items = await self.find(model_cls, filters=filters, sort=sort, limit=page_size, offset=offset)
        import math
        total_pages = math.ceil(total / page_size) if page_size > 0 else 0
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }
