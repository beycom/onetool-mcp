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


CallDirection = Annotated[
    Literal["consumer_to_provider", "provider_to_consumer"],
    BeforeValidator(_strip_direction),
]
DataFlowDirection = Annotated[
    Literal["provider_to_consumer", "consumer_to_provider", "bidirectional"],
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
    """Named row with an authored inclusive milestone interval."""

    start_in: Identifier | None = None
    end_in: Identifier | None = None


class Milestone(NamedItem):
    """Named point at which an architecture may change."""


class Timeline(StrictModel):
    """Ordered milestone scenario."""

    id: Identifier
    milestones: list[Identifier]


class Theme(StrictModel):
    """Authored presentation colors retained for located validation."""

    kinds: dict[str, object]


class System(TemporalNamedItem):
    """Highest-level software boundary."""


class Subsystem(TemporalNamedItem):
    """Logical grouping of related containers within one system."""

    parent: Identifier


class Container(TemporalNamedItem):
    """Deployable boundary nested under a system or subsystem."""

    parent: Identifier


class Component(TemporalNamedItem):
    """Leaf runtime or data boundary owned by one container."""

    container: Identifier


class Code(TemporalNamedItem):
    """Code-level element owned by one component."""

    component: Identifier


class User(TemporalNamedItem):
    """Human role, persona, or group."""


class Interface(TemporalNamedItem):
    """Realised bilateral connection between two architecture entities."""

    provider: Identifier
    consumer: Identifier
    call_direction: CallDirection = "consumer_to_provider"
    data_flow_direction: DataFlowDirection = "provider_to_consumer"


class Relationship(StrictModel):
    """Semantic statement read as source, action, target."""

    id: Identifier
    action: Text
    source: Identifier
    target: Identifier
    start_in: Identifier | None = None
    end_in: Identifier | None = None
    description: Text | None = None
    tags: list[Text] = Field(default_factory=list)
    properties: dict[Text, PropertyValue] = Field(default_factory=dict)


class Architecture(StrictModel):
    """Complete authored schema-v3 architecture."""

    schema_version: Literal[3]
    milestones: list[Milestone]
    timelines: list[Timeline] | None = None
    theme: Theme | None = None
    systems: list[System]
    subsystems: list[Subsystem]
    containers: list[Container]
    components: list[Component]
    code: list[Code]
    users: list[User]
    interfaces: list[Interface]
    relationships: list[Relationship]
