from typing import Any

import pytest
from httpx import AsyncClient

from app.main import app
from app.services.storage import get_storage
from tests.conftest import Login
from tests.fakes import MemoryStorage

pytestmark = pytest.mark.db

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture
def storage(db_client: AsyncClient) -> MemoryStorage:
    fake = MemoryStorage()
    app.dependency_overrides[get_storage] = lambda: fake
    return fake


@pytest.fixture
async def ticket_id(manager: AsyncClient, project_id: str) -> str:
    response = await manager.post(f"/projects/{project_id}/tickets", json={"title": "Proof"})
    return response.json()["id"]


async def upload(
    client: AsyncClient, ticket_id: str, name: str, data: bytes, content_type: str = "image/png"
) -> Any:
    return await client.post(
        f"/tickets/{ticket_id}/attachments", files={"file": (name, data, content_type)}
    )


async def test_upload_list_and_download_round_trip(
    manager: AsyncClient, ticket_id: str, storage: MemoryStorage
) -> None:
    uploaded = await upload(manager, ticket_id, "screenshot.png", PNG)
    listed = (await manager.get(f"/tickets/{ticket_id}/attachments")).json()
    download = await manager.get(f"/attachments/{uploaded.json()['id']}/download")

    assert uploaded.status_code == 201
    assert uploaded.json()["content_type"] == "image/png"
    assert uploaded.json()["size_bytes"] == len(PNG)
    assert [(a["filename"], a["uploader_name"]) for a in listed] == [("screenshot.png", "Manager")]
    assert download.content == PNG
    assert download.headers["content-disposition"].startswith(
        'attachment; filename="screenshot.png"'
    )
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["content-security-policy"] == "sandbox"
    assert len(storage.objects) == 1


async def test_images_may_open_inline_other_files_always_download(
    manager: AsyncClient, ticket_id: str, storage: MemoryStorage
) -> None:
    image = (await upload(manager, ticket_id, "a.png", PNG)).json()
    text = (await upload(manager, ticket_id, "notes.txt", b"hello", "text/plain")).json()

    image_inline = await manager.get(f"/attachments/{image['id']}/download?inline=true")
    text_inline = await manager.get(f"/attachments/{text['id']}/download?inline=true")

    assert image_inline.headers["content-disposition"].startswith("inline")
    assert text_inline.headers["content-disposition"].startswith("attachment")


@pytest.mark.parametrize(
    ("name", "data", "claimed_type"),
    [
        pytest.param("page.html", b"<script>alert(1)</script>", "text/html", id="html"),
        pytest.param("logo.svg", b"<svg onload=alert(1)>", "image/svg+xml", id="svg"),
        pytest.param(
            "fake.png", b"<script>alert(1)</script>", "image/png", id="html posing as png"
        ),
        pytest.param("tool.exe", b"MZ\x90\x00", "application/octet-stream", id="executable"),
        pytest.param("binary.txt", b"\x00\x01\x02", "text/plain", id="binary posing as text"),
    ],
)
async def test_dangerous_or_mislabelled_files_are_refused(
    manager: AsyncClient,
    ticket_id: str,
    storage: MemoryStorage,
    name: str,
    data: bytes,
    claimed_type: str,
) -> None:
    response = await upload(manager, ticket_id, name, data, claimed_type)

    assert response.status_code == 422
    assert storage.objects == {}


async def test_content_type_comes_from_the_file_not_the_browser(
    manager: AsyncClient, ticket_id: str, storage: MemoryStorage
) -> None:
    response = await upload(manager, ticket_id, "report.pdf", b"%PDF-1.7 ...", "text/html")

    assert response.json()["content_type"] == "application/pdf"


async def test_filename_is_cleaned(
    manager: AsyncClient, ticket_id: str, storage: MemoryStorage
) -> None:
    response = await upload(manager, ticket_id, "../../etc/pass wd.txt", b"x", "text/plain")

    assert response.json()["filename"] == "pass wd.txt"
    assert all(key.startswith(f"tickets/{ticket_id}/") for key in storage.objects)


async def test_size_limits(manager: AsyncClient, ticket_id: str, storage: MemoryStorage) -> None:
    empty = await upload(manager, ticket_id, "empty.txt", b"", "text/plain")
    too_big = await upload(manager, ticket_id, "big.txt", b"a" * (10 * 2**20 + 1), "text/plain")

    assert empty.status_code == 422
    assert too_big.status_code == 413
    assert storage.objects == {}


async def test_who_may_upload_and_delete(
    manager: AsyncClient,
    employee: AsyncClient,
    ticket_id: str,
    storage: MemoryStorage,
    login: Login,
) -> None:
    by_employee = (await upload(employee, ticket_id, "proof.png", PNG)).json()
    by_manager = (await upload(manager, ticket_id, "spec.png", PNG)).json()
    outsider = await login("outsider")

    outsider_download = await outsider.get(f"/attachments/{by_manager['id']}/download")
    employee_deletes_managers = await employee.delete(f"/attachments/{by_manager['id']}")
    employee_deletes_own = await employee.delete(f"/attachments/{by_employee['id']}")
    manager_deletes = await manager.delete(f"/attachments/{by_manager['id']}")

    assert outsider_download.status_code == 404
    assert employee_deletes_managers.status_code == 403
    assert employee_deletes_own.status_code == manager_deletes.status_code == 204
    assert storage.objects == {}


async def test_storage_outage_gives_a_clear_error_and_no_orphan_row(
    manager: AsyncClient, ticket_id: str, storage: MemoryStorage
) -> None:
    storage.fail = True

    response = await upload(manager, ticket_id, "a.png", PNG)
    storage.fail = False
    listed = (await manager.get(f"/tickets/{ticket_id}/attachments")).json()

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "storage_unavailable"
    assert listed == []


async def test_oversized_request_is_refused_before_reading_the_body(
    manager: AsyncClient, ticket_id: str
) -> None:
    response = await manager.post(
        f"/tickets/{ticket_id}/attachments",
        content=b"x",
        headers={"content-length": str(50 * 2**20), "content-type": "multipart/form-data"},
    )

    assert response.status_code == 413
