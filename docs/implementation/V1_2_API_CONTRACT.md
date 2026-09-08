# V1.2 API Contract

The V1.2 backend exposes reusable JSON APIs for `/org`, `/teams`, `/resources`, `/relationships`, `/rooms`, `/skills`, `/memories`, `/work-evidence`, and `/cost`. Existing V1 endpoints remain compatible.

Enums and lifecycle states are represented as strings. Create/update endpoints return the persisted typed object; archive/delete operations are soft where possible and return `{ "status": "archived" }` or `{ "status": "removed" }`. Invalid graph cycles, archived memberships, unsafe learned skills and budget violations return HTTP 409. Secret values are never returned.

Foundation-only: external provider billing settlement and encrypted credential storage depend on deployment key management; the API fails closed when a secure key is unavailable.
