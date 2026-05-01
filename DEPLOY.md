# Deploy / operations

## First tenant

1. Run database migrations (`alembic upgrade head` in the API image or CI).
2. The multi-tenant migration seeds a **Default** tenant (`slug=default`). Use platform APIs or SQL to add more tenants.
3. **Platform admin** (JWT claim `platform_roles` containing `platform_admin`):
   - `POST /api/v1/platform/tenants` with JSON body `{ "name": "Acme", "slug": "acme", "admin_subject": "<oidc-sub>", "admin_email": "ops@acme.test" }` to create a tenant and grant that OIDC subject `tenant_admin` on it.
4. Map **OIDC subject → user row**: the `admin_subject` must match the `sub` claim in issued JWTs. Additional members can be inserted into `users` + `memberships` as needed.

## Connection secrets (OpenSearch)

- Set **`CONNECTION_SECRETS_FERNET_KEY`** to a [Fernet](https://cryptography.io/en/latest/fernet/) key (32 url-safe base64-encoded bytes). Generate locally:
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
- Use **`PUT /api/v1/platform/tenants/{tenant_id}/connection`** with plaintext passwords/API keys in the JSON body; the API encrypts `opensearch_password`, `opensearch_api_key`, and `opensearch_ca_certs` before storing.
- If the Fernet key is **empty**, secrets are stored as plaintext (development only).

## Ingest API keys

- Set a strong **`API_KEY_PEPPER`** in production (same value must be stable per deployment so hashes remain valid).
- Tenants create keys with `POST /api/v1/tenant-api-keys` (requires `tenant_admin` or `platform_admin` JWT).
- Send the raw key once as `Authorization: Bearer lgk_...` or `X-API-Key: lgk_...` on `POST /api/v1/ingest/logs`.
- Revoke with `POST /api/v1/tenant-api-keys/{id}/revoke`.

## Rotate / revoke

- **JWT**: handled by your IdP (short TTL + refresh).
- **Ingest keys**: revoke in API; create a new key before decommissioning the old one if you need zero downtime.
- **Fernet**: rotating the key requires re-encrypting stored connection secrets (not automated here); plan a maintenance window or dual-read period.

## Disaster recovery

- **Postgres**: restore from backup; ensure `tenants`, `tenant_connections`, and `tenant_api_keys` are included.
- **OpenSearch**: restore indices per your cluster DR plan; tenant **index patterns** live in `tenant_connections.opensearch_index_pattern` or global env defaults.
- **Secrets**: restore `.env` / secret manager entries for `DATABASE_URL`, `CONNECTION_SECRETS_FERNET_KEY`, `API_KEY_PEPPER`, `DEV_JWT_SECRET` (dev only), and OIDC settings.

## Frontend

- Sign in via `/login` using **SSO** (OIDC) or **dev token** (credentials provider).
- Tenancy is selected from the left sidebar (**Tenant** selector) and sent to the API as `X-Tenant-Id`.
- Set `NEXT_PUBLIC_API_URL` to the public API base (e.g. `https://api.example.com/api/v1`).
- **Platform UI:** `/platform/tenants` in the web app lists and creates tenants (requires `platform_admin` JWT, or `AUTH_DISABLED=true` in dev).
- **Live WebSocket:** `NEXT_PUBLIC_WS_URL` should point at `wss://…/ws/live`. The browser sends `access_token` and `tenant_id` query params so only that tenant’s anomaly/summary events are delivered (platform admins receive all tenants’ events).

## Tenant roles (RBAC)

- **Tenant access** for API data is driven by **`memberships`** (OIDC `sub` → `users.subject` → `memberships`). JWT may omit per-tenant roles if you manage members only via the API/UI.
- **`tenant_admin`** in the database can manage **ingest API keys**, **members**, and other tenant-admin actions. **`platform_admin`** in the JWT can do the same for any tenant when using `X-Tenant-Id`.
- **Members API:** `GET/POST/PATCH/DELETE /api/v1/tenant/members` (effective tenant from JWT + `X-Tenant-Id`). Listing requires `tenant_member` or `tenant_admin`; changes require `tenant_admin` or platform. The last `tenant_admin` cannot be demoted or removed except by a **platform** JWT.
- **User search (platform):** `GET /api/v1/platform/users?search=` for autocomplete when inviting subjects that already exist in `users`.
