# DataDb: Database Abstraction Layer

DataDb is a provider-agnostic, asynchronous database abstraction layer for the **Discos** project. It allows the application to switch between different database backends (SQLite, PostgreSQL, MySQL, MongoDB) using environment variables, while exposing a single unified, developer-friendly interface.

---

## Table of Contents
- [Architecture](#architecture)
- [Supported Databases](#supported-databases)
- [Configuration](#configuration)
- [Dependency Management](#dependency-management)
- [Usage Examples](#usage-examples)
  - [Defining Models](#1-defining-models)
  - [Basic CRUD Operations](#2-basic-crud-operations)
  - [Filtering and Querying](#3-filtering-and-querying)
  - [Bulk Operations](#4-bulk-operations)
  - [Transactions](#5-transactions)
  - [Pagination](#6-pagination)
  - [Health Checks & Initialization](#7-health-checks--initialization)
- [Adding New Providers](#adding-new-providers)

---

## Architecture

DataDb utilizes a **Factory Pattern** combined with a **Lazy Proxy** pattern:
- **`BaseDatabaseProvider`**: Abstract Base Class defining all required methods.
- **Lazy Proxy (`db`)**: The exported database singleton acts as a proxy. Drivers and configurations are not loaded/evaluated until the database is first queried. This prevents dependency import errors if a database is not active or its drivers are not installed.
- **SQL Alchemy Core Mapping**: For SQL providers (SQLite, Postgres, MySQL), Pydantic schemas (inheriting from `BaseEntity`) are mapped dynamically to SQLAlchemy core tables on startup, removing the need to maintain redundant SQLAlchemy model schemas.
- **Context-Scoped Transactions**: Transactions are managed using Python's `contextvars`, letting queries inside a transaction block automatically bind to the active database session.

---

## Supported Databases

| Provider Name | Driver | Connection URL Format |
| :--- | :--- | :--- |
| **`sqlite`** (Default) | `aiosqlite` | `sqlite+aiosqlite:///path/to/db.db` |
| **`postgres`** | `asyncpg` | `postgresql+asyncpg://user:pass@host:port/dbname` |
| **`mysql`** | `aiomysql` | `mysql+aiomysql://user:pass@host:port/dbname` |
| **`mongodb`** | `motor` | `mongodb://host:port` |

---

## Configuration

Database credentials and options are read from environment variables:

```ini
# Selected DB provider: sqlite, postgres, mysql, mongodb
DB_PROVIDER=sqlite

# SQLite
SQLITE_DB_PATH=DataDb/data.db

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
POSTGRES_DB=discos

# MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=password
MYSQL_DB=discos

# MongoDB
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=discos
```

---

## Dependency Management

To keep the project footprint lightweight, drivers are lazy-imported. Only install the packages for your selected provider:

```bash
# Common Core Requirement (for SQL databases)
pip install SQLAlchemy

# SQLite
pip install aiosqlite

# PostgreSQL
pip install asyncpg

# MySQL
pip install aiomysql

# MongoDB
pip install motor
```

---

## Usage Examples

### 1. Defining Models

All database models must inherit from `BaseEntity` (which inherits from Pydantic `BaseModel`):

```python
from datetime import datetime
from typing import Optional
from pydantic import Field
from DataDb import BaseEntity

class UserProfile(BaseEntity):
    # Specify the target SQL table or MongoDB collection
    __tablename__ = "user_profiles"
    __collectionname__ = "user_profiles"
    
    # Mark primary key with json_schema_extra
    id: str = Field(..., json_schema_extra={"primary_key": True})
    username: str
    email: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    active: bool = Field(default=True)
```

### 2. Basic CRUD Operations

```python
from DataDb import db
from models import UserProfile

# 1. Insert
user_id = await db.insert(UserProfile, {
    "id": "usr_1001",
    "username": "coder_bob",
    "email": "bob@example.com"
})

# 2. Find
users = await db.find(UserProfile, filters={"username": "coder_bob"})
bob = users[0] if users else None

# 3. Update
updated_rows = await db.update(
    UserProfile,
    filters={"id": "usr_1001"},
    data={"email": "new_bob@example.com"}
)

# 4. Delete
deleted_rows = await db.delete(UserProfile, filters={"id": "usr_1001"})
```

### 3. Filtering and Querying

DataDb supports Django-like operators for database-agnostic querying:

```python
# Exact Match (eq)
await db.find(UserProfile, filters={"active": True})

# Greater Than / Less Than
await db.find(UserProfile, filters={"created_at__gte": date_threshold})

# In List
await db.find(UserProfile, filters={"id__in": ["usr_1", "usr_2", "usr_3"]})

# String contains (SQL LIKE or Mongo regex)
await db.find(UserProfile, filters={"email__ilike": "%@example.com"})

# Sorting & Limits
results = await db.find(
    UserProfile,
    filters={"active": True},
    sort=[("created_at", "desc")],
    limit=5,
    offset=0
)
```

### 4. Bulk Operations

```python
# Bulk Insert
await db.bulk_insert(UserProfile, [
    {"id": "usr_2", "username": "alice", "email": "alice@example.com"},
    {"id": "usr_3", "username": "charlie", "email": "charlie@example.com"}
])

# Bulk Update (match rows using `key_field` e.g., 'id')
await db.bulk_update(UserProfile, [
    {"id": "usr_2", "active": False},
    {"id": "usr_3", "active": True}
], key_field="id")
```

### 5. Transactions

Transactions ensure atomic database operations. In case of an exception, all changes are automatically rolled back.

```python
async with db.transaction():
    # These operations will run within the same transaction context
    await db.insert(UserProfile, {"id": "usr_4", "username": "dan", "email": "dan@example.com"})
    await db.update(UserProfile, filters={"id": "usr_2"}, data={"active": True})
    # If any error is raised here, both operations are rolled back
```

### 6. Pagination

```python
page_data = await db.paginate(
    UserProfile,
    page=1,
    page_size=20,
    filters={"active": True},
    sort=[("username", "asc")]
)

print(page_data["items"])       # List of UserProfile objects
print(page_data["total"])       # Total matching records
print(page_data["total_pages"]) # Calculated pages count
```

### 7. Health Checks & Initialization

Initialize the database schema and check the database connection health:

```python
# Ping the database
is_healthy = await db.health_check()

# Initialize tables (run DDL / migrations check on startup)
await db.initialize_db()
```

---

## Adding New Providers

To add a new provider:
1. Create a new subclass file in `providers/` (e.g. `providers/my_db.py`).
2. Inherit from `BaseDatabaseProvider` and implement all abstract methods.
3. Update `factory.py` to recognize the new provider and register it in `get_db_client()`.
4. Update `config.py` to add any custom settings/connections configurations needed for the database.
