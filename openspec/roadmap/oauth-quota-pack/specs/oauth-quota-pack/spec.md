## ADDED Requirements

### Requirement: Quota Pack Registration
The system SHALL provide an `otutil` MCP pack named `quota` for AI subscription quota reporting.

#### Scenario: Pack is discoverable
- **WHEN** OneTool discovers installed `otutil` tool packs
- **THEN** the `quota` pack SHALL be discoverable as a callable pack namespace

#### Scenario: Public tools are exposed
- **WHEN** the `quota` pack is loaded
- **THEN** it SHALL expose public tools for usage snapshots, tokenmax guidance, summary output, and effective configuration

#### Scenario: Pack is fully registered, not just importable
- **WHEN** `ot.packs()` lists the `quota` pack
- **THEN** it SHALL show a real description (not "(no description)"), sourced from the prompts configuration
- **AND** the pack's `doc_slug` SHALL resolve to the published documentation page (no 404)

### Requirement: Provider Selection
The `quota` pack SHALL support Claude Code OAuth subscription usage and OpenAI Codex OAuth subscription usage.

#### Scenario: All providers requested
- **WHEN** `quota.usage(provider="all")` is called
- **THEN** the result SHALL include one provider result for each enabled provider

#### Scenario: Single provider requested
- **WHEN** `quota.usage(provider="claude")` or `quota.usage(provider="codex")` is called
- **THEN** the result SHALL include only the requested provider result

#### Scenario: Disabled provider skipped
- **GIVEN** a provider is not listed in `tools.quota.enabled_providers`
- **WHEN** all providers are requested
- **THEN** the disabled provider SHALL NOT be queried
- **AND** the result SHALL identify which providers were enabled for that call

#### Scenario: Unknown provider rejected
- **WHEN** a quota tool is called with an unknown provider value
- **THEN** the tool SHALL return an error string explaining the supported provider values

### Requirement: Local OAuth State
The `quota` pack SHALL reuse local authenticated state where possible and SHALL NOT require provider API keys.

#### Scenario: Codex auth file is used
- **GIVEN** a Codex auth file exists at the configured path or default Codex auth path
- **WHEN** Codex usage is requested
- **THEN** the Codex provider SHALL use that local auth state to request subscription usage

#### Scenario: Claude OAuth state is used
- **GIVEN** Claude OAuth state exists at the configured path or known default Claude auth path
- **WHEN** Claude usage is requested
- **THEN** the Claude provider SHALL use that local auth state to request subscription usage

#### Scenario: Claude credentials found per platform
- **GIVEN** a macOS host where Claude Code stores credentials in the Keychain (service `Claude Code-credentials`) and no `~/.claude/.credentials.json` exists
- **WHEN** Claude usage is requested
- **THEN** the Claude provider SHALL read the OAuth state from the Keychain
- **AND** on Linux/WSL it SHALL read `~/.claude/.credentials.json` (or the configured `claude.credentials_path`)
- **AND** a file-only lookup that reports missing credentials on macOS SHALL be treated as a defect, not an acceptable degradation

#### Scenario: Missing credentials reported
- **GIVEN** no usable local auth state exists for a provider
- **WHEN** that provider's usage is requested
- **THEN** the provider result SHALL report an authentication-state error
- **AND** the result SHALL NOT include token values or other credential secrets

#### Scenario: Terminal output is not scraped
- **WHEN** provider usage is requested
- **THEN** the provider SHALL NOT shell out to provider CLIs to scrape terminal output

#### Scenario: OneTool secrets are not used for OAuth tokens
- **WHEN** provider usage is requested
- **THEN** the provider SHALL NOT read Claude or Codex OAuth tokens from OneTool `secrets.yaml`

### Requirement: Normalized Usage Snapshot
The `quota.usage()` tool SHALL return normalized usage snapshots with provider-neutral fields.

#### Scenario: Successful snapshot
- **WHEN** a provider usage request succeeds
- **THEN** the provider result SHALL include provider name, source, status, fetched timestamp, cache metadata, account or plan when available, and normalized usage windows

#### Scenario: Session and weekly windows
- **WHEN** provider data includes session and weekly quota windows
- **THEN** the provider result SHALL expose those windows as `session` and `weekly`

#### Scenario: Window reset metadata
- **WHEN** a usage window includes a reset time
- **THEN** the normalized window SHALL include `reset_at`, `seconds_until_reset`, and `time_remaining_percent`

#### Scenario: Window quota metadata
- **WHEN** a usage window includes usage percentage
- **THEN** the normalized window SHALL include `used_percent` and `remaining_percent`

#### Scenario: Partial provider data
- **WHEN** a provider response omits an account, plan, reset time, or usage percentage field
- **THEN** the provider result SHALL return the available fields
- **AND** the provider result SHALL identify missing or unparsed fields without failing unrelated providers

### Requirement: Cache-Aware Polling
The `quota` pack SHALL avoid excessive provider polling through cache TTL and minimum polling intervals.

#### Scenario: Fresh cache used
- **GIVEN** a cached provider snapshot is younger than `tools.quota.cache_ttl_seconds`
- **WHEN** usage is requested with `refresh=False`
- **THEN** the cached snapshot SHALL be returned
- **AND** the result SHALL include `cached=true` and cache age metadata

#### Scenario: Refresh honors minimum polling interval
- **GIVEN** a provider was polled more recently than its configured minimum polling interval
- **WHEN** usage is requested with `refresh=True`
- **THEN** the provider SHALL NOT be polled again
- **AND** the cached snapshot or a polling-throttled provider result SHALL include `next_refresh_at`

#### Scenario: Stale cache refreshes
- **GIVEN** a cached provider snapshot is older than `tools.quota.cache_ttl_seconds`
- **AND** the provider minimum polling interval has elapsed
- **WHEN** usage is requested
- **THEN** the provider SHALL be polled for a fresh snapshot

### Requirement: Tokenmax Guidance
The `quota.tokenmax()` tool SHALL return guidance comparing quota remaining with time remaining.

#### Scenario: Weekly burn ratio calculated
- **WHEN** a weekly window includes remaining percentage and time remaining percentage
- **THEN** tokenmax guidance SHALL include a burn ratio derived from those values

#### Scenario: Conserve guidance
- **GIVEN** quota remaining is low relative to time remaining
- **WHEN** tokenmax guidance is requested
- **THEN** the result SHALL classify the provider or window as needing conservation

#### Scenario: Spend available guidance
- **GIVEN** quota remaining is high relative to time remaining
- **WHEN** tokenmax guidance is requested
- **THEN** the result SHALL classify the provider or window as having spend available

#### Scenario: Critical quota guidance
- **GIVEN** quota remaining is at or below `tools.quota.tokenmax.critical_quota_left_percent`
- **WHEN** tokenmax guidance is requested
- **THEN** the result SHALL classify the provider or window as critical

#### Scenario: Insufficient data
- **WHEN** usage or reset metadata is insufficient to calculate tokenmax guidance
- **THEN** the result SHALL report insufficient data for that provider or window
- **AND** the tool SHALL NOT invent percentages or reset times

### Requirement: Summary Output
The `quota.summary()` tool SHALL return a compact human-readable subscription status.

#### Scenario: Summary includes quota and time
- **WHEN** summary output is requested for a provider with weekly data
- **THEN** the summary SHALL include quota remaining, reset time or days remaining, and time remaining percentage

#### Scenario: Summary includes recommendation
- **WHEN** tokenmax guidance is available
- **THEN** the summary SHALL include the recommendation classification

#### Scenario: Summary handles partial failures
- **WHEN** one provider succeeds and another provider fails
- **THEN** the summary SHALL include the successful provider status
- **AND** the summary SHALL include a concise error for the failed provider

### Requirement: Quota Configuration
The `quota` pack SHALL provide typed configuration for providers, polling, endpoints, native credential paths, and tokenmax thresholds.

#### Scenario: Defaults used when omitted
- **WHEN** `tools.quota` is omitted
- **THEN** the pack SHALL use built-in defaults for enabled providers, cache TTL, request timeout, endpoint URLs, polling intervals, and tokenmax thresholds

#### Scenario: Effective config returned
- **WHEN** `quota.config()` is called
- **THEN** the tool SHALL return effective non-secret configuration values

#### Scenario: Unknown config key rejected
- **WHEN** `tools.quota` contains an unknown configuration key
- **THEN** OneTool configuration validation SHALL reject the configuration instead of silently accepting it

#### Scenario: Invalid config value rejected
- **WHEN** a quota configuration value violates its typed constraints
- **THEN** OneTool configuration validation SHALL reject the value instead of falling back to defaults

### Requirement: Credential Safety
The `quota` pack SHALL avoid exposing or mutating local credentials by default.

#### Scenario: Token values are redacted
- **WHEN** any quota tool returns provider results, config, errors, or diagnostics
- **THEN** access tokens, refresh tokens, cookies, and authorization headers SHALL NOT be included in returned data

#### Scenario: Token refresh disabled by default
- **WHEN** provider usage is requested
- **THEN** providers SHALL NOT use refresh tokens or write refreshed credentials back to local auth files

#### Scenario: Browser session not used
- **WHEN** provider usage is requested
- **THEN** providers SHALL NOT read browser cookies or browser session state

### Requirement: Provider Error Handling
The `quota` pack SHALL report provider failures without hiding successful provider results.

#### Scenario: Provider rate limited
- **WHEN** a provider returns a rate-limit response
- **THEN** the provider result SHALL identify the rate-limit condition
- **AND** the result SHALL include retry or refresh timing when available

#### Scenario: Provider response changes
- **WHEN** a provider returns JSON that does not match the expected parser shape
- **THEN** the provider result SHALL identify a parse error
- **AND** the result SHALL include safe non-secret diagnostic metadata

#### Scenario: One provider fails among all providers
- **WHEN** `provider="all"` is requested and one provider fails
- **THEN** successful provider results SHALL still be returned
- **AND** failed provider results SHALL include provider-specific error status

### Requirement: Quota Tool Documentation
The `quota` pack SHALL include user-facing reference documentation.

#### Scenario: Reference doc follows pack format
- **WHEN** quota reference documentation is added
- **THEN** it SHALL follow the tool reference sections for highlights, functions, key parameters, requirements, configuration, examples, and source or attribution

#### Scenario: Open-source references attributed
- **WHEN** the quota documentation describes upstream projects used for behavior research
- **THEN** it SHALL identify them as references or inspiration unless implementation code is copied
