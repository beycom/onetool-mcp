"""OAuth registration and persistent token-storage tests for MCP proxies."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qs

import httpx
import pytest
from fastmcp.client.auth import OAuth
from filelock import AsyncFileLock
from key_value.aio.stores.keyring.store import (
    KeyringV1CollectionSanitizationStrategy,
    KeyringV1KeySanitizationStrategy,
)
from mcp.client.auth.utils import create_client_registration_request
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from ot.proxy import oauth as proxy_oauth
from ot.proxy.oauth import OneToolOAuth, SecureOAuthTokenStore

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

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
    monkeypatch.setattr(
        proxy_oauth.keyring,
        "delete_password",
        lambda service_name, username: values.pop((service_name, username), None),
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


def _oauth(
    *,
    store: SecureOAuthTokenStore,
    mcp_url: str = MCP_URL,
    scopes: list[str] | None = None,
    callback_port: int = 43100,
    lock_path: Path | None = None,
    lock_timeout: float = 30.0,
) -> OneToolOAuth:
    return OneToolOAuth(
        mcp_url=mcp_url,
        scopes=scopes,
        token_storage=store,
        callback_port=callback_port,
        lock_path=lock_path,
        lock_timeout=lock_timeout,
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
        await first._initialize()
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
        await first._initialize()
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


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.usefixtures("fake_keyring")
class TestOAuthAuthorizationIdentity:
    """Stored OAuth state matches endpoint, scopes, and current registration."""

    async def test_callback_change_keeps_tokens_but_discards_registration(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        store = _store()
        first = _oauth(store=store, scopes=["read"], callback_port=43100)
        await first._initialize()
        await first.token_storage_adapter.set_client_info(_client_info(first))
        tokens = OAuthToken(
            access_token="valid-access",
            refresh_token="valid-refresh",
            expires_in=3600,
        )
        await first.token_storage_adapter.set_tokens(tokens)

        recreated = _oauth(store=store, scopes=["read"], callback_port=43101)
        await recreated._initialize()

        assert recreated.context.current_tokens == tokens
        assert recreated.context.client_info is not None

        async def reauthorization_flow(
            provider: OAuth, request: httpx.Request
        ) -> AsyncGenerator[httpx.Request, httpx.Response]:
            response = yield request
            assert response.status_code == 401
            assert provider.context.client_info is None
            yield request

        monkeypatch.setattr(OAuth, "async_auth_flow", reauthorization_flow)
        request = httpx.Request("GET", MCP_URL)
        flow = recreated.async_auth_flow(request)
        assert await anext(flow) is request
        assert await flow.asend(httpx.Response(401, request=request)) is request
        await flow.aclose()

        assert recreated.context.client_info is None
        assert await recreated.token_storage_adapter.get_client_info() is None
        assert [
            str(uri) for uri in recreated.context.client_metadata.redirect_uris or []
        ] == ["http://localhost:43101/callback"]

    async def test_scope_change_invalidates_tokens_and_registration(self) -> None:
        store = _store()
        first = _oauth(store=store, scopes=["read"], callback_port=43100)
        await first._initialize()
        await first.token_storage_adapter.set_client_info(_client_info(first))
        await first.token_storage_adapter.set_tokens(
            OAuthToken(access_token="old-access", refresh_token="old-refresh")
        )

        changed = _oauth(store=store, scopes=["write"], callback_port=43100)
        await changed._initialize()

        assert changed.context.current_tokens is None
        assert changed.context.client_info is None

    async def test_scope_order_has_one_identity(self) -> None:
        store = _store()
        first = _oauth(store=store, scopes=["write", "read"], callback_port=43100)
        await first._initialize()
        info = _client_info(first)
        await first.token_storage_adapter.set_client_info(info)
        tokens = OAuthToken(access_token="valid-access", refresh_token="refresh")
        await first.token_storage_adapter.set_tokens(tokens)

        reordered = _oauth(
            store=store, scopes=["read", "write", "read"], callback_port=43100
        )
        await reordered._initialize()

        assert reordered.context.current_tokens == tokens
        assert reordered.context.client_info is not None
        assert reordered.context.client_info.model_dump(mode="json") == info.model_dump(
            mode="json"
        )
        assert reordered.context.client_metadata.scope == "read write"

    async def test_state_without_identity_metadata_is_invalidated(self) -> None:
        store = _store()
        old_client = _oauth(store=store, scopes=["read"], callback_port=43100)
        await old_client.token_storage_adapter.set_client_info(_client_info(old_client))
        await old_client.token_storage_adapter.set_tokens(
            OAuthToken(access_token="unverified", refresh_token="unverified-refresh")
        )

        current = _oauth(store=store, scopes=["read"], callback_port=43100)
        await current._initialize()

        assert current.context.current_tokens is None
        assert current.context.client_info is None


@pytest.mark.unit
@pytest.mark.core
@pytest.mark.usefixtures("fake_keyring")
class TestOAuthStateLock:
    """OAuth refresh and registration transactions are process-safe."""

    async def test_concurrent_refresh_reloads_rotated_tokens(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        store = _store()
        lock_path = tmp_path / "refresh.lock"
        seed = _oauth(store=store, lock_path=lock_path)
        await seed._initialize()
        await seed.token_storage_adapter.set_client_info(_client_info(seed))
        await seed.token_storage_adapter.set_tokens(
            OAuthToken(
                access_token="expired-access",
                refresh_token="rotating-refresh",
                expires_in=-1,
            )
        )
        refresh_tokens_used: list[str] = []

        async def refresh_flow(
            provider: OAuth, request: httpx.Request
        ) -> AsyncGenerator[httpx.Request, httpx.Response]:
            if not provider.context.is_token_valid():
                assert provider.context.current_tokens is not None
                refresh_tokens_used.append(
                    provider.context.current_tokens.refresh_token or ""
                )
                await asyncio.sleep(0.05)
                rotated = OAuthToken(
                    access_token="rotated-access",
                    refresh_token="rotated-refresh",
                    expires_in=3600,
                )
                await provider.token_storage_adapter.set_tokens(rotated)
                provider.context.current_tokens = rotated
                provider.context.update_token_expiry(rotated)
            yield request

        monkeypatch.setattr(OAuth, "async_auth_flow", refresh_flow)
        clients = [
            _oauth(store=store, lock_path=lock_path),
            _oauth(store=store, lock_path=lock_path),
        ]

        async def run(client: OneToolOAuth) -> str:
            request = httpx.Request("GET", MCP_URL)
            flow = client.async_auth_flow(request)
            await anext(flow)
            await flow.aclose()
            assert client.context.current_tokens is not None
            return client.context.current_tokens.access_token

        assert await asyncio.gather(*(run(client) for client in clients)) == [
            "rotated-access",
            "rotated-access",
        ]
        assert refresh_tokens_used == ["rotating-refresh"]

    async def test_concurrent_registration_runs_once(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        store = _store()
        lock_path = tmp_path / "registration.lock"
        seed = _oauth(store=store, lock_path=lock_path)
        await seed._initialize()
        registrations = 0

        async def registration_flow(
            provider: OAuth, request: httpx.Request
        ) -> AsyncGenerator[httpx.Request, httpx.Response]:
            nonlocal registrations
            if provider.context.client_info is None:
                registrations += 1
                await asyncio.sleep(0.05)
                await provider.token_storage_adapter.set_client_info(
                    _client_info(provider)
                )
                tokens = OAuthToken(access_token="registered", expires_in=3600)
                await provider.token_storage_adapter.set_tokens(tokens)
                provider.context.client_info = _client_info(provider)
                provider.context.current_tokens = tokens
                provider.context.update_token_expiry(tokens)
            yield request

        monkeypatch.setattr(OAuth, "async_auth_flow", registration_flow)
        clients = [
            _oauth(store=store, lock_path=lock_path),
            _oauth(store=store, lock_path=lock_path),
        ]

        async def run(client: OneToolOAuth) -> None:
            flow = client.async_auth_flow(httpx.Request("GET", MCP_URL))
            await anext(flow)
            await flow.aclose()

        await asyncio.gather(*(run(client) for client in clients))
        assert registrations == 1
        assert all(client.context.client_info is not None for client in clients)

    async def test_waiting_and_holding_cancellation_release_lock(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        store = _store()
        lock_path = tmp_path / "cancellation.lock"
        seed = _oauth(store=store, lock_path=lock_path)
        await seed._initialize()
        holder = _oauth(store=store, lock_path=lock_path)
        waiter = _oauth(store=store, lock_path=lock_path)
        successor = _oauth(store=store, lock_path=lock_path)
        holder_entered = asyncio.Event()

        async def cancellable_flow(
            provider: OAuth, request: httpx.Request
        ) -> AsyncGenerator[httpx.Request, httpx.Response]:
            if provider is holder:
                holder_entered.set()
                await asyncio.Event().wait()
            yield request

        monkeypatch.setattr(OAuth, "async_auth_flow", cancellable_flow)
        holder_flow = holder.async_auth_flow(httpx.Request("GET", MCP_URL))
        holder_task = asyncio.create_task(anext(holder_flow))
        await holder_entered.wait()

        waiter_flow = waiter.async_auth_flow(httpx.Request("GET", MCP_URL))
        waiter_task = asyncio.create_task(anext(waiter_flow))
        await asyncio.sleep(0.05)
        assert not waiter_task.done()
        waiter_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter_task

        holder_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await holder_task

        successor_flow = successor.async_auth_flow(httpx.Request("GET", MCP_URL))
        await asyncio.wait_for(anext(successor_flow), timeout=1)
        await successor_flow.aclose()

    async def test_different_endpoints_do_not_block(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        store = _store()
        entered = 0
        both_entered = asyncio.Event()
        release = asyncio.Event()

        async def concurrent_flow(
            _provider: OAuth, request: httpx.Request
        ) -> AsyncGenerator[httpx.Request, httpx.Response]:
            nonlocal entered
            entered += 1
            if entered == 2:
                both_entered.set()
            await release.wait()
            yield request

        monkeypatch.setattr(OAuth, "async_auth_flow", concurrent_flow)
        clients = [
            _oauth(
                store=store,
                mcp_url="https://first.mcp.test/mcp",
                lock_path=tmp_path / "first.lock",
            ),
            _oauth(
                store=store,
                mcp_url="https://second.mcp.test/mcp",
                lock_path=tmp_path / "second.lock",
            ),
        ]
        flows = [
            client.async_auth_flow(httpx.Request("GET", client.mcp_url))
            for client in clients
        ]
        tasks = [asyncio.create_task(anext(flow)) for flow in flows]
        await asyncio.wait_for(both_entered.wait(), timeout=1)
        release.set()
        await asyncio.gather(*tasks)
        await asyncio.gather(*(flow.aclose() for flow in flows))

    async def test_lock_timeout_is_async_and_sanitized(
        self, tmp_path: Path
    ) -> None:
        endpoint = "https://mcp.test/mcp?credential=highly-secret"
        lock_path = proxy_oauth.oauth_lock_path(endpoint, config_dir=tmp_path)
        other_lock_path = proxy_oauth.oauth_lock_path(
            "https://other.mcp.test/mcp", config_dir=tmp_path
        )
        assert lock_path != other_lock_path
        assert "mcp.test" not in lock_path.name
        assert "highly-secret" not in lock_path.name

        held_lock = AsyncFileLock(lock_path)
        await held_lock.acquire()
        client = _oauth(
            store=_store(),
            mcp_url=endpoint,
            lock_path=lock_path,
            lock_timeout=0.05,
        )
        event_loop_progressed = asyncio.Event()

        async def tick() -> None:
            await asyncio.sleep(0)
            event_loop_progressed.set()

        tick_task = asyncio.create_task(tick())
        try:
            flow = client.async_auth_flow(httpx.Request("GET", endpoint))
            with pytest.raises(
                TimeoutError,
                match="Timed out waiting for exclusive OAuth credential update",
            ):
                await anext(flow)
            assert event_loop_progressed.is_set()
            await tick_task
        finally:
            await held_lock.release()
