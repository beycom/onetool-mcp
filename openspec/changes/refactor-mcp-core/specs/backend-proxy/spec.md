# Backend Proxy

## ADDED Requirements

### Requirement: onetool-mcp MUST connect to backend MCP servers

A proxy manager MUST connect to configured backend servers (onetool-util, onetool-dev, etc.) using MCP protocol over stdio.

#### Scenario: Starting onetool-mcp with backends configured

**Given** backend_servers section exists in config with onetool-util and onetool-dev
**When** onetool-mcp starts
**Then** ProxyManager initializes and connects to enabled backends
**And** lazy backends start only on first use
**And** non-lazy backends start immediately

#### Scenario: Backend fails to start

**Given** a backend server command is invalid or missing
**When** ProxyManager attempts to start the backend
**Then** a clear error message is logged
**And** other backends continue to function
**And** the failed backend is marked as unavailable

### Requirement: onetool-mcp MUST route tool calls to correct backends

When a tool is called, the proxy manager MUST route it to the backend that provides that tool.

#### Scenario: Calling file.read() routes to onetool-util

**Given** onetool-util backend provides file pack
**When** user calls `__ot file.read(path="test.txt")`
**Then** ProxyManager routes call to onetool-util backend
**And** result is returned to user
**And** routing is transparent to user

#### Scenario: Calling a tool when its backend is not running

**Given** a backend is configured with lazy=true and not yet started
**When** user calls a tool from that backend
**Then** ProxyManager starts the backend automatically
**And** waits for it to be ready
**And** routes the tool call
**And** subsequent calls use the running backend

### Requirement: onetool-mcp MUST aggregate tools from all backends

Meta tools (ot.tools, ot.help) MUST show tools from all connected backends, not just core tools.

#### Scenario: Listing all available tools

**Given** onetool-util and onetool-dev backends are connected
**When** user runs `__ot ot.tools()`
**Then** output includes core tools (5 tools) plus backend tools (100+ tools)
**And** each tool shows which backend it comes from
**And** tools can be filtered by pattern

#### Scenario: Searching for tools with ot.help

**Given** multiple backends are connected
**When** user runs `__ot ot.help(query="file")`
**Then** search results include file pack from onetool-util
**And** result shows it comes from onetool-util backend
**And** tool signatures and descriptions are shown

### Requirement: Backend failures MUST be isolated

If a backend crashes or fails, it MUST NOT bring down onetool-mcp or other backends.

#### Scenario: Backend crashes during tool call

**Given** a backend server is running
**When** the backend process crashes
**Then** ProxyManager detects the failure
**And** returns clear error to user
**And** core onetool-mcp continues running
**And** other backends are unaffected
**And** failed backend can be restarted

### Requirement: Backend configuration MUST support external MCP servers

The backend_servers config MUST support both OneTool backends and external MCP servers like github and devtools.

#### Scenario: Configuring external MCP server

**Given** user wants to use github MCP server
**When** they add github entry to backend_servers with its command
**Then** ProxyManager connects to github server
**And** github tools appear in ot.tools() output
**And** github tools can be called like any other tool
