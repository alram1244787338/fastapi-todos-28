import uuid
from typing import Optional

from pydantic import BaseModel

from app.schemas.base import BaseInDB, BaseUpdateInDB
from app.models.tables import Category


class CategoryCreate(BaseModel):
    name: str


class CategoryRead(CategoryCreate):
    id: int

    class Config:
        orm_mode = True


class CategoryReadWithDetails(BaseModel):
    id: int
    name: str
    todos_count: int
    is_default: bool

    class Config:
        orm_mode = True


class CategoryUpdate(BaseModel):
    name: str


class CategoryInDB(BaseInDB, CategoryCreate):
    created_by_id: Optional[uuid.UUID]

    class Config(BaseInDB.Config):
        orm_model = Category


class CategoryUpdateInDB(BaseUpdateInDB, CategoryUpdate):
    created_by_id: uuid.UUID

    class Config(BaseInDB.Config):
        orm_model = Category
