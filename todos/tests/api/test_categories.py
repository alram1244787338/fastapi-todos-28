import pytest
from pytest_lazyfixture import lazy_fixture
from httpx import AsyncClient

from tests.conftest_utils import get_tests_data
from app.core.config import get_config


config = get_config()


def _expected_user_categories(user_index: int = 0):
    # builds the enriched category list the API is expected to return for a user:
    # the system default categories plus the user's own ones, each annotated with
    # is_default and the amount of that user's todos attached to it, ordered by id.
    data = get_tests_data()
    user = data['users'][user_index]

    def todos_count(category_id):
        return sum(
            1
            for todo in user['todos']
            for category in todo['categories']
            if category['id'] == category_id
        )

    default_categories = [
        {'id': c['id'], 'name': c['name'], 'is_default': True, 'todos_count': todos_count(c['id'])}
        for c in data['categories']
    ]
    own_categories = [
        {'id': c['id'], 'name': c['name'], 'is_default': False, 'todos_count': todos_count(c['id'])}
        for c in user['categories']
    ]
    categories = default_categories + own_categories
    categories.sort(key=lambda category: category['id'])
    return categories


@pytest.mark.asyncio
@pytest.mark.parametrize('headers, status_code, res_body', [
    (None, 401, {'detail': 'Unauthorized'}),
    (
        lazy_fixture('user_token_headers'),
        200,
        _expected_user_categories()
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
@pytest.mark.parametrize('headers, category_id, status_code, res_body', [
    (None, 1, 401, {'detail': 'Unauthorized'}),
    (
        lazy_fixture('user_token_headers'),
        1,
        200,
        {'id': 1, 'name': 'Personal', 'is_default': True, 'todos_count': 1}
    ),
    (
        lazy_fixture('user_token_headers'),
        2,
        200,
        {'id': 2, 'name': 'Work', 'is_default': True, 'todos_count': 0}
    ),
    (
        lazy_fixture('user_token_headers'),
        3,
        200,
        {'id': 3, 'name': 'Chess', 'is_default': False, 'todos_count': 1}
    ),
    (lazy_fixture('user_token_headers'), 4, 404, {'detail': 'category does not exist'}),
    (lazy_fixture('user_token_headers'), 999, 404, {'detail': 'category does not exist'})
], ids=[
    'unauthorized access',
    'authorized access default category',
    'authorized access default category with no todos',
    'authorized access own category',
    'authorized access another users category',
    'authorized access non existing category'
])
async def test_get_category(
    client: AsyncClient,
    headers,
    category_id,
    status_code,
    res_body
):
    res = await client.get(f'{config.API_V1_STR}/categories/{category_id}', headers=headers)
    assert res.status_code == status_code
    assert res.json() == res_body


@pytest.mark.asyncio
@pytest.mark.parametrize('headers, data, status_code, res_body', [
    (None, {'name': 'Work'}, 401, {'detail': 'Unauthorized'}),
    (lazy_fixture('user_token_headers'), {'name': 'Personal'}, 409, {'detail': 'category name already exists'}),
    (lazy_fixture('user_token_headers'), {'name': 'Chess'}, 409, {'detail': 'category name already exists'}),
    (lazy_fixture('user_token_headers'), {'name': 'Nintendo'}, 201, {'name': 'Nintendo', 'id': 5})
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
    (None, 3, {'name': 'Strategy'}, 401, {'detail': 'Unauthorized'}),
    (
        lazy_fixture('user_token_headers'),
        999,
        {'name': 'Strategy'},
        404,
        {'detail': 'category does not exist'}
    ),
    (
        lazy_fixture('user_token_headers'),
        1,
        {'name': 'Strategy'},
        403,
        {'detail': 'a user can not update a category that was not created by him'}
    ),
    (
        lazy_fixture('user_token_headers'),
        4,
        {'name': 'Strategy'},
        403,
        {'detail': 'a user can not update a category that was not created by him'}
    ),
    (
        lazy_fixture('user_token_headers'),
        3,
        {'name': 'Work'},
        409,
        {'detail': 'category name already exists'}
    ),
    (
        lazy_fixture('user_token_headers'),
        3,
        {'name': 'Personal'},
        409,
        {'detail': 'category name already exists'}
    )
], ids=[
    'unauthorized access',
    'authorized access non existing category',
    'authorized access default existing category',
    'authorized access another users existing category',
    'authorized access rename to existing default category',
    'authorized access rename to another existing default category'
])
async def test_update_category_failure(
    client: AsyncClient,
    headers,
    category_id,
    data,
    status_code,
    res_body
):
    res = await client.patch(
        f'{config.API_V1_STR}/categories/{category_id}',
        headers=headers,
        json=data
    )
    assert res.status_code == status_code
    assert res.json() == res_body


@pytest.mark.asyncio
@pytest.mark.parametrize('category_id, data, res_body', [
    (3, {'name': 'Strategy'}, {'id': 3, 'name': 'Strategy'}),
    (3, {'name': 'Chess'}, {'id': 3, 'name': 'Chess'})
], ids=['rename own category', 'rename own category to its current name'])
async def test_update_category_success(
    client: AsyncClient,
    user_token_headers: dict[str, str],
    category_id,
    data,
    res_body
):
    res = await client.patch(
        f'{config.API_V1_STR}/categories/{category_id}',
        headers=user_token_headers,
        json=data
    )
    assert res.status_code == 200
    assert res.json() == res_body


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
