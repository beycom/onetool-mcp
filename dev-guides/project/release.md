# Local release candidates

Building does not publish. No recipe tags, commits, pushes, merges main or uploads artifacts. Those actions require the owner's authorization.

Set the version with `just version 4.0.0rc1`. Update the README/changelog examples when changing the candidate name. Run the full source check, commit the reviewed tree and place a local `v4.0.0rc1` tag on that commit.

Build and collect artifacts:

```sh
just build
```

This produces the pure Python wheel, sdist and a copy of `scripts/install.sh` in `dist/`. The sdist includes docs, tests/fixtures, examples and release helpers; it excludes private planning, agent skills and retired packages.

Install the wheel into a clean Python 3.12 environment outside the checkout. Before adding test dependencies, use that environment's Python with `just release-inventory PATH_TO_PYTHON`. The recipe runs `scripts/release.py inventory dist`, writes the installed dependency/license inventory and hashes every artifact into SHA256SUMS. It records the source SHA/tag, dirty status, interpreter/platform and measured line counts.

Then add pytest/pytest-asyncio to that environment and run copied tests outside the source tree. Run installed MCP, EOF/SIGINT and uv-installer checks, including paths with spaces. Record commands, counts, sizes/startup times and skips in evidence. An uncommitted artifact is provisional; rebuild inventory/artifacts from the accepted local tag before delivery.

Supported 4.0 artifact formats are a pure Python wheel and the tested macOS arm64 uv installer route. The script downloads uv and a managed Python. It does not need Developer ID signing or notarization. Do not maintain a second PyInstaller build.

Release evidence must include production Python plus every shipped helper/config recipe, tests separately, <=800 user documentation lines and <=500 developer lines. Do not compress code to meet a budget. Inspect the wheel/sdist contents and prove a source build with planning absent.

Before publication, the owner still owes one real OAuth login and one week of daily use. Keep T10 open for main cutover, publishing and registry metadata. Earlier source/changelog remains readable at `archive/pre-v4-main`; never modify the preserved old checkout or worktrees.
