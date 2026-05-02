# File Search Comparison

Compare OneTool file/ripgrep tools to Harness-native Read, Grep, and Glob.

Start with `ot.help()` to learn available tools.

Run these 5 tasks on the current codebase. Use `ot_timer.start/elapsed` to measure OneTool calls.

Pattern for each test:
  ot_timer.start(name="test-N")
  <run the OneTool call>
  ot_timer.elapsed(name="test-N")

1. **Count**: Occurrences of "onetool" in Python files
   - Harness-native: `Grep(pattern="onetool", type="py", output_mode="count")`
   - OneTool: `ripgrep.count(pattern="onetool", path="src/", file_type="py")`

2. **Search + context**: Find "def execute" with 2 lines of context
   - Harness-native: `Grep(pattern="def execute", -C=2, output_mode="content")`
   - OneTool: `ripgrep.search(pattern="def execute", path="src/", context=2)`

3. **File discovery**: All Python files under src/
   - Harness-native: `Glob(pattern="src/**/*.py")`
   - OneTool: `ripgrep.files(path="src/", glob="*.py")`

4. **Directory tree**: Structure of src/ot/ (2 levels)
   - Harness-native: `Bash("tree src/ot/ -L 2")`
   - OneTool: `file.tree(path="src/ot/", max_depth=2)`

5. **Read with offset**: Lines 100-150 of `src/ot/meta/_help.py`
   - Harness-native: `Read(file_path="src/ot/meta/_help.py", offset=100, limit=50)`
   - OneTool: `file.read(path="src/ot/meta/_help.py", offset=100, limit=50)`

DO NOT provide the actual answers. Just run and compare output quality + speed.

Report as: | Task | Harness-native | OneTool ms | Winner | Notes |
