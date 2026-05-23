from DataDb.providers.sql_provider import SQLProvider
from DataDb.config import DBConfig

class MysqlProvider(SQLProvider):
    """
    MySQL provider implementation using SQLAlchemy + aiomysql.
    """
    
    def __init__(self):
        url = DBConfig.get_sql_url()
        super().__init__(connection_url=url, required_driver="aiomysql")
