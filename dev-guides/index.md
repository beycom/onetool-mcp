# Developer guides

Start with [agent hints](agents/hints.md) for constraints and the [project map](agents/project-map.md) for code ownership. These guides describe V4 as implemented.

| Need | Read |
| --- | --- |
| Working conventions | [Practices](practices/index.md) |
| Runtime boundaries | [Architecture](project/architecture.md) |
| Candidate artifacts | [Release](project/release.md) |
| Commands and checks | [Testing](practices/testing.md) |
| Worktrees and private planning | [Workspace](practices/workspace.md) |
| User configuration and execution | [Config](../docs/config.md), [Python](../docs/python.md) |

Run `just install-locked`, then `just check`. Read `AGENTS.md` before changing source. Plans and evidence live in the optional private planning checkout; they are not package inputs.
