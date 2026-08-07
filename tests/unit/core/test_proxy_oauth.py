"""OAuth registration and persistent token-storage tests for MCP proxies."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
from fastmcp.client.auth import OAuth
from key_value.aio.stores.keyring.store import (
    KeyringV1CollectionSanitizationStrategy,
    KeyringV1KeySanitizationStrategy,
)
from mcp.client.auth.utils import create_client_registration_request
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from ot.proxy import oauth as proxy_oauth
from ot.proxy.oauth import SecureOAuthTokenStore

MCP_URL = "https://mcp.notion.test/mcp"


@pytest.fixture
def fake_keyring(monkeypatch: pytest.MonkeyPatch) -> dict[tuple[str, str], str]:
    """Replace OS-keychain calls with a process-persistent dictionary."""
    values: dict[tuple[str, str], str] = {}

    monkeypatch.setattr(proxy_oauth, "_assert_secure_keyring_backend", lambda _: None)
    monkeypatch.setattr(
        proxy_oauth.keyring,
        "get_password",
        lambda service_name, username: values.get((service_name, username)),
    )
    monkeypatch.setattr(
        proxy_oauth.keyring,
        "set_password",
        lambda service_name, username, password: values.__setitem__(
            (service_name, username), password
        ),
    )
    return values


def _store(service_name: str = "onetool-mcp.oauth.test") -> SecureOAuthTokenStore:
    return SecureOAuthTokenStore(
        service_name=service_name,
        key_sanitization_strategy=KeyringV1KeySanitizationStrategy(),
        collection_sanitization_strategy=KeyringV1CollectionSanitizationStrategy(),
    )


def _client_info(oauth: OAuth) -> OAuthClientInformationFull:
    return OAuthClientInformationFull(
        client_id="notion-public-client",
        token_endpoint_auth_method="none",
        redirect_uris=oauth.context.client_metadata.redirect_uris,
        grant_types=["authorization_code", "refresh_token"],
        response_types=["code"],
    )


def _oauth(*, store: SecureOAuthTokenStore, mcp_url: str = MCP_URL) -> OAuth:
    return OAuth(
        mcp_url=mcp_url,
        client_name="OneTool",
        token_storage=store,
        additional_client_metadata={"token_endpoint_auth_method": "none"},
    )


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.usefixtures("fake_keyring")
class TestPublicClientRegistration:
    """Public PKCE metadata controls registration and token authentication."""

    async def test_notion_shaped_registration_and_token_exchange(self) -> None:
        oauth = _oauth(store=_store())

        registration_request = create_client_registration_request(
            None,
            oauth.context.client_metadata,
            "https://mcp.notion.test",
        )
        registration_body = json.loads(registration_request.content)
        assert registration_body["token_endpoint_auth_method"] == "none"
        assert registration_body["grant_types"] == [
            "authorization_code",
            "refresh_token",
        ]

        oauth.context.client_info = _client_info(oauth)
        token_request = await oauth._exchange_token_authorization_code(
            "approved-code", "pkce-verifier"
        )
        token_body = parse_qs(token_request.content.decode())

        assert "Authorization" not in token_request.headers
        assert token_body["client_id"] == ["notion-public-client"]
        assert "client_secret" not in token_body
        assert token_body["code_verifier"] == ["pkce-verifier"]


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.usefixtures("fake_keyring")
class TestOAuthTokenPersistence:
    """Client information and rotating tokens survive OAuth client recreation."""

    async def test_credentials_and_tokens_reused_and_scoped_by_endpoint(self) -> None:
        first = _oauth(store=_store())
        client_info = _client_info(first)
        initial_tokens = OAuthToken(
            access_token="first-access",
            refresh_token="first-refresh",
            expires_in=3600,
        )
        await first.token_storage_adapter.set_client_info(client_info)
        await first.token_storage_adapter.set_tokens(initial_tokens)

        recreated = _oauth(store=_store())
        await recreated._initialize()

        assert recreated.context.client_info is not None
        assert recreated.context.client_info.client_id == client_info.client_id
        assert (
            recreated.context.client_info.token_endpoint_auth_method
            == client_info.token_endpoint_auth_method
        )
        assert [
            str(uri) for uri in recreated.context.client_info.redirect_uris or []
        ] == [str(uri) for uri in client_info.redirect_uris or []]
        assert recreated.context.current_tokens == initial_tokens
        assert recreated.context.token_expiry_time is not None

        other_endpoint = _oauth(
            store=_store(), mcp_url="https://mcp.notion.test/another-workspace"
        )
        await other_endpoint._initialize()
        assert other_endpoint.context.client_info is None
        assert other_endpoint.context.current_tokens is None

    async def test_refresh_token_rotation_is_persisted(self) -> None:
        first = _oauth(store=_store())
        await first.token_storage_adapter.set_client_info(_client_info(first))
        await first.token_storage_adapter.set_tokens(
            OAuthToken(
                access_token="expired-access",
                refresh_token="old-refresh",
                expires_in=1,
            )
        )

        recreated = _oauth(store=_store())
        await recreated._initialize()
        refresh_request = await recreated._refresh_token()
        refresh_body = parse_qs(refresh_request.content.decode())
        assert refresh_body["refresh_token"] == ["old-refresh"]
        assert "Authorization" not in refresh_request.headers

        refresh_response = httpx.Response(
            200,
            json={
                "access_token": "rotated-access",
                "refresh_token": "rotated-refresh",
                "token_type": "Bearer",
                "expires_in": 7200,
            },
        )
        assert await recreated._handle_refresh_response(refresh_response) is True

        restarted = _oauth(store=_store())
        await restarted._initialize()
        assert restarted.context.current_tokens is not None
        assert restarted.context.current_tokens.access_token == "rotated-access"
        assert restarted.context.current_tokens.refresh_token == "rotated-refresh"

    def test_keyring_service_is_scoped_to_onetool_directory(self) -> None:
        first_dir = Path("/tmp/project-one/.onetool")
        second_dir = Path("/tmp/project-two/.onetool")

        assert proxy_oauth._oauth_keyring_service_name(
            first_dir
        ) == proxy_oauth._oauth_keyring_service_name(first_dir)
        assert proxy_oauth._oauth_keyring_service_name(
            first_dir
        ) != proxy_oauth._oauth_keyring_service_name(second_dir)
