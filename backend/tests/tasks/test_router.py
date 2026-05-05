from httpx import AsyncClient


async def test_list_tasks_empty(client: AsyncClient):
    response = await client.get("/api/v1/tasks/")
    assert response.status_code == 200
    assert response.json() == []


async def test_create_task_minimal(client: AsyncClient):
    response = await client.post("/api/v1/tasks/", json={"title": "My task"})
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "My task"
    assert data["status"] == "pending"
    assert data["description"] is None
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


async def test_create_task_full(client: AsyncClient):
    response = await client.post(
        "/api/v1/tasks/",
        json={"title": "Full", "description": "Some desc", "status": "in_progress"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["description"] == "Some desc"
    assert data["status"] == "in_progress"


async def test_create_task_invalid_status(client: AsyncClient):
    response = await client.post(
        "/api/v1/tasks/", json={"title": "X", "status": "unknown"}
    )
    assert response.status_code == 422


async def test_create_task_missing_title(client: AsyncClient):
    response = await client.post("/api/v1/tasks/", json={})
    assert response.status_code == 422


async def test_list_tasks(client: AsyncClient):
    await client.post("/api/v1/tasks/", json={"title": "Task 1"})
    await client.post("/api/v1/tasks/", json={"title": "Task 2"})

    response = await client.get("/api/v1/tasks/")
    assert response.status_code == 200
    titles = [t["title"] for t in response.json()]
    assert "Task 1" in titles
    assert "Task 2" in titles


async def test_get_task(client: AsyncClient):
    created = (await client.post("/api/v1/tasks/", json={"title": "Find me"})).json()

    response = await client.get(f"/api/v1/tasks/{created['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


async def test_get_task_not_found(client: AsyncClient):
    response = await client.get("/api/v1/tasks/99999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


async def test_update_task(client: AsyncClient):
    created = (await client.post("/api/v1/tasks/", json={"title": "Old"})).json()

    response = await client.patch(
        f"/api/v1/tasks/{created['id']}",
        json={"title": "New", "status": "done"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New"
    assert data["status"] == "done"


async def test_update_task_partial(client: AsyncClient):
    created = (
        await client.post(
            "/api/v1/tasks/", json={"title": "Task", "description": "Desc"}
        )
    ).json()

    response = await client.patch(
        f"/api/v1/tasks/{created['id']}",
        json={"status": "in_progress"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Task"
    assert data["description"] == "Desc"
    assert data["status"] == "in_progress"


async def test_update_task_not_found(client: AsyncClient):
    response = await client.patch("/api/v1/tasks/99999", json={"title": "X"})
    assert response.status_code == 404


async def test_delete_task(client: AsyncClient):
    created = (await client.post("/api/v1/tasks/", json={"title": "Delete me"})).json()

    response = await client.delete(f"/api/v1/tasks/{created['id']}")
    assert response.status_code == 204

    assert (await client.get(f"/api/v1/tasks/{created['id']}")).status_code == 404


async def test_delete_task_not_found(client: AsyncClient):
    response = await client.delete("/api/v1/tasks/99999")
    assert response.status_code == 404


async def test_tasks_isolation_between_tests(client: AsyncClient):
    """Each test gets a clean DB state due to transaction rollback."""
    response = await client.get("/api/v1/tasks/")
    assert response.json() == []
