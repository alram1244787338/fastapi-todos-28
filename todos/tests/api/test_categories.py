import pytest
from pytest_lazyfixture import lazy_fixture
from httpx import AsyncClient

from tests.conftest_utils import get_tests_data
from app.core.config import get_config


config = get_config()


# Build expected categories with todos_count and is_default
_SYSTEM_CATEGORIES = [
    {'id': 1, 'name': 'Personal', 'todos_count': 1, 'is_default': True},
    {'id': 2, 'name': 'Work', 'todos_count': 0, 'is_default': True},
]
_USER1_CATEGORIES = [
    {'id': 3, 'name': 'Chess', 'todos_count': 1, 'is_default': False},
]


@pytest.mark.asyncio
@pytest.mark.parametrize('headers, status_code, res_body', [
    (None, 401, {'detail': 'Unauthorized'}),
    (
        lazy_fixture('user_token_headers'),
        200,
        _SYSTEM_CATEGORIES + _USER1_CATEGORIES
    )
], ids=['unauthorized access', 'authorized access'])
async def test_get_categories(
    client: AsyncClient,
    headers,
    status_code,
    res_body
):
    res = await client.get(f'{config.API_V1_STR}/categories', headers=headers)
    assert res.status_code == status_code
    assert res.json() == res_body


@pytest.mark.asyncio
@pytest.mark.parametrize('headers, data, status_code, res_body', [
    (None, {'name': 'Work'}, 401, {'detail': 'Unauthorized'}),
    (lazy_fixture('user_token_headers'), {'name': 'Personal'}, 409, {'detail': 'category name already exists'}),
    (lazy_fixture('user_token_headers'), {'name': 'Chess'}, 409, {'detail': 'category name already exists'}),
    (
        lazy_fixture('user_token_headers'),
        {'name': 'Nintendo'},
        201,
        {'id': 5, 'name': 'Nintendo', 'todos_count': 0, 'is_default': False}
    )
], ids=[
    'unauthorized access',
    'authorized access default existing category',
    'authorized access another users existing category',
    'authorized access non existing category'
])
async def test_add_category(
    client: AsyncClient,
    headers,
    data,
    status_code,
    res_body
):
    res = await client.post(f'{config.API_V1_STR}/categories', headers=headers, json=data)
    assert res.status_code == status_code
    assert res.json() == res_body


@pytest.mark.asyncio
@pytest.mark.parametrize('headers, category_id, data, status_code, res_body', [
    (None, 3, {'name': 'Go'}, 401, {'detail': 'Unauthorized'}),
    (
        lazy_fixture('user_token_headers'),
        999,
        {'name': 'Go'},
        404,
        {'detail': 'category does not exist'}
    ),
    (
        lazy_fixture('user_token_headers'),
        1,
        {'name': 'RenamedPersonal'},
        403,
        {'detail': 'a user can not update a category that was not created by him'}
    ),
    (
        lazy_fixture('user_token_headers'),
        4,
        {'name': 'RenamedNintendo'},
        403,
        {'detail': 'a user can not update a category that was not created by him'}
    ),
    (
        lazy_fixture('user_token_headers'),
        3,
        {'name': 'Personal'},
        409,
        {'detail': 'category name already exists'}
    ),
    (
        lazy_fixture('user_token_headers'),
        3,
        {'name': 'Work'},
        409,
        {'detail': 'category name already exists'}
    )
], ids=[
    'unauthorized access',
    'authorized access non existing category',
    'authorized access default category',
    'authorized access another users category',
    'authorized access rename to existing default name',
    'authorized access rename to another existing default name'
])
async def test_update_category_failure(
    client: AsyncClient,
    headers,
    category_id,
    data,
    status_code,
    res_body
):
    res = await client.put(
        f'{config.API_V1_STR}/categories/{category_id}',
        headers=headers,
        json=data
    )
    assert res.status_code == status_code
    assert res.json() == res_body


@pytest.mark.asyncio
async def test_update_category_success(
    client: AsyncClient,
    user_token_headers: dict[str, str]
):
    res = await client.put(
        f'{config.API_V1_STR}/categories/3',
        headers=user_token_headers,
        json={'name': 'Go'}
    )
    assert res.status_code == 200
    assert res.json() == {'id': 3, 'name': 'Go', 'todos_count': 1, 'is_default': False}


@pytest.mark.asyncio
@pytest.mark.parametrize('headers, category_id, status_code, res_body', [
    (None, 1, 401, {'detail': 'Unauthorized'}),
    (lazy_fixture('user_token_headers'), 5, 404, {'detail': 'category does not exist'}),
    (
        lazy_fixture('user_token_headers'),
        1,
        403,
        {'detail': 'a user can not delete a category that was not created by him'}
    ),
    (
        lazy_fixture('user_token_headers'),
        4,
        403,
        {'detail': 'a user can not delete a category that was not created by him'}
    )
], ids=[
    'unauthorized access',
    'authorized access non existing category',
    'authorized access default existing category',
    'authorized access another users existing category'
])
async def test_delete_category_failure(
    client: AsyncClient,
    headers,
    category_id,
    status_code,
    res_body
):
    res = await client.delete(f'{config.API_V1_STR}/categories/{category_id}', headers=headers)
    assert res.status_code == status_code
    assert res.json() == res_body


@pytest.mark.asyncio
async def test_delete_category_success(
    client: AsyncClient,
    user_token_headers: dict[str, str]
):
    res = await client.delete(f'{config.API_V1_STR}/categories/3', headers=user_token_headers)
    assert res.status_code == 204
    assert len(res.content) == 0
