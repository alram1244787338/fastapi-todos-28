from typing import Final

import pytest
from pytest_lazyfixture import lazy_fixture
from httpx import AsyncClient

from tests.conftest_utils import get_tests_data
from app.core.config import get_config


config = get_config()

API_TODOS_PREFIX: Final[str] = f'{config.API_V1_STR}/todos'

# Expected paginated response for user 1's todos (from tests_data.json)
_USER1_TODOS = get_tests_data()['users'][0]['todos']


@pytest.mark.asyncio
@pytest.mark.parametrize('headers, status_code, items, total', [
    (None, 401, None, None),
    (
        lazy_fixture('user_token_headers'),
        200,
        _USER1_TODOS,
        len(_USER1_TODOS)
    )
], ids=['unauthorized access', 'authorized access'])
async def test_get_todos(
    client: AsyncClient,
    headers,
    status_code,
    items,
    total
):
    res = await client.get(API_TODOS_PREFIX, headers=headers)
    assert res.status_code == status_code
    if status_code == 200:
        body = res.json()
        assert body['items'] == items
        assert body['total'] == total
        assert body['skip'] == 0
        assert body['limit'] == 100
    else:
        assert res.json() == {'detail': 'Unauthorized'}


@pytest.mark.asyncio
@pytest.mark.parametrize('headers, data, status_code, res_body', [
    (None, {}, 401, {'detail': 'Unauthorized'}),
    (
        lazy_fixture('user_token_headers'),
        {'content': 'Play Smash Bros', 'priority_id': 1, 'categories_ids': [1, 4]},
        400,
        {'detail': 'categories are not valid'}
    ),
    (
        lazy_fixture('user_token_headers'),
        {'content': 'Play Smash Bros', 'priority_id': 1, 'categories_ids': [1, 1]},
        400,
        {'detail': 'categories are not valid'}
    ),
    (
        lazy_fixture('user_token_headers'),
        {'content': 'Play Smash Bros', 'priority_id': 1, 'categories_ids': [1, 8]},
        400,
        {'detail': 'categories are not valid'}
    ),
    (
        lazy_fixture('user_token_headers'),
        {'content': 'Play Smash Bros', 'priority_id': 4, 'categories_ids': [1, 2]},
        400,
        {'detail': 'priority is not valid'}
    ),
    (
        lazy_fixture('user_token_headers'),
        {'content': 'Play Smash Bros', 'priority_id': 1, 'categories_ids': [1, 3]},
        201,
        {
            # id is 7 because the initial test data inserts 5 todos (1-5),
            # and the 'authorized access non existing priority' test case
            # above promotes the primary key by consuming one sequence value.
            'id': 7,
            'is_completed': False,
            'content': 'Play Smash Bros',
            'priority': {'id': 1, 'name': 'Low'},
            'categories': [
                {
                    'id': 1,
                    'name': 'Personal'
                },
                {
                    'id': 3,
                    'name': 'Chess'
                }
            ]
        }
    ),
], ids=[
    'unauthorized access',
    'authorized access another users category',
    'authorized access duplicate valid category',
    'authorized access non existing category',
    'authorized access non existing priority',
    'authorized access valid data'
])
async def test_add_todo(
    client: AsyncClient,
    headers,
    data,
    status_code,
    res_body
):
    res = await client.post(API_TODOS_PREFIX, headers=headers, json=data)
    assert res.status_code == status_code
    assert res.json() == res_body


@pytest.mark.asyncio
@pytest.mark.parametrize('headers, todo_id, data, status_code, res_body', [
    (None, 1, {}, 401, {'detail': 'Unauthorized'}),
    (
        lazy_fixture('user_token_headers'),
        999,
        {'content': 'Learn the sicilian', 'is_completed': True, 'priority_id': 3, 'categories_ids': [2]},
        404,
        {'detail': 'todo does not exist'}
    ),
    (
        lazy_fixture('user_token_headers'),
        2,
        {'content': 'Learn the sicilian', 'is_completed': True, 'priority_id': 3, 'categories_ids': [2]},
        403,
        {'detail': 'a user can not update a todo that was not created by him'}
    ),
    (
        lazy_fixture('user_token_headers'),
        1,
        {'content': 'Learn the sicilian opening', 'is_completed': True, 'priority_id': 2, 'categories_ids': [1, 4]},
        400,
        {'detail': 'categories are not valid'}
    ),
    (
        lazy_fixture('user_token_headers'),
        1,
        {'content': 'Learn the sicilian opening', 'is_completed': True, 'priority_id': 2, 'categories_ids': [1, 1]},
        400,
        {'detail': 'categories are not valid'}
    ),
    (
        lazy_fixture('user_token_headers'),
        1,
        {'content': 'Learn the sicilian opening', 'is_completed': True, 'priority_id': 2, 'categories_ids': [1, 8]},
        400,
        {'detail': 'categories are not valid'}
    ),
    (
        lazy_fixture('user_token_headers'),
        1,
        {'content': 'Learn the sicilian opening', 'is_completed': True, 'priority_id': 5, 'categories_ids': [2]},
        400,
        {'detail': 'priority is not valid'}
    ),
    (
        lazy_fixture('user_token_headers'),
        1,
        {'content': 'Learn the sicilian', 'is_completed': True, 'priority_id': 1, 'categories_ids': [2]},
        200,
        {
            'id': 1,
            'is_completed': True,
            'content': 'Learn the sicilian',
            'priority': {'id': 1, 'name': 'Low'},
            'categories': [
                {
                    'id': 2,
                    'name': 'Work'
                }
            ]
        }
    )

], ids=[
    'unauthorized access',
    'authorized access non existing todo',
    'authorized access another users todo',
    'authorized access another users category',
    'authorized access duplicate valid category',
    'authorized access non existing category',
    'authorized access non existing priority',
    'authorized access valid data'
])
async def test_update_todo(
    client: AsyncClient,
    headers,
    todo_id,
    data,
    status_code,
    res_body
):
    res = await client.put(f'{API_TODOS_PREFIX}/{todo_id}', headers=headers, json=data)
    assert res.status_code == status_code
    assert res.json() == res_body


@pytest.mark.asyncio
@pytest.mark.parametrize('headers, todo_id, status_code, res_body', [
    (None, 1, 401, {'detail': 'Unauthorized'}),
    (lazy_fixture('user_token_headers'), 999, 404, {'detail': 'todo does not exist'}),
    (
        lazy_fixture('user_token_headers'),
        2,
        403,
        {'detail': 'a user can not delete a todo that was not created by him'}
    )
], ids=[
    'unauthorized access',
    'authorized access non existing todo',
    'authorized access another users todo'
])
async def test_delete_todo_failure(
    client: AsyncClient,
    headers,
    todo_id,
    status_code,
    res_body
):
    res = await client.delete(f'{API_TODOS_PREFIX}/{todo_id}', headers=headers)
    assert res.status_code == status_code
    assert res.json() == res_body


@pytest.mark.asyncio
async def test_delete_todo_success(
    client: AsyncClient,
    user_token_headers: dict[str, str]
):
    res = await client.delete(f'{API_TODOS_PREFIX}/1', headers=user_token_headers)
    assert res.status_code == 204
    assert len(res.content) == 0


# ============================================================
# Filter & pagination tests
# ============================================================

@pytest.mark.asyncio
async def test_get_todos_filter_by_is_completed(
    client: AsyncClient,
    user_token_headers: dict[str, str]
):
    # user 1 has 2 incomplete (ids 1, 4) and 2 complete (ids 3, 5)
    res = await client.get(
        f'{API_TODOS_PREFIX}?is_completed=false',
        headers=user_token_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body['total'] == 2
    assert len(body['items']) == 2
    contents = {item['content'] for item in body['items']}
    assert contents == {'Learn the sicilian opening', 'Review work project'}
    assert all(item['is_completed'] is False for item in body['items'])

    res = await client.get(
        f'{API_TODOS_PREFIX}?is_completed=true',
        headers=user_token_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body['total'] == 2
    contents = {item['content'] for item in body['items']}
    assert contents == {'Practice endgames', 'Buy groceries'}


@pytest.mark.asyncio
async def test_get_todos_filter_by_priority_id(
    client: AsyncClient,
    user_token_headers: dict[str, str]
):
    # user 1: priority 1 (Low) → ids 3, 4; priority 2 (Medium) → ids 1, 5
    res = await client.get(
        f'{API_TODOS_PREFIX}?priority_id=1',
        headers=user_token_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body['total'] == 2
    contents = {item['content'] for item in body['items']}
    assert contents == {'Practice endgames', 'Review work project'}

    res = await client.get(
        f'{API_TODOS_PREFIX}?priority_id=2',
        headers=user_token_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body['total'] == 2
    contents = {item['content'] for item in body['items']}
    assert contents == {'Learn the sicilian opening', 'Buy groceries'}


@pytest.mark.asyncio
async def test_get_todos_filter_by_category_id(
    client: AsyncClient,
    user_token_headers: dict[str, str]
):
    # user 1: category 1 (Personal) → ids 1, 5; category 3 (Chess) → ids 1, 3; category 2 (Work) → id 4
    res = await client.get(
        f'{API_TODOS_PREFIX}?category_id=3',
        headers=user_token_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body['total'] == 2
    contents = {item['content'] for item in body['items']}
    assert contents == {'Learn the sicilian opening', 'Practice endgames'}

    res = await client.get(
        f'{API_TODOS_PREFIX}?category_id=2',
        headers=user_token_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body['total'] == 1
    assert body['items'][0]['content'] == 'Review work project'


@pytest.mark.asyncio
async def test_get_todos_filter_by_search(
    client: AsyncClient,
    user_token_headers: dict[str, str]
):
    # search for 'sicilian' → only id 1
    res = await client.get(
        f'{API_TODOS_PREFIX}?search=sicilian',
        headers=user_token_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body['total'] == 1
    assert body['items'][0]['content'] == 'Learn the sicilian opening'

    # case-insensitive: search 'PRACTICE'
    res = await client.get(
        f'{API_TODOS_PREFIX}?search=PRACTICE',
        headers=user_token_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body['total'] == 1
    assert body['items'][0]['content'] == 'Practice endgames'


@pytest.mark.asyncio
async def test_get_todos_combined_filters(
    client: AsyncClient,
    user_token_headers: dict[str, str]
):
    # is_completed=false AND priority_id=1 → only id 4 (Review work project)
    res = await client.get(
        f'{API_TODOS_PREFIX}?is_completed=false&priority_id=1',
        headers=user_token_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body['total'] == 1
    assert body['items'][0]['content'] == 'Review work project'

    # is_completed=true AND category_id=1 → only id 5 (Buy groceries)
    res = await client.get(
        f'{API_TODOS_PREFIX}?is_completed=true&category_id=1',
        headers=user_token_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body['total'] == 1
    assert body['items'][0]['content'] == 'Buy groceries'

    # is_completed=false AND priority_id=1 AND search='review' → id 4
    res = await client.get(
        f'{API_TODOS_PREFIX}?is_completed=false&priority_id=1&search=review',
        headers=user_token_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body['total'] == 1
    assert body['items'][0]['content'] == 'Review work project'


@pytest.mark.asyncio
async def test_get_todos_no_results(
    client: AsyncClient,
    user_token_headers: dict[str, str]
):
    # is_completed=true AND priority_id=1 AND category_id=1 → no match
    # (id 5 is completed+priority2+category1; id 3 is completed+priority1+category3)
    res = await client.get(
        f'{API_TODOS_PREFIX}?is_completed=true&priority_id=1&category_id=1',
        headers=user_token_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body['total'] == 0
    assert body['items'] == []

    # search for non-existing keyword
    res = await client.get(
        f'{API_TODOS_PREFIX}?search=nonexistent_todo_content',
        headers=user_token_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body['total'] == 0
    assert body['items'] == []


@pytest.mark.asyncio
async def test_get_todos_pagination(
    client: AsyncClient,
    user_token_headers: dict[str, str]
):
    # user 1 has 4 todos; paginate with limit=2
    res = await client.get(
        f'{API_TODOS_PREFIX}?skip=0&limit=2',
        headers=user_token_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body['total'] == 4
    assert len(body['items']) == 2
    assert body['skip'] == 0
    assert body['limit'] == 2

    # second page
    res = await client.get(
        f'{API_TODOS_PREFIX}?skip=2&limit=2',
        headers=user_token_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body['total'] == 4
    assert len(body['items']) == 2
    assert body['skip'] == 2
    assert body['limit'] == 2

    # skip beyond total → empty items but total still 4
    res = await client.get(
        f'{API_TODOS_PREFIX}?skip=10&limit=2',
        headers=user_token_headers
    )
    assert res.status_code == 200
    body = res.json()
    assert body['total'] == 4
    assert body['items'] == []


@pytest.mark.asyncio
async def test_get_todos_filter_only_own_todos(
    client: AsyncClient,
    user_token_headers: dict[str, str]
):
    # Even with no filters, only user 1's 4 todos are returned (not user 2's)
    res = await client.get(API_TODOS_PREFIX, headers=user_token_headers)
    assert res.status_code == 200
    body = res.json()
    assert body['total'] == 4
    # Ensure user 2's todo is never included
    all_contents = [item['content'] for item in body['items']]
    assert 'Grind mario kart online' not in all_contents
