from typing import Optional, Type, TypeVar, Union, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update, and_

from app.models.base import Base
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

    async def get_multi_by_ids(
        self,
        session: AsyncSession,
        *,
        table_model: Type[ModelType],
        ids: list[int],
        owner_filter=None,
    ) -> list[ModelType]:
        filters = [table_model.id.in_(ids)]
        if owner_filter is not None:
            filters.append(owner_filter)
        query = select(table_model).filter(and_(*filters))
        result = await session.execute(query)
        return result.scalars().all()

    async def batch_update_is_completed(
        self,
        session: AsyncSession,
        *,
        table_model: Type[ModelType],
        ids: list[int],
        is_completed: bool,
    ) -> int:
        stmt = (
            update(table_model)
            .where(table_model.id.in_(ids))
            .values(is_completed=is_completed)
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount

    async def delete_by_ids(
        self,
        session: AsyncSession,
        *,
        table_model: Type[ModelType],
        ids: list[int],
    ) -> int:
        stmt = delete(table_model).where(table_model.id.in_(ids))
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount
