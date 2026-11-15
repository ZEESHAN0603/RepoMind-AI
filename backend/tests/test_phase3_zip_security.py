import io
import zipfile
from pathlib import Path
import pytest
from httpx import AsyncClient

from app.core.exceptions import BadRequestException
from app.services.zip_service import ZipService


def create_zip_bytes(files: dict) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            zf.writestr(filename, content)
    return buf.getvalue()


def test_zip_slip_protection(tmp_path: Path):
    dest_dir = tmp_path / "extracted"
    # Construct malicious zip with ../ traversal
    malicious_bytes = create_zip_bytes({
        "../../etc/passwd": "root:x:0:0:root",
        "normal.txt": "Safe text",
    })

    with pytest.raises(BadRequestException) as exc:
        ZipService.validate_and_extract(malicious_bytes, dest_dir)
    assert "Path traversal detected" in str(exc.value)


def test_invalid_header_rejection(tmp_path: Path):
    dest_dir = tmp_path / "extracted"
    junk_bytes = b"NOT_A_ZIP_HEADER_JUNK_DATA"

    with pytest.raises(BadRequestException) as exc:
        ZipService.validate_and_extract(junk_bytes, dest_dir)
    assert "Invalid archive format" in str(exc.value)


def test_symlink_rejection(tmp_path: Path):
    dest_dir = tmp_path / "extracted"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # Create an entry with symlink attribute
        zinfo = zipfile.ZipInfo("symlink_entry")
        # 0o120000 is S_IFLNK (symlink)
        zinfo.external_attr = 0o120000 << 16
        zf.writestr(zinfo, "/etc/shadow")

    with pytest.raises(BadRequestException) as exc:
        ZipService.validate_and_extract(buf.getvalue(), dest_dir)
    assert "Symlinks are forbidden" in str(exc.value)


@pytest.mark.asyncio
async def test_zip_upload_api(client: AsyncClient):
    # Register & login
    await client.post(
        "/api/v1/auth/register",
        json={"full_name": "Zip Tester", "email": "ziptester@repomind.ai", "password": "Password123!"},
    )
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "ziptester@repomind.ai", "password": "Password123!"},
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Reject non-zip file
    non_zip_file = ("document.txt", io.BytesIO(b"Hello world"), "text/plain")
    res_bad = await client.post(
        "/api/v1/repositories/upload",
        files={"file": non_zip_file},
        headers=headers,
    )
    assert res_bad.status_code == 400
    assert "must be a .zip archive" in res_bad.json()["error"]["message"]

    # 2. Upload valid zip file
    valid_zip = create_zip_bytes({
        "myrepo/app.py": "print('hello')",
        "myrepo/requirements.txt": "flask>=2.0\n",
    })
    zip_file = ("myrepo.zip", io.BytesIO(valid_zip), "application/zip")
    res_ok = await client.post(
        "/api/v1/repositories/upload",
        files={"file": zip_file},
        data={"name": "custom-zip-repo"},
        headers=headers,
    )
    assert res_ok.status_code == 201
    repo = res_ok.json()
    assert repo["name"] == "custom-zip-repo"
    assert repo["source_type"] == "zip_upload"

