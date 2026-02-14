# Tool Extraction

## REMOVED Requirements

### Requirement: onetool-mcp MUST NOT include utility tools

Utility tools (file, excel, convert, brave_search, grounding_search) have been extracted to onetool-util backend and MUST be removed from onetool-mcp.

#### Scenario: Checking for utility tools in onetool-mcp

**Given** onetool-util backend exists with utility tools
**When** developer lists files in onetool-mcp/src/ot_tools/
**Then** file.py, excel.py, convert.py, brave_search.py, grounding_search.py do not exist
**And** tests for these tools are removed

### Requirement: onetool-mcp MUST NOT include developer tools

Developer tools (db, ripgrep, web_fetch, package, context7, diagram, devtools_util, playwright_util) have been extracted to onetool-dev backend and MUST be removed.

#### Scenario: Checking for developer tools in onetool-mcp

**Given** onetool-dev backend exists with developer tools
**When** developer lists files in onetool-mcp/src/ot_tools/
**Then** db.py, ripgrep.py, web_fetch.py, package.py, context7.py, diagram.py do not exist
**And** devtools_util.py, playwright_util.py, _inject_base.py do not exist
**And** tests for these tools are removed

## ADDED Requirements

### Requirement: onetool-mcp MUST retain core meta tools

Core tools (mem, timer, scaffold, transform, meta) MUST remain in onetool-mcp as they are fundamental to the MCP frontend functionality.

#### Scenario: Verifying core tools after extraction

**Given** utility and developer tools have been removed
**When** developer lists files in onetool-mcp/src/ot_tools/
**Then** exactly 5 tool files exist: mem.py, timer.py, scaffold.py, transform.py, meta.py
**And** tests for these core tools remain
**And** all 5 core tools are functional
