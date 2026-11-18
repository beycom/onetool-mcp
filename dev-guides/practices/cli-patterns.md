# CLI patterns

`src/onetool/cli.py` uses argparse. Keep help concise and commands explicit: `onetool --version`, `onetool --help`, `onetool check-config --config PATH`, and `onetool serve --config PATH`.

Help/version exit without loading configuration or accessing a server. Validation reads only the explicit file and environment references. Runtime imports remain after argument/config validation so check-config cannot launch a process, access keyring or open OAuth.

Serving uses MCP stdio. stdout belongs to protocol traffic; diagnostics go to stderr. Do not add progress bars, styled output, implicit file searches, environment-file loading or configuration creation.

Return 0 for orderly completion, 2 for arguments/config, 1 for fatal runtime failure. Preserve KeyboardInterrupt's orderly shutdown behavior. Use sanitized failure categories rather than a raw traceback. Add CLI tests for any changed exit or output contract.
