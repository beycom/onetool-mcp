# Python Code Review

Comprehensive review for Python projects covering code quality, tests, documentation, and spec alignment.

**Assumptions**
- Python-based project
- Uses openspec (`/openspec/specs` for spec review)
- pytest with markers in `pyproject.toml`
- `conftest.py` for shared fixtures

> **Note:** See `AGENTS.md` for project-specific tooling and rules.

## Guardrails

- DO NOT make any changes without explicit user confirmation
- DO NOT create commits - this command is for review only
- Present findings clearly with actionable suggestions
- Focus on meaningful issues, not style nitpicks handled by formatters

## Workflow

Process each phase sequentially. After each phase:
1. Present findings for that phase
2. Ask which issues to fix
3. Apply confirmed fixes
4. Move to next phase

---

## Step 1: Identify Scope

Use `git status --short -uall` to show all changed files, then ASK the user which to review.

**Important:** The `-uall` flag is required to expand untracked directories into individual files. Without it, git collapses directories like `src/ot/utils/` into a single entry, causing undercounting.

Review options:

1. **Staged files** - Only files staged for commit (recommended for pre-commit)
2. **Changed files** - All staged + unstaged + untracked
3. **By component** - Filter by a specific module or directory
4. **All files** - Full codebase review

Wait for confirmation before proceeding.

---

## Step 2: Code Review

### 2.1 Run Automated Checks

Run the project's check command (see `AGENTS.md` for the specific command).

If no project command exists, run linters/formatters/type checkers as configured.

### 2.2 Manual Code Quality Review

Inspect files for issues that automated tooling misses:

#### Understandability

- Unclear or misleading names (variables, functions, classes)
- Missing or outdated comments for complex logic
- Functions doing too many things (violates single responsibility)
- Deep nesting that could be flattened
- Magic numbers or strings without explanation

#### Duplication

- Copy-pasted code blocks that should be extracted
- Similar functions that could be unified
- Repeated patterns that warrant abstraction

#### Dead Code

- Unused imports, variables, or functions
- Commented-out code blocks
- Unreachable code paths
- Obsolete files or deprecated implementations

#### Correctness

- Missing error handling or edge cases
- Race conditions or async issues
- Resource leaks (unclosed handles, missing cleanup)
- Security issues (hardcoded secrets, injection vulnerabilities)

#### Backward Compatibility Violations

Per project rules (see `AGENTS.md`), flag any:

- Compatibility shims or polyfills
- Re-exports for moved/renamed code
- Deprecation warnings or migration paths
- `# removed` comments for deleted code
- Unused `_vars` to maintain signatures

### 2.3 Present Code Findings

Show findings table:

```text
| # | Type | file:line | Category | Description | Suggested fix |
```

Types: `[A]` = Automated, `[M]` = Manual
Categories: `error` → `warning` → `quality` → `duplication`

### 2.4 Fix Code Issues

ASK user which to fix (e.g., "1, 3", "all", "none"). Apply confirmed fixes, then proceed.

---

## Step 3: Test Review

Review tests to ensure minimal, DRY testing aligned with project testing conventions.

### 3.1 Test Structure

Check that tests follow the testing principles:

- **Lean tests** - Minimum tests to verify behavior. No implementation detail testing.
- **DRY fixtures** - Shared setup in `conftest.py`. No duplicated setup code.
- **Test behavior** - Focus on inputs/outputs, not internal code paths.

### 3.2 Test Markers

Verify every test has required markers:

- **Speed tier** (pick one): `smoke`, `unit`, `integration`, `slow`
- **Component tag**: A marker matching the module being tested
- **Dependency tags** (as needed): `network`, `api`, `docker`

### 3.3 Test Antipatterns

Flag these issues:

- Duplicated setup code across test files
- Tests that check implementation details instead of behavior
- Over-testing (multiple tests for the same behavior)
- Missing speed/component markers
- Tests without clear assertions
- Fixtures defined in test files that should be in `conftest.py`

### 3.4 Present Test Findings

Show findings table:

```text
| # | Type | file:line | Category | Description | Suggested fix |
```

Categories: `missing-marker` → `duplication` → `antipattern`

### 3.5 Fix Test Issues

ASK user which to fix. Apply confirmed fixes, then proceed.

---

## Step 4: Documentation Review

Review README and project docs in `/docs`.

### 4.1 README.md

- Do setup instructions still work?
- Are documented features still accurate?
- Do examples match current API/usage?
- Are dependencies and requirements current?

### 4.2 Docs Directory

For each file in `/docs`:

- Does content match current implementation?
- Are code examples accurate and runnable?
- Are CLI commands and flags up to date?
- Is navigation/linking correct?

### 4.3 Internal Documentation

- Do doc comments match actual behaviour?
- Are API contracts (types, interfaces) consistent with implementation?

### 4.4 Present Docs Findings

Show findings table:

```text
| # | Type | file:line | Category | Description | Suggested fix |
```

Categories: `outdated` → `incorrect` → `missing`

### 4.5 Fix Docs Issues

ASK user which to fix. Apply confirmed fixes, then proceed.

---

## Step 5: Spec Review

Review code against specs in `/openspec/specs`.

**Important:** Code is the source of truth. When code and spec diverge, update the spec to match the code (after user confirmation).

### 5.1 Function Signatures

- Does spec reflect actual parameter names in code?
- Does spec reflect actual default values?
- Does spec correctly document required vs optional parameters?

### 5.2 Environment Variables

- Does spec document all env vars used in code?
- Are env var names in spec correct?

### 5.3 Behavior

- Does spec accurately describe actual code behavior?
- Are spec scenarios consistent with implementation?
- Does spec document actual return formats?

### 5.4 Docstrings

- Do spec descriptions match function docstrings?
- Are parameter descriptions in spec accurate?

### 5.5 Present Spec Findings

Show findings table:

```text
| # | Type | file:line | Category | Description | Suggested fix |
```

Categories: `breaking` → `incorrect` → `outdated` → `missing`

### 5.6 Fix Spec Issues

ASK user which to fix. Apply confirmed fixes by updating the spec to match the code.

---

## Step 6: Summary

After all phases complete, show a brief summary:

- Total issues found per phase
- Issues fixed vs skipped
- Any remaining items for follow-up
