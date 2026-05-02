# Test a Pack

Test an OneTool pack — find defects and suggest improvements.

Start with `ot.help()` then `ot.tools(pattern="{pack}", info="full")`.

<!-- Hint: info="core" is invalid — valid values are "min", "default", "full" -->

Run each tool in the pack with realistic inputs. Note errors, edge cases, and UX issues.

Write issue files to `wip/issues/1-new/exp-{pack}-{issue}.md` and test output to `wip/test-output/{pack}-pack-test.md`.

Accepts comma-separated pack names as arguments (e.g., `brave,mem,db`).
