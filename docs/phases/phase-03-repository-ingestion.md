# Phase 3: Repository Ingestion & Workspace Isolation

## Status: Completed

### Scope & Invariants
- **Ingestion Sources**: Direct ZIP file upload (`multipart/form-data`) and remote GitHub repository cloning via public/authenticated API archives.
- **Archive Safety Guards**: Comprehensive protection against ZIP bombs, path traversal attacks (Zip Slip), symlinks, and archive corruption.
- **Workspace Isolation**: Repositories are unpacked into isolated directories partitioned strictly by `user_id` and `repository_id`. Traversal outside root storage is strictly forbidden.
- **Snapshot Support**: Filesystem snapshots captured at baseline and updates to enable zero-loss diffing and change intelligence.
- **Status Machine**: Repositories transition deterministically: `pending` -> `extracting` -> `processing` -> `completed` (or `failed` with descriptive error details).

---

### Core Services & Security Measures

#### 1. Safe ZIP Processing (`ZipService`)
- Validates CRC32 integrity using `zipfile.testzip()`.
- Rejects archives exceeding file count limit (`MAX_EXTRACT_FILE_COUNT = 5,000`).
- Rejects uncompressed contents exceeding size limit (`MAX_UNCOMPRESSED_SIZE_BYTES = 250 MB`).
- Defense against compression bombs: rejects files with compression ratio > 100:1 when uncompressed size exceeds 1 MB.
- Rejects Unix symlinks (`0o120000` mode flag) to prevent arbitrary file reading.
- Rejects directory traversal paths containing `..` or absolute paths starting with `/` or `\`.

#### 2. Workspace Management (`WorkspaceService`)
- Isolated directory structure: `storage/workspaces/{user_id}/{repository_id}`.
- Path resolution sanitization using `Path.resolve()` and asserting paths remain strictly within `workspaces_root`.
- Snapshot preservation in `storage/snapshots/{user_id}/{repository_id}/{snapshot_id}` for historical comparisons.
- Safe workspace clean-up routines.

#### 3. Ingestion Pipeline (`IngestionService`)
- Extracts archives, strips common root directories, and scans file trees.
- Filters binary files, ignored directories (`.git`, `node_modules`, `dist`, `__pycache__`, `venv`), and environment secret files.
- Persists file metadata (`RepositoryFile`) into Supabase PostgreSQL with line counts, byte sizes, and MIME types.
- Dispatches background processing tasks for code intelligence indexing.
