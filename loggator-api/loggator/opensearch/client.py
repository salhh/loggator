import boto3
import structlog
from opensearchpy import AsyncOpenSearch
from opensearchpy import AWSV4SignerAsyncAuth

from loggator.config import settings

log = structlog.get_logger()


def _build_client() -> AsyncOpenSearch:
    host = {"host": settings.opensearch_host, "port": settings.opensearch_port}
    # AIOHttpConnection is the default async connection class — do not override it
    common: dict = {
        "hosts": [host],
        "use_ssl": settings.opensearch_use_ssl,
        "verify_certs": settings.opensearch_verify_certs,
    }
    if settings.opensearch_ca_certs:
        common["ca_certs"] = settings.opensearch_ca_certs

    auth_type = settings.opensearch_auth_type

    if auth_type == "none":
        return AsyncOpenSearch(**common)

    if auth_type == "basic":
        return AsyncOpenSearch(
            **common,
            http_auth=(settings.opensearch_username, settings.opensearch_password),
        )

    if auth_type == "api_key":
        return AsyncOpenSearch(
            **common,
            headers={"x-api-key": settings.opensearch_api_key},
        )

    if auth_type == "aws_iam":
        credentials = boto3.Session().get_credentials()
        aws_auth = AWSV4SignerAsyncAuth(credentials, settings.aws_region, "es")
        return AsyncOpenSearch(**common, http_auth=aws_auth)

    raise ValueError(f"Unknown OPENSEARCH_AUTH_TYPE: {auth_type!r}")


_client: AsyncOpenSearch | None = None


def get_client() -> AsyncOpenSearch:
    global _client
    if _client is None:
        _client = _build_client()
        log.info("opensearch.client.created", auth_type=settings.opensearch_auth_type)
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
