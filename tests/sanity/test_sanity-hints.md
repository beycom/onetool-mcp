# Sanity Test Hints

OneTool is setup correctly with all dependencies and secrets needed.

## Efficiency tips

1. **Check signatures first**: Before testing a pack, run `ot.tools(pattern="packname", info="full")` to see all parameter names and avoid guessing
2. **Batch similar tools**: Test tools in groups - e.g., all search tools together, all file tools together
3. **Skip task tracking**: Don't create granular tasks for each pack - it adds overhead. Just work through the list sequentially
4. **Use minimal test inputs**: Use small counts (2-3) and simple queries to speed up API calls
5. **Test one tool per pack first**: If the first tool works, others likely will too - focus deeper testing on tools with different signatures

## Parameter naming hints

🔹 **excel tools**: Use `filepath` not `path`, and `sheet_name` not `sheet`
   - Example: `excel.info(filepath="data.xlsx")` not `excel.info(path="data.xlsx")`
   - Example: `excel.read(filepath="data.xlsx", sheet_name="Sales")` not `excel.read(path="data.xlsx", sheet="Sales")`

🔹 **ground tools**: Use `max_sources` not `count` to limit results
   - Example: `ground.search(query="topic", max_sources=5)` not `ground.search(query="topic", count=5)`

## Expected behaviors (not bugs)

- `brave.summarize` returns "No summary available" without Brave Pro subscription
- `file.write` blocks paths outside allowed directories - this is security working correctly

## Test URLs

🔹 **web.fetch**: Use `https://en.wikipedia.org` or `https://en.wikipedia.org/wiki/OpenAI` - NOT example.com as it does not exist

## Quick smoke test order

Test these first for fast coverage (one tool from each category):
1. `brave.search(query="test", count=2)` - web search
2. `ripgrep.search(pattern="TODO", path="src/", limit=3)` - file search
3. `db.tables(db_url="sqlite:///demo/db/northwind.db")` - database
4. `file.tree(path="demo", max_depth=1)` - filesystem
5. `ot.health()` - introspection
6. `$pkg_pypi packages="requests"` - snippets

If all pass, the core infrastructure is working.
