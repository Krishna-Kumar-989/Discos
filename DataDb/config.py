import os
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("DataDb.config")

class DBConfig:
    PROVIDER: str = os.getenv("DB_PROVIDER", "sqlite").lower()
    
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", "DataDb/data.db")
    
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "discos")
    
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DB: str = os.getenv("MYSQL_DB", "discos")
    
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB: str = os.getenv("MONGODB_DB", "discos")

    @classmethod
    def load_from_yaml(cls, config_path: str):
        """Load database configurations from a YAML file, overriding environment variables."""
        if not os.path.exists(config_path):
            logger.warning(f"Config file not found at {config_path}")
            return
            
        try:
            import yaml
        except ImportError:
            logger.error("pyyaml is not installed. Cannot load YAML configuration.")
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                
            db_data = data.get("database", data)
                
            if "provider" in db_data:
                cls.PROVIDER = str(db_data["provider"]).lower()
                
            sqlite_data = db_data.get("sqlite", {})
            if "db_path" in sqlite_data:
                cls.SQLITE_DB_PATH = sqlite_data["db_path"]
            elif "db_path" in db_data:
                cls.SQLITE_DB_PATH = db_data["db_path"]
                
            pg_data = db_data.get("postgres", {})
            if "host" in pg_data: cls.POSTGRES_HOST = pg_data["host"]
            if "port" in pg_data: cls.POSTGRES_PORT = int(pg_data["port"])
            if "user" in pg_data: cls.POSTGRES_USER = pg_data["user"]
            if "password" in pg_data: cls.POSTGRES_PASSWORD = pg_data["password"]
            if "db" in pg_data: cls.POSTGRES_DB = pg_data["db"]
            
            mysql_data = db_data.get("mysql", {})
            if "host" in mysql_data: cls.MYSQL_HOST = mysql_data["host"]
            if "port" in mysql_data: cls.MYSQL_PORT = int(mysql_data["port"])
            if "user" in mysql_data: cls.MYSQL_USER = mysql_data["user"]
            if "password" in mysql_data: cls.MYSQL_PASSWORD = mysql_data["password"]
            if "db" in mysql_data: cls.MYSQL_DB = mysql_data["db"]
            
            mongo_data = db_data.get("mongodb", {})
            if "uri" in mongo_data: cls.MONGODB_URI = mongo_data["uri"]
            if "db" in mongo_data: cls.MONGODB_DB = mongo_data["db"]
            
            logger.info(f"Loaded database configuration from {config_path}")
        except Exception as e:
            logger.error(f"Error loading configuration from YAML: {e}")

    @classmethod
    def get_sql_url(cls) -> str:
        """Get SQLAlchemy connection URL based on the active provider."""
        if cls.PROVIDER == "sqlite":
            path = cls.SQLITE_DB_PATH
            if not os.path.isabs(path):
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                path = os.path.abspath(os.path.join(project_root, path))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            return f"sqlite+aiosqlite:///{path}"
            
        elif cls.PROVIDER == "postgres":
            return f"postgresql+asyncpg://{cls.POSTGRES_USER}:{cls.POSTGRES_PASSWORD}@{cls.POSTGRES_HOST}:{cls.POSTGRES_PORT}/{cls.POSTGRES_DB}"
            
        elif cls.PROVIDER == "mysql":
            return f"mysql+aiomysql://{cls.MYSQL_USER}:{cls.MYSQL_PASSWORD}@{cls.MYSQL_HOST}:{cls.MYSQL_PORT}/{cls.MYSQL_DB}"
            
        else:
            raise ValueError(f"Provider {cls.PROVIDER} is not an SQL provider.")

env_config_path = os.getenv("DB_CONFIG_PATH")
if env_config_path:
    DBConfig.load_from_yaml(env_config_path)
else:
    this_dir = os.path.dirname(os.path.abspath(__file__))
    local_yaml = os.path.join(this_dir, "config.yaml")
    root_yaml = os.path.join(os.path.dirname(this_dir), "config.yaml")
    
    if os.path.exists(local_yaml):
        DBConfig.load_from_yaml(local_yaml)
    elif os.path.exists(root_yaml):
        DBConfig.load_from_yaml(root_yaml)
