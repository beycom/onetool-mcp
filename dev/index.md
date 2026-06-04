# Developer Documentation

Internal reference for agents and developers working on OneTool MCP.

---

## Quick Start

```bash
just install    # Install dependencies
just check      # Lint + typecheck + test
just dev        # Run MCP server in dev mode
```

For the full command reference, use [practices/justfile.md](practices/justfile.md).

## Which File To Use

Start with the smallest file that answers the question:

| Need | Use | Why |
|------|-----|-----|
| Immediate agent context | [agents/hints.md](agents/hints.md) | One-page commands, rules, structure, and common paths |
| Full source/test layout | [agents/project-map.md](agents/project-map.md) | Directory map and ownership boundaries |
| Architecture or execution flow | [project/arch/index.md](project/arch/index.md) | Entry point to request pipeline, routing, registry, proxy, security, and config architecture |
| Creating or changing tools | [project/guides/index.md](project/guides/index.md) | Routes to creating tools, tool config, reference docs, attribution, and review guidance |
| Deciding file locations | [project/guides/onetool-file-layout.md](project/guides/onetool-file-layout.md) | Canonical ownership rules for config, runtime, data, state, artifacts, and templates |
| Generic development practice | [practices/index.md](practices/index.md) | Routes to testing, Python/frontend style, git, logging, CLI, docs, release, and just commands |
| Frontend/UI practice | [practices/typescript-react-ui.md](practices/typescript-react-ui.md) | TypeScript, React, Tailwind, testing, renderer safety, and browser asset pipeline |
| Brand, terminology, claims, links | [project/brand/index.md](project/brand/index.md) | OneTool wording, claims, taglines, and external references |
| Tool reference content | [../docs/reference/tools/index.md](../docs/reference/tools/index.md) | User-facing pack/tool descriptions and per-tool docs |

When updating docs, update the authoritative guide and link to it from indexes. Do not copy detailed guidance into multiple files.

---

## Documentation Principles

**Follow these principles when updating or adding to dev docs:**

### 1. DRY (Don't Repeat Yourself)

**Each piece of information should exist in exactly ONE place.**

**Good:**
- Index has minimal quick start → links to detailed guide
- Detailed guide has complete reference
- Related docs cross-reference → don't duplicate content

**Bad:**
- Same commands in multiple files
- Copy-paste between docs
- Duplicated architecture explanations

**Before adding content, check:**
```bash
# Does this info already exist?
rg "your new content" dev/ -l
```

**If content exists:** Link to it, don't duplicate it.

### 2. Single Source of Truth

Each topic has ONE authoritative doc:
- Just commands → `practices/justfile.md`
- Tool creation → `project/guides/tool-development.md`
- Testing patterns → `practices/testing.md`
- Git workflow → `practices/git.md`

**When updating:** Update the authoritative doc, not copies.

### 3. Minimal Indexes

Index files should:
- Provide quick orientation
- Link to detailed docs
- NOT duplicate detailed content

**Example:**
```markdown
## Quick Start
\`\`\`bash
just install    # Install dependencies
just check      # Run all checks
\`\`\`

For all commands, see [justfile.md](practices/justfile.md).
```

### 4. Clear Cross-References

**Use links, not duplication:**
```markdown
<!-- GOOD -->
For testing guide, see [testing.md](practices/testing.md).

<!-- BAD -->
Testing uses pytest with markers...
[copies entire testing guide]
```

**Link budget:** Maximum 2 links deep
- Index → Guide → Related guide ✅
- Index → Guide → Related → Another → ... ❌

### 5. Where vs. How

**Indexes answer "where":**
- Where is the testing guide?
- Where are the tool pack descriptions?

**Guides answer "how":**
- How do I create a tool?
- How do I write tests?

### 6. Validation Before Committing

**Check for duplications:**
```bash
# These should each return ONE file only:
rg "just install" dev/ -l
rg "pytest.*marker" dev/ -l
rg "@tool decorator" dev/ -l
```

**Check for broken links:**
```bash
# All internal links should resolve
rg '\[.*\]\([^http].*\.md.*\)' dev/ -A 1
```

**Check organization:**
- Is it OneTool-specific? → `project/`
- Is it generic dev practice? → `practices/`
- Is it a quick reference? → `agents/`

---

## Documentation Structure

### Where to Put New Content

Use this decision tree:

**Is it OneTool-specific?** → `project/`
- Architecture, system design → `project/arch/`
- How to create/configure tools → `project/guides/`
- Brand, messaging, tool descriptions → `project/brand/`

**Is it a generic dev practice?** → `practices/`
- Git, commits, releases → `practices/`
- Python style, frontend style, testing, logging → `practices/`
- CLI patterns, workflows → `practices/`

**Is it a quick reference for agents?** → `agents/`
- Quick hints file → `agents/hints.md`
- Project structure map → `agents/project-map.md`

**Not sure?** Ask:
1. Could this apply to any Python project? → `practices/`
2. Is it about OneTool's unique architecture? → `project/arch/`
3. Is it about brand/messaging? → `project/brand/`

---

## Section Guide

### agents/ - Navigation Layer

**Purpose:** Quick reference for AI agents to navigate the docs

| File | What's Inside | When to Read |
|------|--------------|--------------|
| [hints.md](agents/hints.md) | Single-page quick reference | Always load first |
| [project-map.md](agents/project-map.md) | Detailed project structure | When you need full structure |
| [index.md](agents/index.md) | How to use hints + mem search | Getting oriented |

**What belongs here:**
- Quick reference tables and checklists
- Pointers to detailed docs in project/ and practices/
- Common commands and file locations
- Minimal content - this is navigation, not content

**What doesn't belong:**
- Detailed guides (use project/guides/ or practices/)
- Architecture explanations (use project/arch/)
- Full workflow documentation (use practices/)

---

### project/ - OneTool-Specific Domain Knowledge

**Purpose:** Everything unique to OneTool that wouldn't apply to other projects

#### project/arch/ - System Architecture

| File | What's Inside | When to Read |
|------|--------------|--------------|
| [index.md](project/arch/index.md) | Architecture overview with diagram | Understanding OneTool's design |
| [core-concepts.md](project/arch/core-concepts.md) | Packs, aliases, snippets, namespaces | Learning OneTool concepts |
| [request-pipeline.md](project/arch/request-pipeline.md) | End-to-end request flow | Understanding execution |
| [execution-routing.md](project/arch/execution-routing.md) | How tools are dispatched | Deep dive on routing |
| [registry-system.md](project/arch/registry-system.md) | AST-based tool discovery | Understanding tool loading |
| [proxy-flow.md](project/arch/proxy-flow.md) | External MCP server communication | Working with proxies |
| [security-model.md](project/arch/security-model.md) | Four-layer defense, validation | Security deep dive |
| [configuration-architecture.md](project/arch/configuration-architecture.md) | Config system architecture | Understanding config |

**What belongs here:**
- OneTool's unique architecture and design decisions
- System diagrams (Mermaid, sequence diagrams)
- Component interactions specific to OneTool
- Core concepts that define how OneTool works

**Examples:**
- ✅ "How OneTool's pack proxy system works"
- ✅ "Request pipeline from client to tool execution"
- ✅ "Security validation layers"
- ❌ "How to write Python code" (use practices/)
- ❌ "Git workflow" (use practices/)

#### project/guides/ - OneTool-Specific Guides

| File | What's Inside | When to Read |
|------|--------------|--------------|
| [index.md](project/guides/index.md) | Guide overview | Finding the right guide |
| [tool-development.md](project/guides/tool-development.md) | Building OneTool tool packs | Creating a new tool |
| [onetool-configuration.md](project/guides/onetool-configuration.md) | OneTool configuration system | Configuring OneTool |
| [tool-configuration.md](project/guides/tool-configuration.md) | Tool-specific config | Adding tool config |
| [tool-reference-docs.md](project/guides/tool-reference-docs.md) | Tool reference documentation | Writing `docs/reference/tools/` pages |
| [upstream-tool-review.md](project/guides/upstream-tool-review.md) | Upstream tool API review tracker | Checking source projects for changes |
| [attribution.md](project/guides/attribution.md) | License handling for derived tools | Attributing third-party code |

**What belongs here:**
- How to build OneTool-specific features
- Working with OneTool's unique systems
- OneTool configuration and setup

**Examples:**
- ✅ "How to create a tool pack with the @tool decorator"
- ✅ "Adding tool-specific configuration to onetool.yaml"
- ✅ "Using OneTool's path resolution (resolve_ot_path)"
- ❌ "Python docstring format" (use practices/python-style.md)
- ❌ "How to write pytest tests" (use practices/testing.md)

#### project/brand/ - Brand Assets

| File | What's Inside | When to Read |
|------|--------------|--------------|
| [index.md](project/brand/index.md) | Brand overview | Brand work |
| [terminology.md](project/brand/terminology.md) | OneTool terminology guide | Writing docs/marketing |
| [claims.md](project/brand/claims.md) | Benchmark-backed claims | Marketing materials |
| [external-references.md](project/brand/external-references.md) | External references | Finding resources |

**What belongs here:**
- Brand identity, messaging, taglines
- OneTool-specific terminology
- Claims with benchmark evidence

**Examples:**
- ✅ "Terminology: 'pack' vs 'tool' vs 'function'"
- ✅ "Brand claims: '96% token reduction'"
- ❌ "How to use the tool packs" (use project/guides/)
- ❌ "Architecture of tool packs" (use project/arch/)
- ❌ "Tool reference descriptions" (use docs/reference/tools/)

---

### practices/ - Generic Development Practices

**Purpose:** Development workflows and standards that could apply to any Python project

| File | What's Inside | When to Read |
|------|--------------|--------------|
| [index.md](practices/index.md) | Practices overview | Getting oriented |
| [git.md](practices/git.md) | Git workflow, merge strategy | Working with git |
| [commit-scopes.md](practices/commit-scopes.md) | Conventional commit scopes | Making commits |
| [python-style.md](practices/python-style.md) | Python coding standards | Writing Python code |
| [testing.md](practices/testing.md) | Testing strategy, markers, fixtures | Writing tests |
| [logging.md](practices/logging.md) | LogSpan patterns, best practices | Adding logging |
| [cli-patterns.md](practices/cli-patterns.md) | CLI development patterns | Building CLIs |
| [justfile.md](practices/justfile.md) | Just command reference | Using just |
| [release.md](practices/release.md) | Release and publishing workflow | Releasing versions |
| [docs-writing.md](practices/docs-writing.md) | Documentation writing practice | Writing docs |
| [docs-visual-design.md](practices/docs-visual-design.md) | Documentation visual design tokens | Styling docs |

**What belongs here:**
- Generic development workflows (git, testing, Python style)
- Standards that apply beyond OneTool
- Common patterns for Python projects

**Examples:**
- ✅ "Git branch naming conventions"
- ✅ "Python docstring format (Google style)"
- ✅ "Pytest markers and fixture patterns"
- ✅ "Conventional commit message format"
- ❌ "OneTool architecture" (use project/arch/)
- ❌ "Creating tool packs" (use project/guides/)
- ❌ "Tool pack descriptions" (use project/brand/)

**Note:** Some practices use OneTool-specific tools (like LogSpan), but the *patterns* are generic enough to apply elsewhere.

---

## Related

- `pyproject.toml` - Dependencies, ruff/mypy/pytest config
- `justfile` - All dev commands
- `openspec/AGENTS.md` - OpenSpec workflow (linked, not duplicated)

---

## For AI Agents

**Start here:** [agents/hints.md](agents/hints.md)

**Search for details:**
```python
# OneTool-specific
mem.search(query="OneTool architecture")
mem.search(query="how to create tool pack")

# Development practices
mem.search(query="testing markers")
mem.search(query="git workflow")
```

**Browse directly:**
- OneTool-specific: `project/arch/`, `project/guides/`, `project/brand/`
- Dev practices: `practices/`

---
