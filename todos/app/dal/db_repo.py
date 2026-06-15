import uuid
from typing import Optional, Type, TypeVar, Union, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, and_, or_

from app.models.base import Base
from app.models.tables import Category, Todo, TodoCategory
from app.schemas.base import BaseInDB, BaseUpdateInDB
from app.dal.constants import GET_MULTI_DEFAULT_SKIP


ModelType = TypeVar('ModelType', bound=Base)
InDBSchemaType = TypeVar('InDBSchemaType', bound=BaseInDB)
UpdateSchemaType = TypeVar('UpdateSchemaType', bound=BaseUpdateInDB)


class DBRepo:

    def __init__(self) -> None:
        ...

    async def get(  # type: ignore[no-untyped-def]
        self,
        session: AsyncSession,
        *,
        table_model: Type[ModelType],
        query_filter=None  # type: ignore
    ) -> Union[Optional[ModelType]]:
        query = select(table_model)
        if query_filter is not None:
            query = query.filter(query_filter)
        result = await session.execute(query)
        return result.scalars().first()

    async def get_multi(    # type: ignore[no-untyped-def]
        self,
        session: AsyncSession,
        *,
        table_model: Type[ModelType],
        query_filter=None,
        skip: int = GET_MULTI_DEFAULT_SKIP,
        limit: Optional[int] = None
    ) -> list[ModelType]:
        query = select(table_model)
        if query_filter is not None:
            query = query.filter(query_filter)
        query = query.offset(skip)
        if limit is not None:
            query = query.limit(limit)
        result = await session.execute(query)
        return result.scalars().all()

    async def get_categories_with_todos_count(  # type: ignore[no-untyped-def]
        self,
        session: AsyncSession,
        *,
        created_by_id: uuid.UUID,
        query_filter=None,
        skip: int = GET_MULTI_DEFAULT_SKIP,
        limit: Optional[int] = None
    ) -> list[tuple[Category, int]]:
        # returns every category visible to the user (system defaults + own ones)
        # together with the amount of the user's todos attached to each category.
        # the todos are filtered inside the outer join so categories with no
        # matching todo still come back with a count of 0.
        visible_categories_filter = or_(
            Category.created_by_id.is_(None),
            Category.created_by_id == created_by_id
        )
        user_todos_join = and_(
            Todo.id == TodoCategory.todo_id,
            Todo.created_by_id == created_by_id
        )
        query = (
            select(Category, func.count(Todo.id))
            .outerjoin(TodoCategory, TodoCategory.category_id == Category.id)
            .outerjoin(Todo, user_todos_join)
            .where(visible_categories_filter)
            .group_by(Category.id)
            .order_by(Category.id)
        )
        if query_filter is not None:
            query = query.where(query_filter)
        query = query.offset(skip)
        if limit is not None:
            query = query.limit(limit)
        result = await session.execute(query)
        return [(category, todos_count) for category, todos_count in result.all()]

    async def create(
        self,
        session: AsyncSession,
        *,
        obj_to_create: InDBSchemaType
    ) -> ModelType:
        db_obj: ModelType = obj_to_create.to_orm()
        session.add(db_obj)
        await session.commit()
        await session.refresh(db_obj)
        return db_obj

    async def update(
        self,
        session: AsyncSession,
        *,
        updated_obj: UpdateSchemaType,
        db_obj_to_update: Optional[ModelType] = None
    ) -> Optional[ModelType]:
        existing_obj_to_update: Optional[ModelType] = db_obj_to_update or await self.get(
            session,
            table_model=updated_obj.Config.orm_model,
            query_filter=updated_obj.Config.orm_model.id == updated_obj.id
        )
        if existing_obj_to_update:
            existing_obj_to_update_data = existing_obj_to_update.dict()
            updated_data: dict[str, Any] = updated_obj.to_orm().dict()
            for field in existing_obj_to_update_data:
                if field in updated_data:
                    setattr(existing_obj_to_update, field, updated_data[field])
            session.add(existing_obj_to_update)
            await session.commit()
            await session.refresh(existing_obj_to_update)
        return existing_obj_to_update

    async def delete(
        self,
        session: AsyncSession,
        *,
        table_model: Type[ModelType],
        id_to_delete: int
    ) -> None:
        query = delete(table_model).where(table_model.id == id_to_delete)
        await session.execute(query)
        await session.commit()
