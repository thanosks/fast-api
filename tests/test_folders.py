from datetime import datetime, timezone
from unittest.mock import ANY
import os
import pytest
import sys
from pathlib import Path
from collections.abc import Callable


def assert_folder_response(body):
    from app.schemas.folder import FolderResponse
    FolderResponse.model_validate(body)


def register_folder(client, name, path, description=None, writable=False):
    payload = dict(name=name, path=str(path), description=description, writable=writable)
    response = client.post("/folders", json=payload)

    assert response.status_code == 201
    assert_folder_response(response.json())

    return response


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": os.environ["APP_NAME"]}


def test_create_folder(client, sandbox):
    payload = dict(name="New", path=str(sandbox.photos), description=None, writable=False)

    before = datetime.now(timezone.utc)
    response = client.post("/folders", json=payload)
    after = datetime.now(timezone.utc)

    data = response.json()
    assert_folder_response(data)
    created_at_str = data.pop("created_at")
    created_at = datetime.fromisoformat(created_at_str)

    assert response.status_code == 201
    assert before <= created_at <= after
    assert isinstance(data["id"], int)
    assert data["id"] > 0
    assert data == {**payload, "id": ANY}


@pytest.mark.parametrize(
    "make_path",
    [
        pytest.param(lambda s: s.a_file, id="a_file"),
        pytest.param(lambda s: s.tmp, id="tmp"),
        pytest.param(lambda s: s.root_evil, id="root_evil"),
        pytest.param(lambda s: s.allowed_root / "..", id="parent_traversal"),
        pytest.param(lambda s: s.allowed_root / "nope", id="nonexistent_child"),
    ]
)
def test_create_folder_with_invalid_path_returns_422(client, sandbox, make_path: Callable):
    payload = dict(name="New", path=str(make_path(sandbox)), description=None, writable=False)
    response = client.post("/folders", json=payload)

    assert response.status_code == 422
    assert client.get("/folders").json() == []


@pytest.mark.parametrize(
    "make_body",
    [
        pytest.param(lambda s: {"name": "", "path": str(s.photos)}, id="empty_name"),
        pytest.param(lambda s: {"name": " ", "path": str(s.photos)}, id="blank_name"),
        pytest.param(lambda s: {"name": "a"*101, "path": str(s.photos)}, id="name_too_long"),
        pytest.param(lambda s: {"path": str(s.photos)}, id="missing_name"),
        pytest.param(lambda s: {"name": "Photos"}, id="missing_path"),
        pytest.param(lambda s: {"name": "Photos", "path": str(s.photos), "description": "a"*101}, id="description_too_long"),
    ],
)
def test_create_folder_with_invalid_body_returns_422(client, sandbox, make_body: Callable):
    response = client.post("/folders", json=make_body(sandbox))

    assert response.status_code == 422
    assert client.get("/folders").json() == []


def test_list_folders_empty_store_returns_empty_list(client):
    response = client.get("/folders")
    assert response.status_code == 200
    assert response.json() == []


def test_get_folders(client, sandbox):
    payload_photos = dict(name="Photos", path=str(sandbox.photos), description=None, writable=False)
    payload_docs = dict(name="Docs", path=str(sandbox.docs), description=None, writable=False)

    response_photos = client.post("/folders", json=payload_photos)
    assert response_photos.status_code == 201
    assert_folder_response(response_photos.json())

    response_docs = client.post("/folders", json=payload_docs)
    assert response_docs.status_code == 201
    assert_folder_response(response_docs.json())

    response = client.get("/folders")
    data = response.json()

    for d in data:
        assert_folder_response(d)

    assert response.status_code == 200
    assert {d["name"] for d in data} == {"Photos", "Docs"}
    assert len(data) == 2


def test_get_folder_by_id_returns_folder(client, sandbox):
    payload = dict(name="New", path=str(sandbox.photos), description=None, writable=False)

    response = client.post("/folders", json=payload)
    assert_folder_response(response.json())
    response_id = response.json()['id']

    folder_response = client.get(f"/folders/{response_id}")
    assert_folder_response(folder_response.json())

    assert folder_response.status_code == 200
    assert response.json() == folder_response.json()


@pytest.mark.parametrize(
    "folder_id, expected_status",
    [
        pytest.param(999, 404, id="unknown_id"),
        pytest.param("abc", 422, id="not_a_number"),
    ],
)
def test_get_folder_with_invalid_id_returns_error_status(client, folder_id: int | str, expected_status:  int | str):
    folder_response = client.get(f"/folders/{folder_id}")

    assert folder_response.status_code == expected_status


def test_create_folder_with_duplicate_path_returns_409(client, sandbox):
    payload = dict(name="New", path=str(sandbox.photos), description=None, writable=False)
    response = client.post("/folders", json=payload)

    assert response.status_code == 201

    response = client.post("/folders", json=payload)

    assert response.status_code == 409

    payload = dict(name="New_1", path=str(sandbox.photos), description=None, writable=False)
    response = client.post("/folders", json=payload)

    assert response.status_code == 409
    assert len(client.get("/folders").json()) == 1


@pytest.mark.skipif(sys.platform != "win32", reason="Path comparison is case-insensitive only on Windows")
def test_create_folder_with_duplicate_path_in_different_case_returns_409(client, sandbox):
    payload = dict(name="New", path=str(sandbox.photos), description=None, writable=False)
    response = client.post("/folders", json=payload)

    assert response.status_code == 201

    cap_path = str(sandbox.photos.parent / sandbox.photos.name.upper())
    payload = dict(name="New", path=cap_path, description=None, writable=False)
    response = client.post("/folders", json=payload)

    assert response.status_code == 409
    assert len(client.get("/folders").json()) == 1


def test_folder_patch_writable(client, sandbox):
    response = register_folder(client, "New", sandbox.photos)

    response_id = response.json()['id']

    patch_response = client.patch(f"/folders/{response_id}", json=dict(writable=True))

    assert patch_response.status_code == 200

    assert_folder_response(patch_response.json())

