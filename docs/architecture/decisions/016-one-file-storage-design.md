# ADR-016: One File Storage Design — Metadata and Bytes Are Separate

## Status
Accepted

## Date
2026-08-12

## Context

The backlog carried this entry as P1: *"Decide between three ways to write a file to disk.
`LocalDiskStorageConnector` (ADR-007), `SQLiteFileStore` and `FileSystemCloudStore`
arrived from two branches, they overlap, and nothing says which one a caller should
use."*

Measuring it first changed the question. What exists is not three ways to write a file; it
is **one design implemented twice, plus a connector nobody calls**.

### Two services, the same operations

| | `file` service | `cloud` service |
|---|---|---|
| Routes | `/file/upload`, `/file/{id}`, `/file/list`, `/file/stats`, `DELETE /file/{id}` | the same five, plus `/cloud/{id}/download` |
| Item type | `FileItem` | `CloudFileItem` |
| Store interface | `save`, `get`, `list_files`, `delete`, `update_metadata`, `stats`, `clear`, `count`, `total_size` | the same nine |
| Manager | `upload_file`, `get_file`, `list_files`, `delete_file`, `update_metadata`, `stats`, `clear` | the same, plus `download` |
| Backends | in-memory, SQLite | in-memory, SQLite, filesystem, S3 |
| Backend selection | `GALSEN_STORAGE_BACKEND` | `GALSEN_CLOUD_BACKEND`, falling back to the general one |

Method for method, the same service. `1 368` lines across six store files implement one
job twice.

### The one real difference, and it is a defect

The two store interfaces differ in exactly one place:

```python
# cloud    — bytes are a separate operation
def save(self, item: CloudFileItem, data: bytes) -> str
def get_data(self, file_id: str) -> Optional[bytes]

# file     — bytes live inside the item
def save(self, file: FileItem) -> str        # FileItem.data: bytes
```

Because `FileItem` carries its content, **every listing loads every file's content**.
`SQLiteFileStore.list_files()` runs `SELECT * FROM files`, and `*` includes the `data`
BLOB. Measured on this repository, 30 files of 2 MB:

```
list_files() -> 30 fichiers en 652 ms, pic mémoire 60.0 Mo
octets chargés : 60.0 Mo
```

Those 60 MB are read and thrown away: `POST /file/list` serialises with
`to_dict(include_data=False)`. The default limit is 100 files, so the cost grows with what
users store, and the failure mode is the one that arrives without warning — an upload
service that runs fine until the day someone lists a directory of large files.

`SQLiteCloudStore` does not have the defect: it keeps two tables, `cloud_files` for
metadata and `cloud_data` for bytes, and listing never touches the second.

So the service with the modest name has the better design, and the service named after a
deployment topology has the domain name that a file service should have.

### The third implementation is not a competitor

`LocalDiskStorageConnector` is registered in the connector registry at start-up and
**nothing in the platform calls its `put` or `get`**. It is reachable only through the
connector framework's `describe()` and `check()`. It is not a third file store in
competition with the other two; it is a connector without a consumer.

## Decision

### 1. Metadata and bytes are separate, everywhere

A store lists metadata without reading content. Content is fetched by an explicit
operation, for one file at a time.

This is the rule the rest of the decision follows from, and it is not a preference: the
alternative has a measured cost that scales with the data users trust the platform with.

### 2. One item type is never returned half-filled

A listing does not return `FileItem` objects with an empty `data` field. An empty `bytes`
that means *"not loaded"* is indistinguishable from an empty `bytes` that means *"this
file is empty"*, and `.claude/rules/verification.md` forbids exactly that shape of
plausible-but-wrong value.

Listings return `FileSummary` — the same fields without `data`. A caller who needs the
content asks for the file, and the type says so.

### 3. `file` is the platform's file service; `cloud` is a backend, not a domain

`/file/*` and `FileItem` keep the domain name. The `cloud` service's value is its
**backends** — filesystem and S3 — and those belong under the file service, selected the
way every other service selects a store (ADR-005).

`CloudFileItem.provider` stops being a property of a stored file: which backend holds the
bytes is a property of the deployment, and the store already knows it.

### 4. `/cloud/*` is deprecated, not deleted

`v0.1.0` is released and both route families are public. ADR-011 governs what happens
next: `/cloud/*` is marked deprecated in favour of `/file/*`, keeps working, and is
removed no earlier than the next major version.

### 5. `LocalDiskStorageConnector` stays a connector and is not a storage backend

ADR-007 defines connectors as the platform's way of **reaching an external system**, with
health reporting (`check()`, `describe()`). That is a different job from storing the
platform's own files, and this ADR does not merge the two.

It keeps no consumer today. That is recorded rather than hidden: a connector that nothing
calls is a declared capability with no evidence behind it, and the day something needs to
write to an operator-provided directory, this is the interface it uses — not the file
service.

## Consequences

### Immediate

- `FileStore.list_files()` returns `FileSummary`; `SQLiteFileStore` selects the columns it
  needs instead of `*`. The 60 MB measured above become the metadata alone.
- `FileManagerImpl.list_files()` and `POST /file/list` follow the type. The route already
  discarded the content, so what callers receive over HTTP does not change.

### Staged, and not done by this ADR

- Moving the filesystem and S3 backends under the file service.
- Deprecating `/cloud/*` in the OpenAPI description and the deprecation index of ADR-011.
- Retiring `CloudFileItem` in favour of `FileItem`.

Each is a separate change with its own tests, and each is safe to take in any order once
this decision exists. What the backlog asked for — *"nothing says which one a caller
should use"* — is answered by point 3: **a caller uses the file service.**

### Accepted cost

Two route families do the same thing until the next major version. Deleting `/cloud/*`
today would break any client of a released version to save one file of documentation, and
ADR-011 exists precisely to refuse that trade.

## References

- ADR-005 — persistent storage backend, and how a service selects its store
- ADR-007 — the external connector layer
- ADR-011 — API versioning and deprecation
- `.claude/rules/verification.md` — why a half-filled item is refused
