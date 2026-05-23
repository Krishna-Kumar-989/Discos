from DataDb.base import BaseDatabaseProvider
from DataDb.config import DBConfig

_db_instance = None

def get_db_client() -> BaseDatabaseProvider:
    global _db_instance
    if _db_instance is None:
        provider = DBConfig.PROVIDER
        if provider == "sqlite":
            from DataDb.providers.sqlite import SqliteProvider
            _db_instance = SqliteProvider()
        elif provider == "postgres":
            from DataDb.providers.postgres import PostgresProvider
            _db_instance = PostgresProvider()
        elif provider == "mysql":
            from DataDb.providers.mysql import MysqlProvider
            _db_instance = MysqlProvider()
        elif provider == "mongodb":
            from DataDb.providers.mongodb import MongoDBProvider
            _db_instance = MongoDBProvider()
        else:
            raise ValueError(f"Unsupported database provider: {provider}")
            
    return _db_instance

class DatabaseProxy:
    """
    Lazy proxy routing calls to the singleton DB client. Resolves
    drivers/configurations when first accessed rather than import time.
    """
    def __getattr__(self, name):
        client = get_db_client()
        return getattr(client, name)

db = DatabaseProxy()
