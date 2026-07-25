FROM python:3.12-slim AS builder

WORKDIR /src
RUN pip install --no-cache-dir build
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY packages/onetool-pack/pyproject.toml ./packages/onetool-pack/pyproject.toml
COPY packages/onetool-pack/src/ ./packages/onetool-pack/src/
RUN python -m build --wheel --outdir /wheels

FROM python:3.12-slim

COPY --from=builder /wheels/*.whl /tmp/wheels/
RUN wheel="$(find /tmp/wheels -name 'onetool_mcp-*.whl' -print -quit)" \
    && test -n "$wheel" \
    && pip install --no-cache-dir "${wheel}[all]" \
    && rm -rf /tmp/wheels \
    && onetool init --config /onetool/onetool.yaml
ENTRYPOINT ["onetool", "--config", "/onetool/onetool.yaml"]
