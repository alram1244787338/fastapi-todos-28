from typing import Final

import pytest
from pytest_lazyfixture import lazy_fixture
from httpx import AsyncClient

from app.core.config import get_config


config = get_config()

API_TODOS_PREFIX: Final[str] = f'{config.API_V1_STR}/todos'


async def _create_todo(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    content: str,
    priority_id: int,
    categories_ids: list[int],
) -> dict:
    """Helper: POST a new todo and return the response JSON (including the new id)."""
    res = await client.post(
        API_TODOS_PREFIX,
        headers=headers,
        json={
            'content': content,
            'priority_id': priority_id,
            'categories_ids': categories_ids,
        },
    )
    assert res.status_code == 201, f'failed to create todo: {res.text}'
    return res.json()


# ---------------------------------------------------------------------------
# POST /todos/batch/complete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize('headers, data, status_code', [
    (None, {'ids': [1]}, 401),
    (lazy_fixture('user_token_headers'), {'ids': []}, 422),
    (lazy_fixture('user_token_headers'), {'ids': [1, 1]}, 422),
    (lazy_fixture('user_token_headers'), {'ids': [999, 888]}, 404),
    (lazy_fixture('user_token_headers'), {'ids': [2]}, 403),
    (lazy_fixture('user_token_headers'), {'ids': [1, 2]}, 403),
], ids=[
    'unauthorized access',
    'empty ids list',
    'duplicate ids',
    'non-existing ids',
    'another users todo',
    'mixed own and another users todos',
])
async def test_batch_complete_todos_failure(
    client: AsyncClient,
    headers,
    data,
    status_code,
):
    res = await client.post(
        f'{API_TODOS_PREFIX}/batch/complete',
        headers=headers,
        json=data,
    )
    assert res.status_code == status_code


@pytest.mark.asyncio
async def test_batch_complete_todos_success(
    client: AsyncClient,
    user_token_headers: dict[str, str],
):
    # Create two extra todos for user 1 (who already has todo id=1)
    t1 = await _create_todo(
        client, user_token_headers,
        content='Batch todo A', priority_id=1, categories_ids=[1],
    )
    t2 = await _create_todo(
        client, user_token_headers,
        content='Batch todo B', priority_id=2, categories_ids=[1],
    )
    new_ids = [t1['id'], t2['id']]

    # Batch-complete the two new todos
    res = await client.post(
        f'{API_TODOS_PREFIX}/batch/complete',
        headers=user_token_headers,
        json={'ids': new_ids},
    )
    assert res.status_code == 200
    assert res.json() == {'affected': 2}

    # Verify they are now completed
    res = await client.get(API_TODOS_PREFIX, headers=user_token_headers)
    assert res.status_code == 200
    completed_ids = {t['id'] for t in res.json() if t['is_completed']}
    assert set(new_ids).issubset(completed_ids)


# ---------------------------------------------------------------------------
# POST /todos/batch/update-status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize('headers, data, status_code', [
    (None, {'ids': [1], 'is_completed': True}, 401),
    (lazy_fixture('user_token_headers'), {'ids': [], 'is_completed': True}, 422),
    (lazy_fixture('user_token_headers'), {'ids': [999], 'is_completed': True}, 404),
    (lazy_fixture('user_token_headers'), {'ids': [2], 'is_completed': True}, 403),
], ids=[
    'unauthorized access',
    'empty ids list',
    'non-existing ids',
    'another users todo',
])
async def test_batch_update_status_failure(
    client: AsyncClient,
    headers,
    data,
    status_code,
):
    res = await client.post(
        f'{API_TODOS_PREFIX}/batch/update-status',
        headers=headers,
        json=data,
    )
    assert res.status_code == status_code


@pytest.mark.asyncio
async def test_batch_update_status_success(
    client: AsyncClient,
    user_token_headers: dict[str, str],
):
    t1 = await _create_todo(
        client, user_token_headers,
        content='Status todo A', priority_id=1, categories_ids=[1],
    )
    t2 = await _create_todo(
        client, user_token_headers,
        content='Status todo B', priority_id=2, categories_ids=[1],
    )
    new_ids = [t1['id'], t2['id']]

    # Mark as completed
    res = await client.post(
        f'{API_TODOS_PREFIX}/batch/update-status',
        headers=user_token_headers,
        json={'ids': new_ids, 'is_completed': True},
    )
    assert res.status_code == 200
    assert res.json() == {'affected': 2}

    # Verify completed
    res = await client.get(API_TODOS_PREFIX, headers=user_token_headers)
    assert res.status_code == 200
    for t in res.json():
        if t['id'] in new_ids:
            assert t['is_completed'] is True

    # Mark back as uncompleted
    res = await client.post(
        f'{API_TODOS_PREFIX}/batch/update-status',
        headers=user_token_headers,
        json={'ids': new_ids, 'is_completed': False},
    )
    assert res.status_code == 200
    assert res.json() == {'affected': 2}

    # Verify uncompleted
    res = await client.get(API_TODOS_PREFIX, headers=user_token_headers)
    assert res.status_code == 200
    for t in res.json():
        if t['id'] in new_ids:
            assert t['is_completed'] is False


# ---------------------------------------------------------------------------
# DELETE /todos/batch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize('headers, data, status_code', [
    (None, {'ids': [1]}, 401),
    (lazy_fixture('user_token_headers'), {'ids': []}, 422),
    (lazy_fixture('user_token_headers'), {'ids': [999]}, 404),
    (lazy_fixture('user_token_headers'), {'ids': [2]}, 403),
    (lazy_fixture('user_token_headers'), {'ids': [1, 2]}, 403),
], ids=[
    'unauthorized access',
    'empty ids list',
    'non-existing ids',
    'another users todo',
    'mixed own and another users todos',
])
async def test_batch_delete_todos_failure(
    client: AsyncClient,
    headers,
    data,
    status_code,
):
    res = await client.request(
        'DELETE',
        f'{API_TODOS_PREFIX}/batch',
        headers=headers,
        json=data,
    )
    assert res.status_code == status_code


@pytest.mark.asyncio
async def test_batch_delete_todos_success(
    client: AsyncClient,
    user_token_headers: dict[str, str],
):
    t1 = await _create_todo(
        client, user_token_headers,
        content='Delete todo A', priority_id=1, categories_ids=[1],
    )
    t2 = await _create_todo(
        client, user_token_headers,
        content='Delete todo B', priority_id=2, categories_ids=[1],
    )
    new_ids = [t1['id'], t2['id']]

    # Batch delete the two new todos
    res = await client.request(
        'DELETE',
        f'{API_TODOS_PREFIX}/batch',
        headers=user_token_headers,
        json={'ids': new_ids},
    )
    assert res.status_code == 204

    # Verify they are gone
    res = await client.get(API_TODOS_PREFIX, headers=user_token_headers)
    assert res.status_code == 200
    remaining_ids = {t['id'] for t in res.json()}
    assert not set(new_ids).intersection(remaining_ids)


# ---------------------------------------------------------------------------
# GET /todos/summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize('headers, status_code', [
    (None, 401),
], ids=['unauthorized access'])
async def test_get_todo_summary_failure(
    client: AsyncClient,
    headers,
    status_code,
):
    res = await client.get(f'{API_TODOS_PREFIX}/summary', headers=headers)
    assert res.status_code == status_code


@pytest.mark.asyncio
async def test_get_todo_summary_success(
    client: AsyncClient,
    user_token_headers: dict[str, str],
):
    # User 1 starts with 1 todo (id=1, priority Medium, not completed).
    # Create 2 more to have a known distribution:
    #   - Low priority, not completed
    #   - Medium priority, not completed
    await _create_todo(
        client, user_token_headers,
        content='Summary todo Low', priority_id=1, categories_ids=[1],
    )
    await _create_todo(
        client, user_token_headers,
        content='Summary todo Med', priority_id=2, categories_ids=[1],
    )

    res = await client.get(f'{API_TODOS_PREFIX}/summary', headers=user_token_headers)
    assert res.status_code == 200

    data = res.json()
    assert data['total'] == 3
    assert data['completed'] == 0
    assert data['uncompleted'] == 3

    # by_priority should have one entry per priority that has todos
    by_priority = data['by_priority']
    assert len(by_priority) == 2
    # Total count across all priorities must equal total
    assert sum(p['count'] for p in by_priority) == 3

    # Each entry must have the expected shape
    for entry in by_priority:
        assert 'priority_id' in entry
        assert 'priority_name' in entry
        assert 'count' in entry
        assert entry['count'] >= 1

    # Verify the specific priority distribution
    priority_map = {p['priority_name']: p['count'] for p in by_priority}
    assert priority_map.get('Low') == 1
    assert priority_map.get('Medium') == 2


@pytest.mark.asyncio
async def test_get_todo_summary_with_completed(
    client: AsyncClient,
    user_token_headers: dict[str, str],
):
    """Verify summary counts reflect completed status after batch operations."""
    # User 1 starts with 1 uncompleted todo (id=1, Medium priority).
    # Create one more and complete it.
    t = await _create_todo(
        client, user_token_headers,
        content='Summary completed todo', priority_id=1, categories_ids=[1],
    )

    # Mark the new todo as completed via batch
    res = await client.post(
        f'{API_TODOS_PREFIX}/batch/complete',
        headers=user_token_headers,
        json={'ids': [t['id']]},
    )
    assert res.status_code == 200

    res = await client.get(f'{API_TODOS_PREFIX}/summary', headers=user_token_headers)
    assert res.status_code == 200

    data = res.json()
    assert data['total'] == 2
    assert data['completed'] == 1
    assert data['uncompleted'] == 1
