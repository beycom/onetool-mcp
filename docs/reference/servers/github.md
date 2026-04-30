# GitHub MCP

GitHub's official MCP server for repository management, issues, pull requests, Actions, and code security. Connects over HTTP using a Personal Access Token.

**Source:** [github/github-mcp-server](https://github.com/github/github-mcp-server)

## Enabling

The server is included in `servers.yaml` with `enabled: false`. To activate it permanently:

```yaml
github:
  enabled: true
```

Or enable for the current session only:

```python
ot_servers.enable(name="github")
```

## Server Config

```yaml
github:
  type: http
  url: https://api.githubcopilot.com/mcp/
  headers:
    Authorization: "Bearer ${GITHUB_TOKEN}"
    Accept: "application/json, text/event-stream"
  timeout: 120
  enabled: true
```

### Setup

1. Create a Personal Access Token at https://github.com/settings/tokens
2. Add it to your `secrets.yaml`:
   ```yaml
   GITHUB_TOKEN: ghp_your_token_here
   ```
3. Set `enabled: true` in `servers.yaml`

## Tools

| Toolset | Description |
|---------|-------------|
| `repos` | Browse code, search files, analyze commits, manage branches |
| `issues` | Create, update, list, search, and manage issues |
| `pull_requests` | Create PRs, review changes, merge, manage reviews |
| `actions` | Monitor workflows, analyze build failures, trigger runs |
| `code_security` | Review security findings, Dependabot alerts |

## Usage Patterns

- **Search before creating**: Check for existing issues/PRs before creating new ones
- **Batch operations**: Use list tools to get multiple items at once rather than individual gets
- **Code changes**: Create branch → push files → create PR
- **Issue workflow**: `search_issues` → `issue_read` → `add_issue_comment` or `issue_write`

## Examples

### 1. Check who you're authenticated as

Verify your token is working and see your account details.

```python
github.get_me()
# Returns: login, name, public_repos, followers, ...
```

### 2. List open PRs waiting for review

See what's pending in a repository.

```python
github.list_pull_requests(owner="myorg", repo="myrepo", state="open")
```

### 3. Search for bug issues across a repo

Find open bugs without browsing the UI.

```python
github.search_issues(q="is:open is:issue label:bug repo:myorg/myrepo")
```

### 4. Get the contents of a file

Read any file directly from a branch — useful for comparing config across environments.

```python
github.get_file_contents(owner="myorg", repo="myrepo", path="pyproject.toml", branch="main")
```

### 5. Find code using a specific pattern across GitHub

Search for all public usage of an API or function name.

```python
github.search_code(q="onetool_mcp language:python")
```

### 6. Get the latest release of a repository

Check the current published version of any project.

```python
github.get_latest_release(owner="microsoft", repo="playwright-mcp")
# Returns: tag_name, published_at, assets, body (release notes)
```

### 7. Create a new issue

File a bug or feature request with a structured body.

```python
github.issue_write(
    owner="myorg",
    repo="myrepo",
    title="Fix: connection timeout on slow networks",
    body="## Description\nConnection drops after 30s on high-latency links.\n\n## Steps to reproduce\n1. ...",
)
```

### 8. Push a file change in one call

Create or update a file without cloning the repo locally.

```python
github.push_files(
    owner="myorg",
    repo="myrepo",
    branch="main",
    message="docs: update changelog",
    files=[{"path": "CHANGELOG.md", "content": "## v1.2.0\n- Added X\n- Fixed Y\n"}],
)
```

## Common Mistakes to Avoid

- Don't create duplicate issues — search first
- Don't forget to specify the repository in `owner/repo` format
- Don't make multiple API calls when a single list or search call works
- Check PR status before attempting to merge
