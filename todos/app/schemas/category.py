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


class CategoryReadDetailed(CategoryRead):
    # is_default tells the client whether this is a system category (created_by_id is NULL)
    # or a private one owned by the user - i.e. whether the user may rename/delete it.
    is_default: bool
    # number of the requesting user's todos attached to this category
    todos_count: int


class CategoryUpdate(BaseModel):
    name: str


class CategoryInDB(BaseInDB, CategoryCreate):
    created_by_id: Optional[uuid.UUID]

    class Config(BaseInDB.Config):
        orm_model = Category


class CategoryUpdateInDB(BaseUpdateInDB, CategoryCreate):
    created_by_id: Optional[uuid.UUID]

    class Config(BaseInDB.Config):
        orm_model = Category
