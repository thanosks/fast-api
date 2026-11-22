from datetime import datetime, timezone
from unittest.mock import ANY
import os
import pytest
import sys
from pathlib import Path
from collections.abc import Callable


INVALID_PATHS = [
    pytest.param(lambda s: s.a_file, id="a_file"),
    pytest.param(lambda s: s.tmp, id="tmp"),
    pytest.param(lambda s: s.root_evil, id="root_evil"),
    pytest.param(lambda s: s.allowed_root / "..", id="parent_traversal"),
    pytest.param(lambda s: s.allowed_root / "nope", id="nonexistent_child"),
]


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


@pytest.mark.parametrize("make_path", INVALID_PATHS)
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
    folder_id = response.json()['id']

    folder_response = client.get(f"/folders/{folder_id}")
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
def test_get_folder_with_invalid_id_returns_error_status(client, folder_id: int | str, expected_status:  int):
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


@pytest.mark.parametrize(
    "field, new_value",
    [
        pytest.param("writable", True, id="Writable"),
        pytest.param("name", "Renamed_New", id="Rename"),
        pytest.param("description", "A note", id="Description"),
    ],
)
def test_patch_folder_updates_only_the_given_field(client, sandbox, field: str, new_value):
    response = register_folder(client, "New", sandbox.photos)
    data = response.json()

    folder_id = data['id']

    patch_response = client.patch(f"/folders/{folder_id}", json={field: new_value})
    patched_data = patch_response.json()

    assert patch_response.status_code == 200

    assert_folder_response(patched_data)

    assert patched_data[field] == new_value

    for key in data:
        if key == field:
            continue

        assert data[key] == patched_data[key]


def test_patch_folder_change_is_persisted(client, sandbox):
    response = register_folder(client, "New", sandbox.photos)
    data = response.json()

    folder_id = data['id']

    patch_response = client.patch(f"/folders/{folder_id}", json={"name": "Rename_New"})

    get_response = client.get(f"/folders/{folder_id}")

    assert_folder_response(get_response.json())
    assert patch_response.json() == get_response.json()
    assert get_response.json()["name"] == "Rename_New"


def test_patch_folder_with_empty_body_changes_nothing(client, sandbox):
    response = register_folder(client, "New", sandbox.photos)
    data = response.json()

    folder_id = data['id']

    patch_response = client.patch(f"/folders/{folder_id}", json={})

    assert patch_response.status_code == 200
    assert patch_response.json() == data


def test_patch_folder_with_own_path_returns_200(client, sandbox):
    response = register_folder(client, "New", sandbox.photos)
    data = response.json()

    folder_id = data['id']

    patch_response = client.patch(f"/folders/{folder_id}", json={"path": str(sandbox.photos)})

    assert patch_response.status_code == 200
    assert patch_response.json()["path"] == data["path"]


def test_patch_folder_with_other_folders_path_returns_409(client, sandbox):
    photos_response = register_folder(client, "Photos", sandbox.photos)
    docs_response = register_folder(client, "Docs", sandbox.docs)

    docs_data = docs_response.json()
    docs_folder_id = docs_data['id']

    patch_response = client.patch(f"/folders/{docs_folder_id}", json={"path": str(sandbox.photos)})

    assert patch_response.status_code == 409

    docs_get_folder_response = client.get(f"/folders/{docs_folder_id}")

    assert docs_get_folder_response.json() == docs_data


@pytest.mark.parametrize("invalid_path", INVALID_PATHS)
def test_patch_folder_with_invalid_path_returns_422(client, sandbox, invalid_path: Callable):
    response = register_folder(client, "New", sandbox.photos)
    data = response.json()

    folder_id = data['id']

    patch_response = client.patch(f"/folders/{folder_id}", json={"path": str(invalid_path(sandbox))})

    assert patch_response.status_code == 422

    docs_get_folder_response = client.get(f"/folders/{folder_id}")

    assert docs_get_folder_response.json()["path"] == data["path"]


@pytest.mark.parametrize(
    "field",
    [
        pytest.param("name", id="null_name"),
        pytest.param("path", id="null_pah"),
        pytest.param("writable", id="null_writable"),
    ],
)
def test_patch_folder_with_null_field_returns_422(client, sandbox, field: str):
    response = register_folder(client, "New", sandbox.photos)
    data = response.json()

    folder_id = data['id']

    patch_response = client.patch(f"/folders/{folder_id}", json={field: None})

    get_folder_response = client.get(f"/folders/{folder_id}")

    assert patch_response.status_code == 422
    assert get_folder_response.json() == data


def test_patch_folder_with_null_description_clears_it(client, sandbox):
    response = register_folder(client, "New", sandbox.photos, "A note")
    data = response.json()

    folder_id = data['id']

    patch_response = client.patch(f"/folders/{folder_id}", json={"description": None})

    get_folder_response = client.get(f"/folders/{folder_id}")

    assert patch_response.status_code == 200
    assert patch_response.json()["description"] is None
    assert get_folder_response.json()["description"] is None


def test_patch_unknown_folder_returns_404(client, sandbox):
    patch_response = client.patch(f"/folders/999", json={"name": "New"})

    assert patch_response.status_code == 404
    assert patch_response.json() == {"detail": "Folder not found"}


def test_delete_folder_returns_204_and_removes_it(client, sandbox):
    response = register_folder(client, "New", sandbox.photos, "A note")
    data = response.json()

    folder_id = data['id']

    delete_response = client.delete(f"/folders/{folder_id}")

    assert delete_response.status_code == 204

    get_folder_response = client.get(f"/folders/{folder_id}")

    assert get_folder_response.status_code == 404


def test_delete_folder_keeps_folder_on_disk(client, sandbox):
    response = register_folder(client, "New", sandbox.photos, "A note")
    data = response.json()

    folder_id = data['id']

    client.delete(f"/folders/{folder_id}")

    assert sandbox.photos.exists()


def test_delete_unknown_folder_returns_404(client, sandbox):
    delete_response = client.delete(f"/folders/999")

    assert delete_response.status_code == 404
