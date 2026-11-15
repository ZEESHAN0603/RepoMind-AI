import io
import os
import zipfile
from pathlib import Path
from typing import Tuple

from app.core.config import settings
from app.core.exceptions import BadRequestException
from app.core.logging import logger


class ZipService:
    """Provides secure, audited ZIP archive validation and extraction."""

    MAGIC_BYTES = b"PK\x03\x04"

    @classmethod
    def validate_zip_header(cls, file_bytes: bytes) -> None:
        """Validates that initial bytes conform to PKZip signature."""
        if len(file_bytes) < 4:
            raise BadRequestException("Invalid file: Empty or too short to be an archive")
        if not file_bytes.startswith(cls.MAGIC_BYTES):
            raise BadRequestException("Invalid archive format: Not a valid ZIP file")

    @classmethod
    def validate_and_extract(
        cls,
        zip_path_or_bytes: Path | bytes,
        destination_dir: Path,
    ) -> Tuple[int, int]:
        """
        Securely inspects and extracts a ZIP archive into destination_dir.
        Enforces defenses against ZIP Slip, ZIP bombs, symlinks, and oversized archives.
        Returns: (file_count, total_uncompressed_bytes)
        """
        destination_dir = destination_dir.resolve()
        destination_dir.mkdir(parents=True, exist_ok=True)

        try:
            if isinstance(zip_path_or_bytes, bytes):
                cls.validate_zip_header(zip_path_or_bytes)
                archive = zipfile.ZipFile(io.BytesIO(zip_path_or_bytes), "r")
            else:
                with open(zip_path_or_bytes, "rb") as f:
                    cls.validate_zip_header(f.read(4))
                archive = zipfile.ZipFile(zip_path_or_bytes, "r")
        except zipfile.BadZipFile as e:
            raise BadRequestException(f"Corrupt or invalid ZIP archive: {e}")
        except Exception as e:
            if isinstance(e, BadRequestException):
                raise
            raise BadRequestException(f"Failed to open archive: {e}")

        with archive:
            # Test CRC32 integrity
            corrupted = archive.testzip()
            if corrupted is not None:
                raise BadRequestException(f"Corrupt ZIP file detected at member: {corrupted}")

            infolist = archive.infolist()

            # Guard 1: File count limit
            if len(infolist) > settings.MAX_EXTRACT_FILE_COUNT:
                raise BadRequestException(
                    f"ZIP archive contains too many files ({len(infolist)} > max {settings.MAX_EXTRACT_FILE_COUNT})"
                )

            total_uncompressed_size = 0
            total_compressed_size = 0

            # Guard 2: Pre-scan for ZIP bombs, symlinks, and path traversal
            for member in infolist:
                total_uncompressed_size += member.file_size
                total_compressed_size += member.compress_size

                # Check max uncompressed size
                if total_uncompressed_size > settings.MAX_UNCOMPRESSED_SIZE_BYTES:
                    raise BadRequestException(
                        f"Uncompressed archive size exceeds limit of {settings.MAX_UNCOMPRESSED_SIZE_BYTES // (1024 * 1024)} MB"
                    )

                # Compression ratio check for ZIP bomb defense
                if member.compress_size > 0:
                    ratio = member.file_size / member.compress_size
                    if ratio > 100 and member.file_size > 1024 * 1024:
                        raise BadRequestException("ZIP bomb detected: Suspicious compression ratio")

                # Symlink detection (Unix mode attribute in upper 16 bits)
                mode = member.external_attr >> 16
                if (mode & 0o170000) == 0o120000:
                    raise BadRequestException(f"Symlinks are forbidden in archive: {member.filename}")

                # Path traversal and absolute path check
                name = member.filename.replace("\\", "/")
                if name.startswith("/") or ".." in name.split("/"):
                    raise BadRequestException(f"Path traversal detected in archive member: {member.filename}")

            # Check if all files are inside a common root folder (e.g. repo-main/)
            names = [m.filename.replace("\\", "/").strip("/") for m in infolist if m.filename.strip("/")]
            strip_prefix = ""
            if names:
                first_parts = [n.split("/")[0] for n in names]
                if len(set(first_parts)) == 1 and all("/" in n for n in names if not n.endswith("/")):
                    strip_prefix = first_parts[0] + "/"

            # Safe extraction pass
            extracted_files = 0
            for member in infolist:
                raw_name = member.filename.replace("\\", "/").strip("/")
                if not raw_name:
                    continue

                if strip_prefix and member.filename.replace("\\", "/").startswith(strip_prefix):
                    rel_name = member.filename.replace("\\", "/")[len(strip_prefix):].lstrip("/")
                else:
                    rel_name = member.filename.replace("\\", "/").lstrip("/")

                if not rel_name:
                    continue

                target_path = (destination_dir / rel_name).resolve()

                # Double check path containment
                try:
                    target_path.relative_to(destination_dir)
                except ValueError:
                    raise BadRequestException(f"Illegal path traversal attempt: {member.filename}")

                if member.is_dir() or member.filename.endswith("/"):
                    target_path.mkdir(parents=True, exist_ok=True)
                else:
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, open(target_path, "wb") as target:
                        # Stream in 64KB chunks
                        while chunk := source.read(65536):
                            target.write(chunk)
                    extracted_files += 1

            logger.info(
                "Extracted %d files (%d bytes uncompressed) safely to %s",
                extracted_files,
                total_uncompressed_size,
                destination_dir,
            )
            return extracted_files, total_uncompressed_size

