"""Strict local YAML loading. No transport, keyring or OAuth side effects."""

from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, Self
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from yaml.nodes import MappingNode
from yaml.tokens import AliasToken, AnchorToken


class ConfigError(ValueError):
    """An input error whose message contains no input values."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class OAuthConfig(StrictModel):
    type: Literal["oauth"]
    scopes: list[str] = Field(default_factory=list)


class ArgumentCuration(StrictModel):
    description: str | None = None
    default: str | int | float | bool | None = None
    hide: bool = False
    required: Literal[True] | None = None
    examples: list[Any] | None = None


class ToolCuration(StrictModel):
    description: str | None = None
    enabled: bool = True
    tags: list[str] | None = None
    meta: dict[str, Any] | None = None
    arguments: dict[str, ArgumentCuration] = Field(default_factory=dict)


class Server(StrictModel):
    description: str | None = None
    source: str | None = None
    instructions: str | None = None
    tools: dict[str, ToolCuration] = Field(default_factory=dict)
    include_tags: list[str] | None = None
    exclude_tags: list[str] | None = None

    @field_validator("tools")
    @classmethod
    def nonempty_tools(cls, value: dict[str, ToolCuration]) -> dict[str, ToolCuration]:
        if any(not name.strip() for name in value):
            raise ValueError("tool names must not be empty")
        return value

    enabled: bool = True
    timeout_seconds: Annotated[float, Field(gt=0, le=3600, allow_inf_nan=False)] = 30


class StdioServer(Server):
    transport: Literal["stdio"]
    command: Annotated[str, Field(min_length=1)]
    args: list[str] = Field(default_factory=list)
    cwd: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    inherit_env: bool = False

    @field_validator("command")
    @classmethod
    def command_not_blank(cls, value: str) -> str:
        if not value.strip() or "${" in value or "\x00" in value:
            raise ValueError("command must be a literal executable name or path")
        return value


class HttpServer(Server):
    transport: Literal["http"]
    url: str
    headers: dict[str, str] = Field(default_factory=dict)
    auth: OAuthConfig | None = None

    @model_validator(mode="after")
    def auth_conflict(self) -> Self:
        if self.auth and any(key.lower() == "authorization" for key in self.headers):
            raise ValueError("Authorization header conflicts with OAuth")
        return self


class Execution(StrictModel):
    timeout_seconds: Annotated[float, Field(gt=0, le=3600, allow_inf_nan=False)] = 60
    max_output_bytes: Annotated[int, Field(ge=1024, le=1048576)] = 65536
    max_tool_calls: Annotated[int, Field(ge=1, le=1000)] = 50


class LoggingConfig(StrictModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    file: str | None = None


class GatewayConfig(StrictModel):
    env: dict[str, str] = Field(default_factory=dict)
    instructions: str = (
        "Use help/search to discover exact tools and get_schema for parameters. "
        "Execute Python with await server.tool(**kwargs) or call_tool. "
        "Use onetool_status for diagnostics, onetool_servers for session controls, "
        "and onetool_results to recover stored output. Never replay unknown outcomes."
    )
    version: int
    servers: dict[str, Annotated[StdioServer | HttpServer, Field(discriminator="transport")]]
    execution: Execution = Field(default_factory=Execution)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @field_validator("version")
    @classmethod
    def v4_only(cls, value: int) -> int:
        if value != 4:
            raise ValueError("version must be 4")
        return value

    @field_validator("servers")
    @classmethod
    def server_names(
        cls, values: dict[str, StdioServer | HttpServer]
    ) -> dict[str, StdioServer | HttpServer]:
        for name in values:
            if name in {
                "onetool",
                "call_tool",
                "call_tools",
                "set_format",
                "results",
            } or not re.fullmatch(r"[a-z][a-z0-9_]*", name):
                raise ValueError("invalid or reserved server name")
        return values


class UniqueLoader(yaml.SafeLoader):
    """SafeLoader which rejects duplicate mapping keys before schema validation."""

    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[Any, Any]:
        keys: set[Any] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                if key in keys:
                    raise ConfigError("duplicate YAML key")
                keys.add(key)
            except TypeError:
                raise ConfigError("YAML mapping keys must be scalar") from None
        return super().construct_mapping(node, deep=deep)


def _schema_error(exc: ValidationError) -> ConfigError:
    # Pydantic's usual string form includes rejected values. Never emit it.
    failures = []
    for item in exc.errors(include_input=False, include_context=False, include_url=False):
        location = ".".join(str(part) for part in item["loc"])
        failures.append(f"{location or 'config'}: {item['type']}")
    return ConfigError("invalid config: " + "; ".join(failures))


def _validate_url(value: str) -> None:
    try:
        if any(char.isspace() or ord(char) < 32 for char in value):
            raise ValueError
        parts = urlsplit(value)
        host = parts.hostname
        if not host or parts.username is not None or parts.password is not None or parts.fragment:
            raise ValueError
        _ = parts.port  # Validate port syntax without connecting.
        loopback = host.lower() == "localhost"
        try:
            loopback = loopback or ipaddress.ip_address(host).is_loopback
        except ValueError:
            pass
        if parts.scheme != "https" and not (parts.scheme == "http" and loopback):
            raise ValueError
    except ValueError:
        raise ConfigError(
            "HTTP URL must use HTTPS or loopback HTTP, without credentials or fragment"
        ) from None


def _path(value: str, directory: Path) -> str:
    path = Path(value)
    return os.path.abspath(directory / path)


if TYPE_CHECKING:
    from onetool.secrets import Variables


@dataclass(frozen=True)
class LoadedConfig:
    path: Path
    model: GatewayConfig
    env_names: frozenset[str]
    secret_values: tuple[str, ...]
    variables: Variables | None = None
    templates: dict[str, StdioServer | HttpServer] = field(default_factory=dict)
    server_errors: dict[str, str] = field(default_factory=dict)
    secrets_path: Path | None = None

    def redacted_env(self) -> dict[str, bool]:
        return {
            name: self.variables.present(name) if self.variables else name in os.environ
            for name in sorted(self.env_names)
        }

    def resolve_server(self, name: str) -> StdioServer | HttpServer:
        if name in self.server_errors:
            raise ConfigError(self.server_errors[name])
        template = self.templates.get(name, self.model.servers[name])
        if self.variables is None:
            return template
        return resolve_values(template, self.variables, runtime=True)


def read_document(path: Path) -> dict[str, Any]:
    """Safe single-document mapping loader shared by config and secrets."""
    try:
        with path.open("rb") as stream:
            raw = stream.read(1048577)
    except OSError as exc:
        raise ConfigError(f"cannot read config: {type(exc).__name__}") from None
    if len(raw) > 1048576:
        raise ConfigError("config exceeds 1 MiB")
    try:
        text = raw.decode("utf-8")
        if any(isinstance(token, AliasToken | AnchorToken) for token in yaml.scan(text)):
            raise ConfigError("YAML anchors and aliases are not supported")
        document = yaml.load(text, Loader=UniqueLoader)
    except (yaml.YAMLError, UnicodeError) as exc:
        mark = getattr(exc, "problem_mark", None)
        location = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
        raise ConfigError("invalid safe YAML" + location) from None
    if not isinstance(document, dict):
        raise ConfigError("config root must be a mapping")
    return document


def resolve_values(
    server: StdioServer | HttpServer, variables: Variables, *, runtime: bool
) -> StdioServer | HttpServer:
    def substitute(value: str) -> str:
        return variables.text(value, runtime=runtime)

    if isinstance(server, StdioServer):
        env = {key: substitute(value) for key, value in {**variables.shared, **server.env}.items()}
        variables.masks.update(value for value in env.values() if len(value) >= 8)
        return server.model_copy(update={"args": [substitute(v) for v in server.args], "env": env})
    url = substitute(server.url)
    if runtime or "${" not in url:
        _validate_url(url)
    headers = {key: substitute(value) for key, value in server.headers.items()}
    variables.masks.update(value for value in headers.values() if len(value) >= 8)
    if urlsplit(url).query:
        variables.masks.add(url)
        variables.masks.update(
            part.partition("=")[2]
            for part in urlsplit(url).query.split("&")
            if part.partition("=")[2]
        )
    return server.model_copy(update={"url": url, "headers": headers})


def load_config(
    path: Path, *, secrets_path: Path | None = None, defer_errors: bool = False
) -> LoadedConfig:
    from onetool.secrets import Variables

    path = path.absolute()
    document = read_document(path)
    try:
        model = GatewayConfig.model_validate(document)
    except ValidationError as exc:
        raise _schema_error(exc) from None

    variables = Variables(secrets_path.absolute() if secrets_path else None, model.env)
    resolved: dict[str, StdioServer | HttpServer] = {}
    templates: dict[str, StdioServer | HttpServer] = {}
    errors: dict[str, str] = {}
    for name, server in model.servers.items():
        if isinstance(server, StdioServer):
            command = server.command
            if "/" in command or "\\" in command:
                command = _path(command, path.parent)
            server = server.model_copy(
                update={
                    "command": command,
                    "cwd": _path(server.cwd, path.parent) if server.cwd is not None else None,
                }
            )
        templates[name] = server
        try:
            resolved[name] = resolve_values(server, variables, runtime=False)
        except ConfigError as exc:
            if not defer_errors:
                raise
            errors[name] = str(exc)
            resolved[name] = server
    logging = model.logging
    if logging.file is not None:
        logging = logging.model_copy(update={"file": _path(logging.file, path.parent)})
    model = model.model_copy(update={"servers": resolved, "logging": logging})
    return LoadedConfig(
        path,
        model,
        frozenset(variables.names),
        tuple(sorted(variables.masks, key=len, reverse=True)),
        variables,
        templates,
        errors,
        secrets_path.absolute() if secrets_path else None,
    )
