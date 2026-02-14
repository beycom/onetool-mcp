# Module Consolidation

## REMOVED Requirements

### Requirement: onetool-mcp MUST NOT duplicate http_client from onetool-common

The http_client module duplicates functionality available in otcommon.http and MUST be removed.

#### Scenario: HTTP client usage after consolidation

**Given** onetool-common provides otcommon.http.get_client()
**When** onetool-mcp code needs HTTP client
**Then** it imports from otcommon.http
**And** src/ot/http_client.py does not exist
**And** 146 LOC are removed

### Requirement: onetool-mcp MUST NOT duplicate base logging from onetool-common

Base logging functionality (LogSpan, setup_logging) duplicates onetool-common and MUST be consolidated, keeping only MCP-specific adapters.

#### Scenario: Logging setup after consolidation

**Given** onetool-common provides base logging functionality
**When** onetool-mcp sets up logging
**Then** it imports LogSpan and setup_logging from otcommon.logging
**And** only MCP-specific code (InterceptHandler, JSONEncoder) remains in ot.logging.mcp_adapters
**And** ~921 LOC are removed

### Requirement: onetool-mcp MUST NOT duplicate base config from onetool-common

Base config loading (YAML loading, env expansion, deep merge) duplicates onetool-common functionality.

#### Scenario: Config loading after consolidation

**Given** onetool-common provides load_config, expand_vars, deep_merge
**When** onetool-mcp loads configuration
**Then** it imports base config functions from otcommon.config
**And** only MCP-specific models (ServerConfig, ProxyConfig, ExecutorConfig) remain
**And** ~716 LOC are removed

### Requirement: onetool-mcp MUST NOT duplicate base paths from onetool-common

Base path utilities (resolve_path, get_project_dir) duplicate onetool-common functionality.

#### Scenario: Path resolution after consolidation

**Given** onetool-common provides base path utilities
**When** onetool-mcp needs path operations
**Then** it imports resolve_path and get_project_dir from otcommon.paths
**And** only MCP-specific paths (get_tools_dir, get_registry_dir, get_executor_cache_dir) remain in ot.paths_mcp
**And** ~244 LOC are removed

## ADDED Requirements

### Requirement: onetool-mcp MUST depend on onetool-common

onetool-mcp MUST declare onetool-common as a dependency to use shared modules.

#### Scenario: Installing onetool-mcp

**Given** pyproject.toml lists onetool-common as dependency
**When** onetool-mcp is installed
**Then** onetool-common is automatically installed
**And** shared modules are available for import
**And** common dependencies (pydantic, pyyaml, loguru, httpx, typer) are transitively available
