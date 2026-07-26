"""Typed OneTool pack, skill, requirement, and help-topic catalog.

This module is safe to import in a base OneTool installation. It contains only
reviewed relationships and does not import optional pack implementations.
"""

from __future__ import annotations

import inspect
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    model_validator,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


class _FrozenModel(BaseModel):
    """Strict immutable base for catalog records."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class PackStability(StrEnum):
    """Release stability of a built-in pack."""

    STABLE = "stable"
    BETA = "beta"


class InstallExtra(StrEnum):
    """OneTool distribution group containing a pack."""

    CORE = "core"
    UTIL = "[util]"
    DEV = "[dev]"
    SCRAPE = "[scrape]"


class SkillRole(StrEnum):
    """Operating role of a distributed OneTool skill."""

    SHARED_REFERENCE = "shared-reference"
    CATALOG_ROUTER = "catalog-router"
    SETUP = "setup"
    RUNTIME_OPERATIONS = "runtime-operations"
    PROXY_LIFECYCLE = "proxy-lifecycle"
    CAPABILITY_OWNER = "capability-owner"
    CROSS_PACK_SELECTION = "cross-pack-selection"


class ProfileRole(StrEnum):
    """Explicit installation-profile placement for cross-catalog skills."""

    DERIVED = "derived"
    FOUNDATION = "foundation"
    CORE = "core"


class HelpTopicKind(StrEnum):
    """How runtime help obtains a topic's deterministic content."""

    DYNAMIC = "dynamic"
    RESOURCE = "resource"
    ADAPTER = "adapter"


class RequirementKind(StrEnum):
    """Supported normalized pack prerequisite kinds."""

    LIB = "lib"
    CLI = "cli"
    SECRET = "secret"
    SERVER = "server"
    CONFIG = "config"


class InvocationPolicy(_FrozenModel):
    """Whether a skill may be invoked by users and models."""

    user_invocable: bool
    model_invocable: bool


class ActivationCondition(_FrozenModel):
    """Config condition controlling whether a requirement is active."""

    field: str = Field(min_length=1)
    equals: Any = True


class PackRequirement(_FrozenModel):
    """One normalized prerequisite declared by a pack."""

    kind: RequirementKind
    name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    install_extra: InstallExtra | None = None
    import_name: str | None = None
    executable: str | None = None
    authoritative_url: str | None = None
    optional: bool = False
    activation: ActivationCondition | None = None

    @model_validator(mode="after")
    def _validate_kind_fields(self) -> PackRequirement:
        if self.kind is RequirementKind.LIB and not self.import_name:
            raise ValueError("lib requirement must declare import_name")
        if self.kind is RequirementKind.LIB and self.install_extra is None:
            raise ValueError("lib requirement must declare install_extra")
        if self.kind is RequirementKind.CLI and not self.executable:
            raise ValueError("cli requirement must declare executable")
        if self.kind is not RequirementKind.LIB and self.import_name is not None:
            raise ValueError("import_name is valid only for lib requirements")
        if self.kind is not RequirementKind.CLI and self.executable is not None:
            raise ValueError("executable is valid only for cli requirements")
        if self.kind is not RequirementKind.CLI and self.authoritative_url is not None:
            raise ValueError("authoritative_url is valid only for cli requirements")
        return self


_REQUIREMENTS_ADAPTER = TypeAdapter(list[PackRequirement])


def parse_pack_requirements(
    declaration: object,
    *,
    source: str,
) -> tuple[PackRequirement, ...]:
    """Parse the sole supported literal ``__ot_requires__`` declaration shape.

    The outer value must be a list and every item must be a mapping accepted by
    :class:`PackRequirement`. Rejecting tuples, strings, and kind-keyed legacy
    mappings here keeps registry discovery, runtime loading, setup diagnostics,
    and extension validation on one contract.
    """

    if not isinstance(declaration, list):
        raise ValueError(
            f"{source}: __ot_requires__ must be a list of normalized requirement "
            "records"
        )
    if any(not isinstance(item, dict) for item in declaration):
        raise ValueError(
            f"{source}: each __ot_requires__ item must be a normalized requirement "
            "mapping"
        )
    try:
        return tuple(_REQUIREMENTS_ADAPTER.validate_python(declaration))
    except ValidationError as exc:
        raise ValueError(f"{source}: invalid __ot_requires__: {exc}") from exc


class ConfigHook(_FrozenModel):
    """Import path for a pack's authoritative Pydantic config model."""

    model: str = Field(min_length=1)


class HelpTopicDescriptor(_FrozenModel):
    """A deterministic runtime-help topic registered for a pack."""

    name: str = Field(pattern=r"^[a-z][a-z0-9_-]*$")
    description: str = Field(min_length=1)
    kind: HelpTopicKind
    source: str = Field(min_length=1)


class SkillCatalogEntry(_FrozenModel):
    """Reviewed metadata for one distributed skill."""

    name: str = Field(pattern=r"^ot-[a-z0-9]+(?:-[a-z0-9]+)*$")
    role: SkillRole
    profile_role: ProfileRole = ProfileRole.DERIVED
    invocation: InvocationPolicy
    purpose: str = Field(min_length=1)


class PackGuidanceEntry(_FrozenModel):
    """Reviewed non-derivable guidance relationships for one built-in pack."""

    pack: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    display_name: str = Field(min_length=1)
    extra: InstallExtra
    default_summary: str = Field(min_length=1)
    skill_owner: str | None
    doc_slug: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    stability: PackStability = PackStability.STABLE
    skill_exclusion_reason: str | None = None
    topics: tuple[HelpTopicDescriptor, ...]
    config_hook: ConfigHook | None = None

    @model_validator(mode="after")
    def _validate_guidance_owner(self) -> PackGuidanceEntry:
        if self.stability is PackStability.STABLE and not self.skill_owner:
            raise ValueError("stable pack must declare a skill owner")
        if self.skill_owner is None and not self.skill_exclusion_reason:
            raise ValueError("ownerless pack must declare skill_exclusion_reason")
        if self.skill_owner is not None and self.skill_exclusion_reason is not None:
            raise ValueError("owned pack cannot declare skill_exclusion_reason")
        topic_names = [topic.name for topic in self.topics]
        if len(topic_names) != len(set(topic_names)):
            raise ValueError("pack help topics must have unique names")
        return self


class RuntimePackFacts(_FrozenModel):
    """Runtime-derived facts joined to a reviewed pack entry."""

    aliases: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()
    signatures: dict[str, str] = Field(default_factory=dict)
    doc_slug: str | None = None
    requirements: tuple[PackRequirement, ...] = ()
    config_hook: ConfigHook | None = None
    config_schema: dict[str, Any] = Field(default_factory=dict)
    config_defaults: dict[str, Any] = Field(default_factory=dict)
    active_config: dict[str, Any] = Field(default_factory=dict)
    config_errors: tuple[dict[str, str], ...] = ()
    proxy_state: dict[str, Any] = Field(default_factory=dict)


class ComposedPackGuidance(_FrozenModel):
    """One catalog entry composed with its current runtime facts."""

    guidance: PackGuidanceEntry
    runtime: RuntimePackFacts | None

    @property
    def available(self) -> bool:
        """Whether this pack is present in the loaded runtime registry."""

        return self.runtime is not None


def _topic(
    name: str,
    description: str,
    *,
    kind: HelpTopicKind = HelpTopicKind.DYNAMIC,
    source: str | None = None,
) -> HelpTopicDescriptor:
    return HelpTopicDescriptor(
        name=name,
        description=description,
        kind=kind,
        source=source or f"catalog.{name}",
    )


def _standard_topics(
    *additional: HelpTopicDescriptor,
) -> tuple[HelpTopicDescriptor, ...]:
    return (
        _topic("overview", "Capability boundary, strengths, tools, and documentation"),
        _topic("workflow", "Safe operating sequence, verification, and recovery"),
        _topic("setup", "Live prerequisite and readiness diagnostics"),
        _topic("config", "Typed configuration schema and redacted active values"),
        *additional,
    )


_MODEL = InvocationPolicy(user_invocable=False, model_invocable=True)
_USER_MODEL = InvocationPolicy(user_invocable=True, model_invocable=True)
_USER_ONLY = InvocationPolicy(user_invocable=True, model_invocable=False)


SKILL_CATALOG: tuple[SkillCatalogEntry, ...] = (
    SkillCatalogEntry(
        name="ot-ref",
        role=SkillRole.SHARED_REFERENCE,
        profile_role=ProfileRole.FOUNDATION,
        invocation=_MODEL,
        purpose="Shared OneTool call, discovery, safety, and recovery reference",
    ),
    SkillCatalogEntry(
        name="ot-ask",
        role=SkillRole.CATALOG_ROUTER,
        profile_role=ProfileRole.FOUNDATION,
        invocation=_USER_ONLY,
        purpose="Route a user situation to the smallest applicable OneTool skill",
    ),
    SkillCatalogEntry(
        name="ot-setup",
        role=SkillRole.SETUP,
        profile_role=ProfileRole.FOUNDATION,
        invocation=_USER_MODEL,
        purpose="Diagnose and guide approved OneTool installation and configuration work",
    ),
    SkillCatalogEntry(
        name="ot-runtime",
        role=SkillRole.RUNTIME_OPERATIONS,
        profile_role=ProfileRole.CORE,
        invocation=_USER_MODEL,
        purpose="Operate, observe, and recover the OneTool root runtime",
    ),
    SkillCatalogEntry(
        name="ot-mcp-proxy",
        role=SkillRole.PROXY_LIFECYCLE,
        invocation=_USER_MODEL,
        purpose="Configure, use, and recover arbitrary outbound MCP proxy servers",
    ),
    *(
        SkillCatalogEntry(
            name=name,
            role=SkillRole.CAPABILITY_OWNER,
            invocation=_MODEL,
            purpose=purpose,
        )
        for name, purpose in (
            ("ot-context", "Store and retrieve large structured tool results"),
            ("ot-forge", "Create and statically validate OneTool extensions"),
            ("ot-image", "Load, inspect, compare, and manage image handles"),
            ("ot-llm", "Transform text or files with a configured language model"),
            ("ot-secrets", "Manage OneTool secret storage safely"),
            ("ot-convert", "Convert office and document formats to useful outputs"),
            ("ot-excel", "Inspect and mutate Excel workbooks with readback"),
            ("ot-file", "Resolve, inspect, search, and mutate files safely"),
            ("ot-knowledge", "Build, maintain, query, and use knowledge bases"),
            ("ot-mem", "Maintain persistent topic-based memory"),
            ("ot-whiteboard", "Create and operate live Excalidraw whiteboards"),
            ("ot-arch", "Validate and generate architecture model artifacts"),
            ("ot-db", "Inspect and query databases with explicit mutation intent"),
            ("ot-diagram", "Select and render diagrams with provider-aware safety"),
            ("ot-localhist", "Maintain project-local snapshot history"),
        )
    ),
    SkillCatalogEntry(
        name="ot-research",
        role=SkillRole.CROSS_PACK_SELECTION,
        invocation=_MODEL,
        purpose="Select and sequence research, documentation, and package sources",
    ),
    SkillCatalogEntry(
        name="ot-browser-guidance",
        role=SkillRole.CROSS_PACK_SELECTION,
        invocation=_MODEL,
        purpose="Use OneTool browser annotation companions with the matching MCP proxy",
    ),
)


PACK_CATALOG: tuple[PackGuidanceEntry, ...] = (
    PackGuidanceEntry(
        pack="ot",
        display_name="OT Core",
        extra=InstallExtra.CORE,
        default_summary="Discover, inspect, operate, and troubleshoot OneTool",
        skill_owner="ot-ref",
        doc_slug="ot_core",
        topics=_standard_topics(
            _topic("security", "Trusted-execution boundary and security preflight workflow")
        ),
    ),
    PackGuidanceEntry(
        pack="arch",
        display_name="Arch",
        extra=InstallExtra.DEV,
        default_summary="Validate and generate architecture models, round trips, and bundles",
        skill_owner="ot-arch",
        doc_slug="arch",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="ot_context",
        display_name="OT Context",
        extra=InstallExtra.CORE,
        default_summary="Store and query large structured results without filling context",
        skill_owner="ot-context",
        doc_slug="ot_context",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="ot_forge",
        display_name="OT Forge",
        extra=InstallExtra.CORE,
        default_summary="Create and statically validate OneTool extension packs",
        skill_owner="ot-forge",
        doc_slug="ot_forge",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="ot_image",
        display_name="OT Image",
        extra=InstallExtra.CORE,
        default_summary="Load, inspect, compare, and manage images through durable handles",
        skill_owner="ot-image",
        doc_slug="ot_image",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="ot_llm",
        display_name="OT LLM",
        extra=InstallExtra.CORE,
        default_summary="Transform text or files with a configured language model",
        skill_owner="ot-llm",
        doc_slug="ot_llm",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="ot_secrets",
        display_name="OT Secrets",
        extra=InstallExtra.CORE,
        default_summary="Initialize, audit, store, retrieve, rotate, and remove secrets",
        skill_owner="ot-secrets",
        doc_slug="ot_secrets",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="ot_servers",
        display_name="OT Servers",
        extra=InstallExtra.CORE,
        default_summary="Inspect and control configured outbound MCP proxy servers",
        skill_owner="ot-mcp-proxy",
        doc_slug="ot_servers",
        topics=_standard_topics(
            _topic("resources", "Live proxied MCP resource inventory"),
            _topic("prompts", "Live proxied MCP prompt inventory"),
        ),
    ),
    PackGuidanceEntry(
        pack="ot_timer",
        display_name="OT Timer",
        extra=InstallExtra.CORE,
        default_summary="Measure named operation spans and inspect recorded timings",
        skill_owner="ot-ref",
        doc_slug="ot_timer",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="brave",
        display_name="Brave",
        extra=InstallExtra.UTIL,
        default_summary="Search the web, news, images, and videos with batch support",
        skill_owner="ot-research",
        doc_slug="brave",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="convert",
        display_name="Convert",
        extra=InstallExtra.UTIL,
        default_summary="Convert PDF and office documents into useful text formats",
        skill_owner="ot-convert",
        doc_slug="convert",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="excel",
        display_name="Excel",
        extra=InstallExtra.UTIL,
        default_summary="Inspect and mutate Excel workbook content and structure",
        skill_owner="ot-excel",
        doc_slug="excel",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="file",
        display_name="File",
        extra=InstallExtra.UTIL,
        default_summary="Resolve, read, search, edit, move, copy, and delete files",
        skill_owner="ot-file",
        doc_slug="file",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="ground",
        display_name="Ground",
        extra=InstallExtra.UTIL,
        default_summary="Research web, developer, documentation, and Reddit sources with citations",
        skill_owner="ot-research",
        doc_slug="ground",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="knowledge",
        display_name="Knowledge",
        extra=InstallExtra.UTIL,
        default_summary="Build and query portable hybrid-search knowledge bases",
        skill_owner="ot-knowledge",
        doc_slug="knowledge",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="mem",
        display_name="Mem",
        extra=InstallExtra.UTIL,
        default_summary="Maintain persistent topic memory with search, history, and recovery",
        skill_owner="ot-mem",
        doc_slug="mem",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="tavily",
        display_name="Tavily",
        extra=InstallExtra.UTIL,
        default_summary="Search, extract, and run deeper web research with Tavily",
        skill_owner="ot-research",
        doc_slug="tavily",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="chrome_util",
        display_name="Chrome DevTools Util",
        extra=InstallExtra.DEV,
        default_summary="Annotate and highlight pages through a Chrome DevTools MCP proxy",
        skill_owner="ot-browser-guidance",
        doc_slug="chrome-util",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="console",
        display_name="Console",
        extra=InstallExtra.CORE,
        default_summary="Publish inline artifacts to a connected beta OneTool Console app",
        skill_owner=None,
        doc_slug="console",
        stability=PackStability.BETA,
        skill_exclusion_reason="Console is beta and must not appear in distributed skills",
        topics=(),
    ),
    PackGuidanceEntry(
        pack="context7",
        display_name="Context7",
        extra=InstallExtra.DEV,
        default_summary="Retrieve current documentation for named software libraries",
        skill_owner="ot-research",
        doc_slug="context7",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="db",
        display_name="DB",
        extra=InstallExtra.DEV,
        default_summary="Inspect schemas, sample tables, and run explicit database queries",
        skill_owner="ot-db",
        doc_slug="db",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="diagram",
        display_name="Diagram",
        extra=InstallExtra.DEV,
        default_summary="Select providers and render validated diagram source",
        skill_owner="ot-diagram",
        doc_slug="diagram",
        topics=_standard_topics(
            _topic(
                "policy",
                "Current diagram generation policy",
                kind=HelpTopicKind.ADAPTER,
                source="diagram.get_diagram_policy",
            ),
            _topic(
                "providers",
                "Available diagram providers and provider-specific guidance",
                kind=HelpTopicKind.ADAPTER,
                source="diagram.list_providers",
            ),
            _topic(
                "templates",
                "Configured and bundled diagram templates",
                kind=HelpTopicKind.ADAPTER,
                source="diagram.templates",
            ),
        ),
    ),
    PackGuidanceEntry(
        pack="localhist",
        display_name="Localhist",
        extra=InstallExtra.DEV,
        default_summary="Save, inspect, restore, and prune project-local snapshot history",
        skill_owner="ot-localhist",
        doc_slug="localhist",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="package",
        display_name="Package",
        extra=InstallExtra.DEV,
        default_summary="Inspect manifest and registry versions plus available AI models",
        skill_owner="ot-research",
        doc_slug="package",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="play_util",
        display_name="Playwright Util",
        extra=InstallExtra.DEV,
        default_summary="Annotate and highlight pages through a Playwright MCP proxy",
        skill_owner="ot-browser-guidance",
        doc_slug="play-util",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="ripgrep",
        display_name="Ripgrep",
        extra=InstallExtra.DEV,
        default_summary="Search code and text with regular expressions, globs, and context",
        skill_owner="ot-file",
        doc_slug="ripgrep",
        topics=_standard_topics(),
    ),
    PackGuidanceEntry(
        pack="whiteboard",
        display_name="WB (Whiteboard)",
        extra=InstallExtra.UTIL,
        default_summary="Create and operate live Excalidraw whiteboards with an additive DSL",
        skill_owner="ot-whiteboard",
        doc_slug="whiteboard",
        topics=_standard_topics(
            _topic(
                "dsl",
                "Complete whiteboard drawing, note, layout, and style DSL",
                kind=HelpTopicKind.RESOURCE,
                source="otdev.tools._excalidraw/dsl-reference.md",
            )
        ),
    ),
    PackGuidanceEntry(
        pack="webfetch",
        display_name="Webfetch",
        extra=InstallExtra.DEV,
        default_summary="Fetch URLs and extract bounded readable content",
        skill_owner="ot-research",
        doc_slug="webfetch",
        topics=_standard_topics(),
    ),
)


def skill_names() -> tuple[str, ...]:
    """Return distributed skill names in reviewed catalog order."""

    return tuple(entry.name for entry in SKILL_CATALOG)


def pack_by_name() -> dict[str, PackGuidanceEntry]:
    """Return the reviewed pack catalog keyed by runtime pack name."""

    return {entry.pack: entry for entry in PACK_CATALOG}


def skill_by_name() -> dict[str, SkillCatalogEntry]:
    """Return the reviewed skill catalog keyed by skill name."""

    return {entry.name: entry for entry in SKILL_CATALOG}


def derive_skill_profiles() -> dict[str, frozenset[str]]:
    """Derive public skill-selection recipes from roles and pack ownership."""

    foundation = {
        skill.name
        for skill in SKILL_CATALOG
        if skill.profile_role is ProfileRole.FOUNDATION
    }
    explicit_core = {
        skill.name
        for skill in SKILL_CATALOG
        if skill.profile_role is ProfileRole.CORE
    }
    core_owners = {
        pack.skill_owner
        for pack in PACK_CATALOG
        if pack.extra is InstallExtra.CORE and pack.skill_owner is not None
    }
    util_owners = {
        pack.skill_owner
        for pack in PACK_CATALOG
        if pack.extra is InstallExtra.UTIL and pack.skill_owner is not None
    }
    dev_owners = {
        pack.skill_owner
        for pack in PACK_CATALOG
        if pack.extra is InstallExtra.DEV and pack.skill_owner is not None
    }
    core = foundation | explicit_core | core_owners
    return {
        "Foundation": frozenset(foundation),
        "Core": frozenset(core),
        "Core + [util]": frozenset(core | util_owners),
        "Core + [dev]": frozenset(core | dev_owners),
        "[all]": frozenset(skill_names()),
    }


def compose_catalog(
    runtime: Mapping[str, RuntimePackFacts],
) -> tuple[ComposedPackGuidance, ...]:
    """Join reviewed pack guidance with injected current runtime facts.

    Callers obtain runtime facts from the loaded registry, active config, and proxy
    manager. Keeping those inputs explicit makes composition deterministic and lets
    the base catalog remain safe when optional extras are not installed.
    """

    return tuple(
        ComposedPackGuidance(guidance=entry, runtime=runtime.get(entry.pack))
        for entry in PACK_CATALOG
    )


def load_composed_catalog() -> tuple[ComposedPackGuidance, ...]:
    """Compose reviewed guidance with the currently loaded runtime.

    Imports are local so importing :mod:`ot.catalog` itself never loads optional
    packs, configuration, or proxy clients.
    """

    from ot.config.introspection import inspect_pack_config, redact_config
    from ot.config.loader import _get_raw_config, get_config, get_tool_config
    from ot.executor.tool_loader import load_tool_registry
    from ot.proxy import get_proxy_manager

    registry = load_tool_registry()
    config = get_config()
    proxy = get_proxy_manager()
    proxy_state = {
        name: {
            "enabled": server.enabled,
            "connected": proxy.get_connection(name) is not None,
            "error": proxy.get_error(name),
        }
        for name, server in config.servers.items()
    }

    runtime: dict[str, RuntimePackFacts] = {}
    for entry in PACK_CATALOG:
        pack_functions = registry.packs.get(entry.pack)
        if pack_functions is None:
            continue
        tool_names = tuple(
            sorted(
                name
                for name in registry.functions
                if name.startswith(f"{entry.pack}.")
            )
        )
        signatures: dict[str, str] = {}
        for name in tool_names:
            function = registry.functions[name]
            try:
                signatures[name] = str(inspect.signature(function))
            except (TypeError, ValueError):
                continue

        expanded_config = get_tool_config(entry.pack)
        raw_config = _get_raw_config(entry.pack)
        config_schema: dict[str, Any] = {}
        config_defaults: dict[str, Any] = {}
        config_errors: tuple[dict[str, str], ...] = ()
        active_config = redact_config(expanded_config, raw_value=raw_config)
        config_model = registry.config_models.get(entry.pack)
        if config_model is not None:
            config_inspection = inspect_pack_config(
                config_model,
                expanded=expanded_config,
                raw=raw_config,
            )
            config_schema = config_inspection.schema_
            config_defaults = config_inspection.defaults
            active_config = config_inspection.current
            config_errors = config_inspection.errors

        runtime[entry.pack] = RuntimePackFacts(
            aliases=tuple(registry.pack_aliases.get(entry.pack, ())),
            tools=tool_names,
            signatures=signatures,
            doc_slug=registry.doc_slugs.get(entry.pack, entry.doc_slug),
            requirements=registry.requirements.get(entry.pack, ()),
            config_hook=registry.config_hooks.get(entry.pack),
            config_schema=config_schema,
            config_defaults=config_defaults,
            active_config=active_config,
            config_errors=config_errors,
            proxy_state=proxy_state if entry.pack == "ot_servers" else {},
        )
    return compose_catalog(runtime)
