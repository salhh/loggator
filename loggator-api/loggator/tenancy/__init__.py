"""Multi-tenant context: default tenant resolution and FastAPI dependencies."""

__all__ = ["get_default_tenant_id", "get_effective_tenant_id"]


def __getattr__(name: str):
    if name == "get_default_tenant_id":
        from loggator.tenancy.bootstrap import get_default_tenant_id

        return get_default_tenant_id
    if name == "get_effective_tenant_id":
        from loggator.tenancy.deps import get_effective_tenant_id

        return get_effective_tenant_id
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
