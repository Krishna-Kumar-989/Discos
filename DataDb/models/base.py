from pydantic import BaseModel, ConfigDict
from typing import ClassVar

class BaseEntity(BaseModel):
    """Base entity representing a database record or document."""
    model_config = ConfigDict(populate_by_name=True)
    
    __tablename__: ClassVar[str] = ""
    __collectionname__: ClassVar[str] = ""
