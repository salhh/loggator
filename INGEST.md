## Log ingestion (HTTP)

The API can index logs into the tenant’s OpenSearch via a bulk ingest endpoint.

### Endpoint

- `POST http://localhost:8000/api/v1/ingest/logs`

### Auth / tenancy

- **JWT:** `Authorization: Bearer <JWT>`. If the token has multiple tenants (`tenant_ids`) and no single `tenant_id` claim, send **`X-Tenant-Id: <uuid>`** (not required when exactly one tenant is implied).
- **Ingest API key:** create via `POST /api/v1/tenant-api-keys` (see `DEPLOY.md`; callers need **`tenant_admin` membership** for that tenant or a **`platform_admin`** JWT). Send the raw key as either:
  - `Authorization: Bearer lgk_...`, or
  - `X-API-Key: lgk_...`  
  Keys are scoped (default scope `ingest`); revoked keys return `401`.
- **Platform admin** may impersonate a tenant by passing **`X-Tenant-Id`** together with a platform JWT.

### Request body

- `index` must **match the tenant’s OpenSearch index pattern** (`logs-*` by default, or `tenant_connections.opensearch_index_pattern` if set).
- Each log becomes an OpenSearch document with `@timestamp` and `message` fields; optional structured fields can be provided.

Example:

```json
{
  "index": "logs-app-2026.05.01",
  "refresh": false,
  "logs": [
    {
      "timestamp": "2026-05-01T09:00:00Z",
      "level": "ERROR",
      "service": "api-gateway",
      "host": "gw-01",
      "message": "SQL syntax error near 'UNION SELECT ...'",
      "fields": {
        "src_ip": "185.220.101.44",
        "path": "/api/v1/login"
      }
    }
  ]
}
```

### Response

- `indexed`: number of docs successfully indexed
- `errors`: number of bulk item errors

### Notes

- This endpoint is intended for automation / agents / log shippers. It does **not** replace existing log pipelines (Filebeat/Fluent Bit/etc.).
- If you use RAG chat, you still need to run **Index for chat** (or call `/api/v1/chat/index`) to embed logs into Postgres vectors.

