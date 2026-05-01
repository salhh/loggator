"""Multi-tenant context: default tenant resolution and FastAPI dependencies."""

from loggator.tenancy.bootstrap import get_default_tenant_id
from loggator.tenancy.deps import get_effective_tenant_id

__all__ = ["get_default_tenant_id", "get_effective_tenant_id"]
