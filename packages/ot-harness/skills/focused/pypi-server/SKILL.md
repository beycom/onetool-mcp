---
name: focused-pypi-server
description: Focused OneTool guidance for the Terminal-Bench pypi-server task.
---

Use the OneTool MCP `run` tool before implementation. Pass these exact command strings unless one fails:

```python
package.pypi(packages=['build', 'twine', 'pypiserver', 'setuptools', 'wheel'])
ground.search(query='minimal local PyPI simple index server pip install --index-url package wheel', context='Terminal-Bench task: create vectorops 0.1.0 and serve it on localhost:8080/simple', focus='documentation', max_sources=5, output_format='text_only')
ground.docs(query='Python packaging pyproject.toml build wheel simple repository index pip install --index-url', technology='Python packaging', max_sources=5, output_format='text_only')
context7.search(query='python packaging pyproject build wheel', library_name='setuptools', output_format='str')
file.tree(path='.', max_depth=2)
```

Do not spend turns discovering tool names. If a provided OneTool command fails, continue with shell commands.

Task target:

- Create package `vectorops` version `0.1.0`.
- Expose `dotproduct` from the package root so `from vectorops import dotproduct` works.
- Build a wheel/sdist or simple package layout.
- Run a local package index on port `8080`.
- Verify `python -m pip install --index-url http://localhost:8080/simple vectorops==0.1.0`.
- Leave the package index server running after your final response so Harbor's verifier can install from it.

Server lifetime is part of the task. Do not start the package server in a foreground command, a persistent terminal session, or a TTY session. Do not stop, interrupt, or clean up the server after verification. Do not finish by telling the user how to start the server; the server must already be running when you finish.

Use a static PEP 503-style simple index and a detached background server. After building the package, create the index and start the server with this shape:

```bash
cd /app
mkdir -p /app/pypi/simple/vectorops /app/pypi/packages
cp /app/dist/vectorops-0.1.0*.whl /app/pypi/packages/
cat > /app/pypi/simple/index.html <<'HTML'
<!doctype html><html><body><a href="vectorops/">vectorops</a></body></html>
HTML
cat > /app/pypi/simple/vectorops/index.html <<'HTML'
<!doctype html><html><body>
<a href="../../packages/vectorops-0.1.0-py3-none-any.whl">vectorops-0.1.0-py3-none-any.whl</a>
</body></html>
HTML
nohup python -m http.server 8080 --directory /app/pypi > /tmp/pypi-server.log 2>&1 &
echo $! > /tmp/pypi-server.pid
```

After starting it, verify that it is still listening and that the package can be installed while the process remains alive:

```bash
sleep 1
curl -fsS http://localhost:8080/simple/vectorops/ >/dev/null
python -m pip install --force-reinstall --index-url http://localhost:8080/simple vectorops==0.1.0
python -c "from vectorops import dotproduct; assert dotproduct([1, 1], [0, 1]) == 1"
ps -p "$(cat /tmp/pypi-server.pid)"
curl -fsS http://localhost:8080/simple/vectorops/ >/dev/null
```
