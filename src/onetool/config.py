"""Strict local YAML loading. No transport, keyring or OAuth side effects."""

from __future__ import annotations

import ipaddress
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Literal, Self
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


class Server(StrictModel):
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


class LoggingConfig(StrictModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    file: str | None = None


class GatewayConfig(StrictModel):
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
            if name == "onetool" or not re.fullmatch(r"[a-z][a-z0-9_]*", name):
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


@dataclass(frozen=True)
class LoadedConfig:
    path: Path
    model: GatewayConfig
    env_names: frozenset[str]
    secret_values: tuple[str, ...]

    def redacted_env(self) -> dict[str, bool]:
        return {name: name in os.environ for name in sorted(self.env_names)}


def load_config(path: Path) -> LoadedConfig:
    """Read at most 1 MiB, validate, substitute allowed values, resolve local paths."""
    path = path.absolute()
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
    try:
        model = GatewayConfig.model_validate(document)
    except ValidationError as exc:
        raise _schema_error(exc) from None

    env_names: set[str] = set()
    secrets: set[str] = set()

    def substitute(value: str) -> str:
        def replace(match: re.Match[str]) -> str:
            name = match.group(1)
            env_names.add(name)
            if name not in os.environ:
                raise ConfigError(f"environment variable is not set: {name}")
            replacement = os.environ[name]
            if replacement:
                secrets.add(replacement)
            return replacement

        return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", replace, value)

    resolved: dict[str, StdioServer | HttpServer] = {}
    for name, server in model.servers.items():
        if isinstance(server, StdioServer):
            args = [substitute(item) for item in server.args]
            env = {key: substitute(value) for key, value in server.env.items()}
            secrets.update(value for value in env.values() if value)
            command = server.command
            if "/" in command or "\\" in command:
                command = _path(command, path.parent)
            resolved[name] = server.model_copy(
                update={
                    "command": command,
                    "args": args,
                    "env": env,
                    "cwd": _path(server.cwd, path.parent) if server.cwd is not None else None,
                }
            )
        else:
            url = substitute(server.url)
            _validate_url(url)
            headers = {key: substitute(value) for key, value in server.headers.items()}
            secrets.update(value for value in headers.values() if value)
            # Error text must not disclose a URL's query credentials.
            if urlsplit(url).query:
                secrets.add(url)
                secrets.update(
                    value
                    for _, _, value in (
                        item.partition("=") for item in urlsplit(url).query.split("&")
                    )
                    if value
                )
            resolved[name] = server.model_copy(update={"url": url, "headers": headers})
    logging = model.logging
    if logging.file is not None:
        logging = logging.model_copy(update={"file": _path(logging.file, path.parent)})
    model = model.model_copy(update={"servers": resolved, "logging": logging})
    return LoadedConfig(
        path, model, frozenset(env_names), tuple(sorted(secrets, key=len, reverse=True))
    )
