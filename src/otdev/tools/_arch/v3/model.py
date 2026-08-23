"""Typed schema-v3 architecture models."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        pattern=r"^[A-Za-z0-9._-]+$",
    ),
]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
PropertyValue = Text | list[Text]


def _strip_direction(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


Direction = Annotated[
    Literal[
        "provider_to_consumer",
        "consumer_to_provider",
        "bidirectional",
        "unspecified",
    ],
    BeforeValidator(_strip_direction),
]


class StrictModel(BaseModel):
    """Base for schema objects that reject unknown fields."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class NamedItem(StrictModel):
    """Fields shared by named catalog and architecture rows."""

    id: Identifier
    name: Text
    description: Text | None = None
    tags: list[Text] = Field(default_factory=list)
    properties: dict[Text, PropertyValue] = Field(default_factory=dict)


class TemporalNamedItem(NamedItem):
    """Named row with an authored half-open milestone interval."""

    from_: Identifier | None = Field(default=None, alias="from")
    until: Identifier | None = None


class Milestone(NamedItem):
    """Named point at which an architecture may change."""


class Timeline(StrictModel):
    """Ordered milestone scenario."""

    id: Identifier
    milestones: list[Identifier]


class System(TemporalNamedItem):
    """Highest-level software boundary."""


class Subsystem(TemporalNamedItem):
    """Logical division of one system."""

    system: Identifier


class Component(TemporalNamedItem):
    """Leaf runtime or data boundary owned by one subsystem."""

    subsystem: Identifier


class User(TemporalNamedItem):
    """Human role, persona, or group."""


class Interface(TemporalNamedItem):
    """Realised bilateral connection between two architecture entities."""

    provider: Identifier
    consumer: Identifier
    call_direction: Direction = "unspecified"
    data_flow: Direction = "unspecified"


class Relationship(StrictModel):
    """Semantic statement read as source, action, target."""

    id: Identifier
    action: Text
    source: Identifier
    target: Identifier
    from_: Identifier | None = Field(default=None, alias="from")
    until: Identifier | None = None
    description: Text | None = None
    tags: list[Text] = Field(default_factory=list)
    properties: dict[Text, PropertyValue] = Field(default_factory=dict)


class Architecture(StrictModel):
    """Complete authored schema-v3 architecture."""

    schema_version: Literal[3]
    milestones: list[Milestone]
    timelines: list[Timeline] | None = None
    systems: list[System]
    subsystems: list[Subsystem]
    components: list[Component]
    users: list[User]
    interfaces: list[Interface]
    relationships: list[Relationship]
