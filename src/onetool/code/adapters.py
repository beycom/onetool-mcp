"""Capability-checked, invocation-scoped harness adapters."""

from __future__ import annotations

import os
import re
import selectors
import shutil
import signal
import subprocess
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from types import FrameType
from typing import TYPE_CHECKING, Protocol

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from onetool.code.domain import EnvironmentDelta, LaunchInvocation, ResolvedRoute
from onetool.code.proxy import ModelDiscovery
from ot.config.routing import validate_client_arguments
from ot.paths import expand_path

if TYPE_CHECKING:
    from ot.config.models import OneToolConfig
    from ot.config.routing import (
        CodeRouteConfig,
        ExternalClientConfig,
        Harness,
    )

_MAX_CAPABILITY_OUTPUT = 65_536
_CAPABILITY_TIMEOUT = 5.0
_PRIVATE_PROVIDER_KEY = "ONETOOL_CODE_PROVIDER_KEY"

_CLAUDE_CLEAN_ENV = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_MODEL",
        "ANTHROPIC_SMALL_FAST_MODEL",
        "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE",
        "CLAUDE_CODE_AUTO_COMPACT_WINDOW",
        "CLAUDE_CODE_DISABLE_1M_CONTEXT",
        "CLAUDE_CODE_ENABLE_GATEWAY_MODEL_DISCOVERY",
        "CLAUDE_CODE_MAX_CONTEXT_TOKENS",
        "CLAUDE_CODE_SUBAGENT_MODEL",
        "DISABLE_AUTO_COMPACT",
        "DISABLE_COMPACT",
        "ENABLE_TOOL_SEARCH",
    }
)
_CODEX_CLEAN_ENV = frozenset({_PRIVATE_PROVIDER_KEY})


class DiscoveryProtocol(Protocol):
    """Minimal inference discovery boundary used by adapters."""

    def validate(self, *identities: str) -> str:
        """Return a unique live identity."""
        ...


DiscoveryFactory = Callable[..., DiscoveryProtocol]


def resolve_client_executable(value: str) -> str:
    """Resolve and check one configured executable without a shell."""
    path = Path(value)
    resolved = str(path) if path.is_absolute() else shutil.which(value)
    if resolved is None:
        raise ValueError(f"Configured executable {value!r} was not found on PATH")
    resolved_path = Path(resolved)
    if not resolved_path.is_file() or not os.access(resolved_path, os.X_OK):
        raise ValueError(f"Configured executable is not an executable file: {resolved}")
    return str(resolved_path)


def run_capability_command(argv: tuple[str, ...]) -> str:
    """Run a non-interactive capability command with strict output/time bounds."""
    process = subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
    )
    if process.stdout is None:
        process.kill()
        process.wait()
        raise RuntimeError("Failed to capture external capability output")

    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + _CAPABILITY_TIMEOUT
    output = bytearray()
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                process.wait()
                raise ValueError(f"Capability command timed out: {Path(argv[0]).name}")
            events = selector.select(remaining)
            if not events:
                continue
            chunk = os.read(process.stdout.fileno(), 8192)
            if not chunk:
                break
            output.extend(chunk)
            if len(output) > _MAX_CAPABILITY_OUTPUT:
                process.kill()
                process.wait()
                raise ValueError(
                    f"Capability output exceeded {_MAX_CAPABILITY_OUTPUT} bytes"
                )
        try:
            return_code = process.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired as exc:
            process.kill()
            process.wait()
            raise ValueError(
                f"Capability command timed out: {Path(argv[0]).name}"
            ) from exc
    finally:
        selector.close()
        process.stdout.close()

    text = output.decode("utf-8", errors="replace")
    if return_code != 0:
        raise ValueError(
            f"Capability command failed for {Path(argv[0]).name} "
            f"with exit code {return_code}"
        )
    return text


def _installed_version(executable: str) -> Version:
    """Parse a bounded installed-client version."""
    output = run_capability_command((executable, "--version"))
    match = re.search(r"\d+(?:\.\d+){1,3}(?:[A-Za-z0-9.+-]*)?", output)
    if match is None:
        raise ValueError(
            f"Could not parse {Path(executable).name} version from bounded output"
        )
    try:
        return Version(match.group(0))
    except InvalidVersion as exc:
        raise ValueError(f"Unsupported {Path(executable).name} version format") from exc


def _check_configured_version(
    *,
    executable: str,
    configured: str | None,
) -> Version:
    """Check a user-configured constraint without imposing a fixture pin."""
    installed = _installed_version(executable)
    if configured is None:
        return installed
    try:
        constraint = SpecifierSet(configured)
    except InvalidSpecifier as exc:
        raise ValueError(
            f"Invalid configured version constraint: {configured}"
        ) from exc
    if installed not in constraint:
        raise ValueError(
            f"{Path(executable).name} {installed} does not satisfy configured "
            f"version constraint {configured}"
        )
    return installed


def check_client_version(*, executable: str, configured: str | None) -> Version:
    """Resolve an executable and return its capability-checked version."""
    return _check_configured_version(
        executable=resolve_client_executable(executable),
        configured=configured,
    )


def required_route_capabilities(
    *,
    harness: Harness,
    route: CodeRouteConfig,
    permission: str,
) -> tuple[str, ...]:
    """Return the stable command-line capabilities required by one route."""
    required = {"--model"}
    if harness == "claude":
        if route.settings_path is not None:
            required.add("--settings")
        if permission == "bypass":
            required.add("--dangerously-skip-permissions")
    else:
        if route.profile is not None:
            required.add("--profile")
        if route.transport != "direct" or route.source != "codex_subscription":
            required.add("--config")
        if permission == "bypass":
            required.add("--dangerously-bypass-approvals-and-sandbox")
    return tuple(sorted(required))


def _check_help_capabilities(
    *,
    executable: str,
    harness: Harness,
    route: CodeRouteConfig,
    permission: str,
) -> None:
    """Verify exact selected adapter flags from non-billable client help."""
    help_output = run_capability_command((executable, "--help"))
    required = required_route_capabilities(
        harness=harness,
        route=route,
        permission=permission,
    )
    missing = [flag for flag in required if flag not in help_output]
    if missing:
        raise ValueError(
            f"{Path(executable).name} lacks required route capabilities: "
            f"{', '.join(missing)}"
        )


def _checked_file(
    config: OneToolConfig,
    value: str,
    *,
    setting: str,
) -> str:
    """Resolve and require one user-owned regular file."""
    path = config._resolve_onetool_relative_path(value)
    if not path.is_file():
        raise ValueError(f"{setting} is not a readable regular file: {path}")
    return str(path)


def _checked_directory(
    config: OneToolConfig,
    value: str,
    *,
    setting: str,
) -> str:
    """Resolve and require one user-owned directory."""
    path = config._resolve_onetool_relative_path(value)
    if not path.is_dir():
        raise ValueError(f"{setting} is not a directory: {path}")
    return str(path)


def _toml_string(value: str) -> str:
    """Quote one invocation-scoped Codex TOML string."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _provider_id(route: ResolvedRoute, configured: str | None) -> str:
    """Return a safe internal Codex provider table identifier."""
    if configured is not None:
        if not re.fullmatch(r"[A-Za-z0-9_]+", configured):
            raise ValueError("provider_id must contain only letters, digits, or _")
        return configured
    normalized = re.sub(r"[^A-Za-z0-9_]", "_", route.name)
    return f"onetool_{normalized}"


def _client_and_route(
    *,
    config: OneToolConfig,
    route: ResolvedRoute,
) -> tuple[ExternalClientConfig, CodeRouteConfig]:
    """Return validated client and route configuration."""
    if config.code is None:
        raise ValueError("Code routing is not configured")
    route_config = config.code.routes[route.name]
    client = (
        config.code.clients.claude
        if route.harness == "claude"
        else config.code.clients.codex
    )
    if client is None:
        raise ValueError(f"Missing code.clients.{route.harness} configuration")
    return client, route_config


def _base_argv(
    *,
    executable: str,
    client: ExternalClientConfig,
    passthrough: tuple[str, ...],
    harness: Harness,
) -> list[str]:
    """Build and validate the common ordered argument prefix."""
    validate_client_arguments(harness=harness, arguments=passthrough)
    return [executable, *client.additional_arguments]


def _claude_invocation(
    *,
    config: OneToolConfig,
    route: ResolvedRoute,
    executable: str,
    client: ExternalClientConfig,
    route_config: CodeRouteConfig,
    passthrough: tuple[str, ...],
    secret_resolver: Callable[[str], str | None],
    discovery_factory: DiscoveryFactory,
) -> LaunchInvocation:
    """Build a native or proxied Claude Code invocation."""
    argv = _base_argv(
        executable=executable,
        client=client,
        passthrough=passthrough,
        harness="claude",
    )
    set_values: dict[str, str] = {}
    model_identity = route.model.id

    if route_config.settings_path is not None:
        settings = _checked_file(
            config,
            route_config.settings_path,
            setting=f"code.routes.{route.name}.settings_path",
        )
        argv.extend(("--settings", settings))

    if route.transport == "cliproxy":
        if config.code is None or config.code.cliproxy is None:
            raise ValueError("code.cliproxy is required for this route")
        connection = config.code.cliproxy
        secret = secret_resolver(connection.secret_name)
        if not secret:
            raise ValueError(
                f"Named inference secret {connection.secret_name!r} is not configured"
            )
        discovery = discovery_factory(config=connection, secret=secret)
        model_identity = discovery.validate(
            route.model.proxy_identity,
            route.model.id,
        )
        slots = route_config.model_slots
        slot_values = (
            (slots.opus, slots.sonnet, slots.haiku)
            if slots is not None
            else (model_identity, model_identity, model_identity)
        )
        validated_slots = tuple(
            discovery.validate(identity) for identity in slot_values
        )
        set_values.update(
            {
                "ANTHROPIC_BASE_URL": connection.base_url,
                "ANTHROPIC_AUTH_TOKEN": secret,
                "ANTHROPIC_DEFAULT_OPUS_MODEL": validated_slots[0],
                "ANTHROPIC_DEFAULT_SONNET_MODEL": validated_slots[1],
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": validated_slots[2],
            }
        )

    argv.extend(("--model", model_identity))
    if route.permission == "bypass":
        argv.append("--dangerously-skip-permissions")
    argv.extend(passthrough)
    return LaunchInvocation(
        route=route,
        executable=executable,
        argv=tuple(argv),
        environment=EnvironmentDelta.create(
            remove=set(_CLAUDE_CLEAN_ENV),
            set_values=set_values,
        ),
        working_directory=None,
    )


def _codex_paths(
    *,
    config: OneToolConfig,
    client: ExternalClientConfig,
    route: ResolvedRoute,
    route_config: CodeRouteConfig,
) -> tuple[dict[str, str], str | None, str | None]:
    """Validate optional Codex home, profile, and model catalog paths."""
    set_values: dict[str, str] = {}
    client_home = getattr(client, "home_path", None)
    if client_home is not None:
        home = _checked_directory(
            config,
            client_home,
            setting="code.clients.codex.home_path",
        )
        set_values["CODEX_HOME"] = home
    else:
        home = str(expand_path(os.environ.get("CODEX_HOME", "~/.codex")))

    profile = route_config.profile
    if profile is not None:
        profile_path = Path(home) / f"{profile}.config.toml"
        if not profile_path.is_file():
            raise ValueError(
                f"Codex profile must use the separate-file form: {profile_path}"
            )

    catalog = None
    if route_config.model_catalog_path is not None:
        catalog = _checked_file(
            config,
            route_config.model_catalog_path,
            setting=f"code.routes.{route.name}.model_catalog_path",
        )
    return set_values, profile, catalog


def _codex_invocation(
    *,
    config: OneToolConfig,
    route: ResolvedRoute,
    executable: str,
    client: ExternalClientConfig,
    route_config: CodeRouteConfig,
    passthrough: tuple[str, ...],
    secret_resolver: Callable[[str], str | None],
    discovery_factory: DiscoveryFactory,
) -> LaunchInvocation:
    """Build a native, proxied, or direct custom Codex invocation."""
    argv = _base_argv(
        executable=executable,
        client=client,
        passthrough=passthrough,
        harness="codex",
    )
    set_values, profile, catalog = _codex_paths(
        config=config,
        client=client,
        route=route,
        route_config=route_config,
    )
    if profile is not None:
        argv.extend(("--profile", profile))

    native = route.source == "codex_subscription" and route.transport == "direct"
    if not native:
        provider_id = _provider_id(route, route_config.provider_id)
        if route.transport == "cliproxy":
            if config.code is None or config.code.cliproxy is None:
                raise ValueError("code.cliproxy is required for this route")
            connection = config.code.cliproxy
            secret_name = connection.secret_name
            base_url = connection.base_url
            secret = secret_resolver(secret_name)
            if not secret:
                raise ValueError(
                    f"Named inference secret {secret_name!r} is not configured"
                )
            discovery_factory(config=connection, secret=secret).validate(
                route.model.proxy_identity,
                route.model.id,
            )
        else:
            if route_config.secret_name is None or route_config.base_url is None:
                raise ValueError("Direct custom Codex route is incomplete")
            secret_name = route_config.secret_name
            base_url = route_config.base_url
            secret = secret_resolver(secret_name)
            if not secret:
                raise ValueError(
                    f"Named provider secret {secret_name!r} is not configured"
                )

        set_values[_PRIVATE_PROVIDER_KEY] = secret
        overrides = (
            ("model_provider", _toml_string(provider_id)),
            (
                f"model_providers.{provider_id}.name",
                _toml_string(f"OneTool {route.name}"),
            ),
            (
                f"model_providers.{provider_id}.base_url",
                _toml_string(base_url),
            ),
            (
                f"model_providers.{provider_id}.env_key",
                _toml_string(_PRIVATE_PROVIDER_KEY),
            ),
            (
                f"model_providers.{provider_id}.wire_api",
                _toml_string("responses"),
            ),
        )
        for key, value in overrides:
            argv.extend(("-c", f"{key}={value}"))
        if route_config.supports_websockets is not None:
            value = str(route_config.supports_websockets).lower()
            argv.extend(
                ("-c", f"model_providers.{provider_id}.supports_websockets={value}")
            )

    if catalog is not None:
        argv.extend(("-c", f"model_catalog_json={_toml_string(catalog)}"))
    argv.extend(("--model", route.model.id))
    if route.permission == "bypass":
        argv.append("--dangerously-bypass-approvals-and-sandbox")
    argv.extend(passthrough)
    return LaunchInvocation(
        route=route,
        executable=executable,
        argv=tuple(argv),
        environment=EnvironmentDelta.create(
            remove=set(_CODEX_CLEAN_ENV),
            set_values=set_values,
        ),
        working_directory=None,
    )


def build_invocation(
    *,
    config: OneToolConfig,
    route: ResolvedRoute,
    passthrough: tuple[str, ...],
    secret_resolver: Callable[[str], str | None],
    discovery_factory: DiscoveryFactory | None = None,
) -> LaunchInvocation:
    """Build a complete capability-checked launch invocation.

    The client binary and local path capabilities are checked before any proxy
    network request or credential resolution.
    """
    client, route_config = _client_and_route(config=config, route=route)
    effective_discovery_factory = discovery_factory or ModelDiscovery
    executable = resolve_client_executable(client.executable)
    _check_configured_version(executable=executable, configured=client.version)
    _check_help_capabilities(
        executable=executable,
        harness=route.harness,
        route=route_config,
        permission=route.permission,
    )

    working_directory = None
    if client.working_directory is not None:
        working_directory = _checked_directory(
            config,
            client.working_directory,
            setting=f"code.clients.{route.harness}.working_directory",
        )

    if route.harness == "claude":
        invocation = _claude_invocation(
            config=config,
            route=route,
            executable=executable,
            client=client,
            route_config=route_config,
            passthrough=passthrough,
            secret_resolver=secret_resolver,
            discovery_factory=effective_discovery_factory,
        )
    else:
        invocation = _codex_invocation(
            config=config,
            route=route,
            executable=executable,
            client=client,
            route_config=route_config,
            passthrough=passthrough,
            secret_resolver=secret_resolver,
            discovery_factory=effective_discovery_factory,
        )

    return LaunchInvocation(
        route=invocation.route,
        executable=invocation.executable,
        argv=invocation.argv,
        environment=invocation.environment,
        working_directory=working_directory,
    )


def run_foreground(
    *,
    invocation: LaunchInvocation,
    parent_environment: Mapping[str, str] | None = None,
) -> tuple[int, float]:
    """Run the harness as an inherited-stream foreground child."""
    environment = invocation.environment.apply(parent_environment or os.environ)
    started = time.monotonic()
    process = subprocess.Popen(
        invocation.argv,
        cwd=invocation.working_directory,
        env=environment,
        shell=False,
    )
    forwarded = (signal.SIGINT, signal.SIGTERM, signal.SIGWINCH)
    previous: dict[
        signal.Signals,
        Callable[[int, FrameType | None], object] | int | signal.Handlers | None,
    ] = {}

    def forward(signum: int, _frame: FrameType | None) -> None:
        """Forward terminal signals to the foreground child."""
        try:
            process.send_signal(signum)
        except ProcessLookupError:
            return

    try:
        for sig in forwarded:
            previous[sig] = signal.getsignal(sig)
            signal.signal(sig, forward)
        return_code = process.wait()
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return return_code, time.monotonic() - started


__all__ = [
    "build_invocation",
    "check_client_version",
    "required_route_capabilities",
    "resolve_client_executable",
    "run_capability_command",
    "run_foreground",
]
