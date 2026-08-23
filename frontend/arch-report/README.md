# Architecture report frontend

Generate the checked-in development payload from the repository root:

```bash
uv run python -m otdev.tools._arch.v3 payload \
  tests/unit/tools/fixtures/arch/acme.yaml \
  frontend/arch-report/src/fixture-payload.json
```

Run the development server:

```bash
cd frontend/arch-report
npm install
npm run dev
```

Build the self-contained report template with `npm run build` from this
directory, or `just build-arch-report` from the repository root. The build
writes `src/otdev/tools/_arch/v3/_bundle/report-template.html`; commit that
file so report generation and wheel builds never require Node.
