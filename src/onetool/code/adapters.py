"""Invocation-scoped proxy adapters for Claude Code and Codex."""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn

from onetool.code.domain import EnvironmentDelta, LaunchInvocation, ResolvedTarget
from ot.config.routing import validate_client_arguments

if TYPE_CHECKING:
    from ot.config.models import OneToolConfig
    from ot.config.routing import ExternalClientConfig, Harness

_MAX_CAPABILITY_OUTPUT = 65_536
_CAPABILITY_TIMEOUT = 5.0
_PRIVATE_PROVIDER_KEY = "ONETOOL_CODE_PROVIDER_KEY"
_PROVIDER_ID = "onetool_proxy"

_CLAUDE_CLEAN_ENV = frozenset(
    {
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL_DESCRIPTION",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL_NAME",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL_DESCRIPTION",
        "ANTHROPIC_DEFAULT_SONNET_MODEL_NAME",
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


def resolve_client_executable(value: str) -> str:
    """Resolve and check one configured executable without a shell."""
    path = Path(value)
    resolved = str(path) if path.is_absolute() else shutil.which(value)
    if resolved is None:
        raise ValueError(f"Configured executable {value!r} was not found on PATH")
    resolved_path = Path(resolved).resolve()
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
        raise RuntimeError("Capability command output pipe was not created")

    output = bytearray()
    deadline = time.monotonic() + _CAPABILITY_TIMEOUT
    try:
        os.set_blocking(process.stdout.fileno(), False)
        while True:
            if time.monotonic() >= deadline:
                raise subprocess.TimeoutExpired(argv, _CAPABILITY_TIMEOUT)
            try:
                chunk = os.read(
                    process.stdout.fileno(),
                    min(8192, _MAX_CAPABILITY_OUTPUT + 1 - len(output)),
                )
            except BlockingIOError:
                chunk = None

            if chunk:
                output.extend(chunk)
                if len(output) > _MAX_CAPABILITY_OUTPUT:
                    raise ValueError(
                        f"Capability output exceeded {_MAX_CAPABILITY_OUTPUT} bytes"
                    )
                continue

            if chunk == b"" and process.poll() is not None:
                break
            time.sleep(0.01)
    except subprocess.TimeoutExpired as exc:
        raise ValueError(
            f"Capability command timed out: {Path(argv[0]).name}"
        ) from exc
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()

    if process.returncode != 0:
        raise ValueError(
            f"Capability command failed for {Path(argv[0]).name} "
            f"with exit code {process.returncode}"
        )
    return output.decode("utf-8", errors="replace")


def required_route_capabilities(
    *,
    harness: Harness,
    permission: str,
    require_proxy: bool = True,
    require_profile: bool = False,
) -> tuple[str, ...]:
    """Return stable flags required by configured adapter targets."""
    required = {"--model"}
    if harness == "codex" and require_proxy:
        required.add("--config")
    if harness == "codex" and require_profile:
        required.add("--profile")
    if permission == "bypass":
        required.add(
            "--dangerously-skip-permissions"
            if harness == "claude"
            else "--dangerously-bypass-approvals-and-sandbox"
        )
    return tuple(sorted(required))


def check_client_capabilities(
    *,
    executable: str,
    harness: Harness,
    permission: str,
    require_proxy: bool = True,
    require_profile: bool = False,
) -> tuple[str, ...]:
    """Verify adapter flags for one resolved executable."""
    help_output = run_capability_command((executable, "--help"))
    required = required_route_capabilities(
        harness=harness,
        permission=permission,
        require_proxy=require_proxy,
        require_profile=require_profile,
    )
    missing = [flag for flag in required if flag not in help_output]
    if missing:
        raise ValueError(
            f"{Path(executable).name} lacks required route capabilities: "
            f"{', '.join(missing)}"
        )
    return required


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


def _client(
    *,
    config: OneToolConfig,
    target: ResolvedTarget,
) -> ExternalClientConfig:
    """Return the configured client for one resolved harness."""
    if config.code is None:
        raise ValueError("Code routing is not configured")
    return (
        config.code.clients.claude
        if target.harness == "claude"
        else config.code.clients.codex
    )


def _secret(
    *,
    config: OneToolConfig,
    secret_resolver: Callable[[str], str | None],
) -> str:
    """Resolve the proxy inference secret without exposing its value."""
    if config.code is None:
        raise ValueError("Code routing is not configured")
    if config.code.proxy is None:
        raise ValueError("Proxy routing is not configured")
    name = config.code.proxy.secret_name
    value = secret_resolver(name)
    if not value:
        raise ValueError(f"Named inference secret {name!r} is not configured")
    return value


def _user_arguments(
    *,
    client: ExternalClientConfig,
    passthrough: tuple[str, ...],
    harness: Harness,
) -> tuple[str, ...]:
    """Validate and combine configured and explicit opaque arguments."""
    validate_client_arguments(
        harness=harness,
        arguments=client.additional_arguments,
    )
    validate_client_arguments(harness=harness, arguments=passthrough)
    return (*client.additional_arguments, *passthrough)


def _claude_invocation(
    *,
    config: OneToolConfig,
    target: ResolvedTarget,
    executable: str,
    client: ExternalClientConfig,
    passthrough: tuple[str, ...],
    secret_resolver: Callable[[str], str | None],
) -> LaunchInvocation:
    """Build one proxied Claude Code invocation."""
    if config.code is None or config.code.proxy is None:
        raise ValueError("Proxy routing is not configured")
    if target.kind != "route":
        raise ValueError("Claude supports proxy routes only")
    secret = _secret(config=config, secret_resolver=secret_resolver)
    model_id = target.model.id
    if target.model.claude_context == "1m":
        model_id = f"{model_id}[1m]"
    argv = [executable, "--model", model_id]
    if target.permission == "bypass":
        argv.append("--dangerously-skip-permissions")
    argv.extend(
        _user_arguments(
            client=client,
            passthrough=passthrough,
            harness="claude",
        )
    )
    set_values = {
        "ANTHROPIC_BASE_URL": config.code.proxy.base_url,
        "ANTHROPIC_AUTH_TOKEN": secret,
        "ANTHROPIC_DEFAULT_OPUS_MODEL": model_id,
        "ANTHROPIC_DEFAULT_SONNET_MODEL": model_id,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": model_id,
    }
    if target.model.claude_context == "1m":
        set_values["ANTHROPIC_MODEL"] = model_id
        if target.model.auto_compact_window is not None:
            set_values["CLAUDE_CODE_AUTO_COMPACT_WINDOW"] = str(
                target.model.auto_compact_window
            )
    elif target.model.claude_context == "standard":
        set_values["CLAUDE_CODE_DISABLE_1M_CONTEXT"] = "1"
    return LaunchInvocation(
        target=target,
        executable=executable,
        argv=tuple(argv),
        environment=EnvironmentDelta.create(
            remove=set(_CLAUDE_CLEAN_ENV),
            set_values=set_values,
        ),
        working_directory=None,
    )


def _codex_invocation(
    *,
    config: OneToolConfig,
    target: ResolvedTarget,
    executable: str,
    client: ExternalClientConfig,
    passthrough: tuple[str, ...],
    secret_resolver: Callable[[str], str | None],
) -> LaunchInvocation:
    """Build one proxied or direct-profile Codex invocation."""
    if config.code is None:
        raise ValueError("Code routing is not configured")
    set_values: dict[str, str] = {}
    client_home = getattr(client, "home_path", None)
    if client_home is not None:
        set_values["CODEX_HOME"] = _checked_directory(
            config,
            client_home,
            setting="code.clients.codex.home_path",
        )

    argv = [executable]
    if target.kind == "route":
        if config.code.proxy is None:
            raise ValueError("Proxy routing is not configured")
        secret = _secret(config=config, secret_resolver=secret_resolver)
        set_values[_PRIVATE_PROVIDER_KEY] = secret
        overrides = (
            ("model_provider", _toml_string(_PROVIDER_ID)),
            (
                f"model_providers.{_PROVIDER_ID}.name",
                _toml_string("OneTool Proxy"),
            ),
            (
                f"model_providers.{_PROVIDER_ID}.base_url",
                _toml_string(config.code.proxy.base_url),
            ),
            (
                f"model_providers.{_PROVIDER_ID}.env_key",
                _toml_string(_PRIVATE_PROVIDER_KEY),
            ),
            (
                f"model_providers.{_PROVIDER_ID}.wire_api",
                _toml_string("responses"),
            ),
        )
        for key, value in overrides:
            argv.extend(("-c", f"{key}={value}"))
    else:
        argv.extend(("--profile", target.name))
    argv.extend(("--model", target.model.id))
    if target.permission == "bypass":
        argv.append("--dangerously-bypass-approvals-and-sandbox")
    argv.extend(
        _user_arguments(
            client=client,
            passthrough=passthrough,
            harness="codex",
        )
    )
    return LaunchInvocation(
        target=target,
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
    target: ResolvedTarget,
    passthrough: tuple[str, ...],
    secret_resolver: Callable[[str], str | None],
) -> LaunchInvocation:
    """Build a local invocation without network or capability subprocesses."""
    client = _client(config=config, target=target)
    executable = resolve_client_executable(client.executable)
    working_directory = (
        _checked_directory(
            config,
            client.working_directory,
            setting=f"code.clients.{target.harness}.working_directory",
        )
        if client.working_directory is not None
        else None
    )
    builder = (
        _claude_invocation if target.harness == "claude" else _codex_invocation
    )
    invocation = builder(
        config=config,
        target=target,
        executable=executable,
        client=client,
        passthrough=passthrough,
        secret_resolver=secret_resolver,
    )
    return LaunchInvocation(
        target=invocation.target,
        executable=invocation.executable,
        argv=invocation.argv,
        environment=invocation.environment,
        working_directory=working_directory,
    )


def replace_process(
    *,
    invocation: LaunchInvocation,
    parent_environment: Mapping[str, str] | None = None,
) -> NoReturn:
    """Replace OneTool with the validated harness invocation."""
    parent = os.environ if parent_environment is None else parent_environment
    environment = invocation.environment.apply(parent)
    if invocation.working_directory is not None:
        os.chdir(invocation.working_directory)
    os.execvpe(invocation.executable, invocation.argv, environment)


__all__ = [
    "build_invocation",
    "check_client_capabilities",
    "replace_process",
    "required_route_capabilities",
    "resolve_client_executable",
    "run_capability_command",
]
