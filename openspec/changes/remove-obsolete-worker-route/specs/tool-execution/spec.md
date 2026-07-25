## REMOVED Requirements

### Requirement: Persistent Worker Subprocess Execution

**Reason**: The supported v3 extension workflow is in-process and no current
Forge template implements the worker protocol.

**Migration**: Load configured extensions in-process and install their
dependencies in the OneTool environment.

### Requirement: PEP 723 Dependency Declaration

**Reason**: Inline script metadata no longer controls OneTool execution or
dependency installation.

**Migration**: Treat inline metadata as inert comments and manage dependencies
through the installed OneTool environment.

### Requirement: Internal Tool In-Process Execution

**Reason**: The worker-only capability is being deleted and the retained
in-process loading contract is owned by `serve-tools-packages`.

**Migration**: Use the unified local-pack loading requirements.

### Requirement: Extension Tool Location

**Reason**: Current configured extension discovery is governed by configuration
and Forge rather than the obsolete worker-only directory contract.

**Migration**: Configure extension paths through the current `tools_dir`
contract or create them through Forge.

### Requirement: Tool Type Detection

**Reason**: V3 has no worker tool type; configured and bundled local packs use
one in-process execution route.

**Migration**: Remove worker-specific type checks and treat PEP 723 blocks as
ordinary comments.
