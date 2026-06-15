import uuid
from typing import Optional

from sqlalchemy import or_, and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dal.db_repo import DBRepo
from app.dal.constants import GET_MULTI_DEFAULT_SKIP, GET_MULTI_DEFAULT_LIMIT
from app.models.tables import Priority, Category, Todo
from app.schemas import CategoryInDB, TodoInDB, TodoUpdateInDB, PriorityCount, TodoSummary
from app.http_exceptions import ResourceNotExists, UserNotAllowed, ResourceAlreadyExists


class DBService:

    def __init__(self) -> None:
        self._repo = DBRepo()

    async def _validate_todo_categories(
        self,
        session: AsyncSession,
        *,
        todo_categories_ids: list[int],
        created_by_id: uuid.UUID
    ) -> bool:
        # validates that the todo categories are valid to the user + no duplications
        default_categories_filter = Category.created_by_id.is_(None)
        user_categories_filter = Category.created_by_id == created_by_id
        valid_categories_filter = or_(default_categories_filter, user_categories_filter)
        todo_categories_ids_filter = Category.id.in_(todo_categories_ids)

        categories_from_db: list[Category] = await self._repo.get_multi(
            session,
            table_model=Category,
            query_filter=and_(valid_categories_filter, todo_categories_ids_filter)
        )
        are_categories_valid: bool = len(todo_categories_ids) == len(categories_from_db)
        return are_categories_valid

    async def get_priorities(self, session: AsyncSession) -> list[Priority]:
        return await self._repo.get_multi(session, table_model=Priority)

    async def get_categories(
        self,
        session: AsyncSession,
        *,
        created_by_id: uuid.UUID,
        skip: int = GET_MULTI_DEFAULT_SKIP,
        limit: int = GET_MULTI_DEFAULT_LIMIT
    ) -> list[Category]:
        default_categories_filter = Category.created_by_id.is_(None)
        user_categories_filter = Category.created_by_id == created_by_id
        query_filter = or_(user_categories_filter, default_categories_filter)
        return await self._repo.get_multi(
            session,
            table_model=Category,
            query_filter=query_filter,
            limit=limit,
            skip=skip
        )

    async def add_category(
        self,
        session: AsyncSession,
        *,
        category_in: CategoryInDB
    ) -> Category:
        users_categories: list[Category] = await self.get_categories(
            session,
            created_by_id=category_in.created_by_id)
        users_categories_names: list[str] = [c.name for c in users_categories]
        if category_in.name in users_categories_names:
            raise ResourceAlreadyExists(resource='category name')
        return await self._repo.create(session, obj_to_create=category_in)

    async def delete_category(
        self,
        session: AsyncSession,
        *,
        id_to_delete: int,
        created_by_id: uuid.UUID
    ) -> None:
        category_to_delete: Optional[Category] = await self._repo.get(
            session,
            table_model=Category,
            query_filter=Category.id == id_to_delete
        )
        if not category_to_delete:
            raise ResourceNotExists(resource='category')
        if category_to_delete.created_by_id != created_by_id:
            raise UserNotAllowed('a user can not delete a category that was not created by him')
        await self._repo.delete(session, table_model=Category, id_to_delete=id_to_delete)

    async def get_todos(
        self,
        session: AsyncSession,
        *,
        created_by_id: uuid.UUID,
        skip: int = GET_MULTI_DEFAULT_SKIP,
        limit: int = GET_MULTI_DEFAULT_LIMIT
    ) -> list[Todo]:
        return await self._repo.get_multi(
            session,
            table_model=Todo,
            query_filter=Todo.created_by_id == created_by_id,
            skip=skip,
            limit=limit
        )

    async def add_todo(
        self,
        session: AsyncSession,
        *,
        todo_in: TodoInDB
    ) -> Todo:
        if await self._validate_todo_categories(
            session,
            todo_categories_ids=todo_in.categories_ids,
            created_by_id=todo_in.created_by_id
        ):
            try:
                return await self._repo.create(session, obj_to_create=todo_in)
            except IntegrityError:
                raise ValueError('priority is not valid')
        raise ValueError('categories are not valid')

    async def update_todo(
        self,
        session: AsyncSession,
        *,
        updated_todo: TodoUpdateInDB
    ) -> Todo:
        todo_to_update: Optional[Todo] = await self._repo.get(
            session,
            table_model=Todo,
            query_filter=Todo.id == updated_todo.id
        )
        if not todo_to_update:
            raise ResourceNotExists(resource='todo')
        if not todo_to_update.created_by_id == updated_todo.created_by_id:
            raise UserNotAllowed('a user can not update a todo that was not created by him')
        if await self._validate_todo_categories(
            session,
            todo_categories_ids=updated_todo.categories_ids,
            created_by_id=updated_todo.created_by_id
        ):
            try:
                todo_updated_obj: Optional[Todo] = await self._repo.update(
                    session,
                    updated_obj=updated_todo,
                    db_obj_to_update=todo_to_update
                )
                if todo_updated_obj:
                    return todo_updated_obj
                raise ResourceNotExists(resource='todo')
            except IntegrityError:
                raise ValueError('priority is not valid')
        raise ValueError('categories are not valid')

    async def delete_todo(
        self,
        session: AsyncSession,
        *,
        id_to_delete: int,
        created_by_id: uuid.UUID
    ) -> None:
        todo_to_delete: Optional[Todo] = await self._repo.get(
            session,
            table_model=Todo,
            query_filter=Todo.id == id_to_delete
        )
        if not todo_to_delete:
            raise ResourceNotExists(resource='todo')
        if todo_to_delete.created_by_id != created_by_id:
            raise UserNotAllowed('a user can not delete a todo that was not created by him')
        await self._repo.delete(session, table_model=Todo, id_to_delete=id_to_delete)

    async def _validate_batch_todo_ownership(
        self,
        session: AsyncSession,
        *,
        todo_ids: list[int],
        created_by_id: uuid.UUID,
    ) -> list[Todo]:
        """Fetch todos by ids and validate they all exist and belong to the user.

        Raises ResourceNotExists (404) if any ids don't exist.
        Raises UserNotAllowed (403) if any ids belong to another user.
        Returns the fetched todos on success.
        """
        todos: list[Todo] = await self._repo.get_multi_by_ids(
            session,
            table_model=Todo,
            ids=todo_ids,
        )
        found_ids = {t.id for t in todos}
        not_found_ids = sorted(set(todo_ids) - found_ids)
        if not_found_ids:
            raise ResourceNotExists(resource=f'todos with ids {not_found_ids}')

        unauthorized_ids = sorted(
            t.id for t in todos if t.created_by_id != created_by_id
        )
        if unauthorized_ids:
            raise UserNotAllowed(
                f'a user can not operate on todos {unauthorized_ids} that were not created by him'
            )
        return todos

    async def batch_complete_todos(
        self,
        session: AsyncSession,
        *,
        todo_ids: list[int],
        created_by_id: uuid.UUID,
    ) -> int:
        await self._validate_batch_todo_ownership(
            session, todo_ids=todo_ids, created_by_id=created_by_id
        )
        return await self._repo.batch_update_is_completed(
            session, table_model=Todo, ids=todo_ids, is_completed=True
        )

    async def batch_update_todos_status(
        self,
        session: AsyncSession,
        *,
        todo_ids: list[int],
        is_completed: bool,
        created_by_id: uuid.UUID,
    ) -> int:
        await self._validate_batch_todo_ownership(
            session, todo_ids=todo_ids, created_by_id=created_by_id
        )
        return await self._repo.batch_update_is_completed(
            session, table_model=Todo, ids=todo_ids, is_completed=is_completed
        )

    async def batch_delete_todos(
        self,
        session: AsyncSession,
        *,
        todo_ids: list[int],
        created_by_id: uuid.UUID,
    ) -> int:
        await self._validate_batch_todo_ownership(
            session, todo_ids=todo_ids, created_by_id=created_by_id
        )
        return await self._repo.delete_by_ids(
            session, table_model=Todo, ids=todo_ids
        )

    async def get_todo_summary(
        self,
        session: AsyncSession,
        *,
        created_by_id: uuid.UUID,
    ) -> TodoSummary:
        owner_filter = Todo.created_by_id == created_by_id

        total_result = await session.execute(
            select(func.count(Todo.id)).filter(owner_filter)
        )
        total: int = total_result.scalar() or 0

        completed_result = await session.execute(
            select(func.count(Todo.id)).filter(
                and_(owner_filter, Todo.is_completed.is_(True))
            )
        )
        completed: int = completed_result.scalar() or 0
        uncompleted: int = total - completed

        priority_query = (
            select(
                Priority.id.label('priority_id'),
                Priority.name.label('priority_name'),
                func.count(Todo.id).label('count'),
            )
            .outerjoin(Todo, and_(Todo.priority_id == Priority.id, owner_filter))
            .group_by(Priority.id, Priority.name)
            .having(func.count(Todo.id) > 0)
            .order_by(Priority.id)
        )
        priority_result = await session.execute(priority_query)
        by_priority: list[PriorityCount] = [
            PriorityCount(
                priority_id=row.priority_id,
                priority_name=row.priority_name,
                count=row.count,
            )
            for row in priority_result
        ]

        return TodoSummary(
            total=total,
            completed=completed,
            uncompleted=uncompleted,
            by_priority=by_priority,
        )


db_service = DBService()
