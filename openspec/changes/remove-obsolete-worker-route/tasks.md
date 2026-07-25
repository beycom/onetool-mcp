## 1. Runtime simplification

- [x] 1.1 Remove PEP 723 parsing, worker pool/proxy modules, protocol routing,
  and worker state from the tool loader
- [x] 1.2 Remove worker-specific branches from pack namespaces, metadata,
  diagnostics, CLI output, and docs generation
- [x] 1.3 Preserve reload, registry, config-health, and failed-extension behavior
  through the unified in-process route

## 2. Verification

- [x] 2.1 Delete worker-only tests and add focused configured/Forge extension
  tests, including inert PEP 723 comments and missing dependencies
- [x] 2.2 Run focused loader, registry, Forge, config-health, CLI, and docsgen
  tests

## 3. Contracts and documentation

- [x] 3.1 Delete the worker-only main spec and update installation requirements
  plus the canonical spec index
- [x] 3.2 Update current extension, security, installation, and architecture
  guidance to the single in-process model
- [x] 3.3 Validate OpenSpec strictly, build docs strictly, and confirm completion
  searches contain no current worker execution contract

## 4. Repository validation

- [x] 4.1 Run `just check` and resolve every substantive batch review finding
