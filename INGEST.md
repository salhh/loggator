## Log ingestion (HTTP)

The API can index logs into the tenant’s OpenSearch via a bulk ingest endpoint.

### Endpoint

- `POST http://localhost:8000/api/v1/ingest/logs`

### Auth / tenancy

- If auth is enabled, include `Authorization: Bearer <JWT>`.
- For multi-tenant tokens or platform support, include `X-Tenant-Id: <uuid>`.

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

