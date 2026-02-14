# Dependency Reduction

## REMOVED Requirements

### Requirement: onetool-mcp MUST NOT depend on document processing libraries

Document processing libraries (pymupdf, python-docx, python-pptx, openpyxl) are now in onetool-util and MUST be removed from onetool-mcp dependencies.

#### Scenario: Checking dependencies after utility tool extraction

**Given** onetool-util provides document processing tools
**When** developer checks onetool-mcp pyproject.toml
**Then** pymupdf, python-docx, python-pptx, openpyxl are not listed
**And** these libraries are not installed in onetool-mcp venv

### Requirement: onetool-mcp MUST NOT depend on developer-specific libraries

Developer-specific libraries (sqlalchemy, trafilatura, google-generativeai) are now in backends and MUST be removed.

#### Scenario: Checking dependencies after developer tool extraction

**Given** onetool-dev and onetool-util provide developer tools
**When** developer checks onetool-mcp pyproject.toml
**Then** sqlalchemy and trafilatura are not listed (now in onetool-dev)
**And** google-generativeai is not listed (now in onetool-util)
**And** these libraries are not installed in onetool-mcp venv

## MODIFIED Requirements

### Requirement: onetool-mcp MUST have minimal core dependencies

After extracting tools to backends, onetool-mcp MUST have ~10-15 dependencies (85-90% reduction from ~100).

#### Scenario: Verifying dependency reduction

**Given** tools have been extracted and modules consolidated
**When** developer runs `uv pip list` in onetool-mcp venv
**Then** total package count is ~10-15
**And** core dependencies remain: fastmcp, openai, tiktoken, jinja2, onetool-common
**And** onetool-common brings: pydantic, pyyaml, loguru, httpx, typer
**And** no heavy document/database libraries are present

#### Scenario: Fresh installation is fast

**Given** a developer installs onetool-mcp for the first time
**When** they run `uv sync`
**Then** installation completes in seconds (not minutes)
**And** venv size is small (~50MB vs ~500MB)
**And** only core dependencies are installed
