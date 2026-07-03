## ADDED Requirements

### Requirement: Security model documentation matches the executor implementation

`dev/project/arch/security-model.md` SHALL describe the `exec()` trust boundary accurately: it MUST
NOT claim that Layer 3 (Namespace Restriction) exposes "only allowlisted builtins" or excludes
`eval`/`__import__`/filesystem access/network access, because none of that is true of the shipped
implementation — `src/ot/executor/runner.py` passes the full `__builtins__` mapping into the exec
namespace unfiltered, and the AST validator's `__builtins__` guard
(`src/ot/executor/validator.py`, `visit_Subscript`) only blocks the literal name `__builtins__`, not
an aliased reference (`x = __builtins__; x['eval'](...)`) or the class-hierarchy walk
(`().__class__.__base__.__subclasses__()`). The document MUST instead state, in the Layer 3 section,
that:
- `exec()` is not a sandbox: AST validation blocks casual mistakes and known-dangerous imports/calls,
  but does not contain a determined escape.
- The security boundary is process/user/environment isolation for a trusted local user running a
  trusted agent session — not `exec()` itself.
- Users must not feed untrusted content to an agent with OneTool access and expect the validator to
  hold as a security control.

This is a documentation-only requirement — no runtime behavior changes. It exists as a spec so the
doc-truth outcome is independently verifiable rather than asserted.

#### Scenario: Layer 3 no longer claims a narrowed builtin set
- **WHEN** `dev/project/arch/security-model.md` is searched for the phrase `only allowlisted builtins`
- **THEN** no match is found

#### Scenario: Layer 3 no longer claims eval/import/filesystem/network exclusion
- **WHEN** `dev/project/arch/security-model.md`'s Layer 3 section is read
- **THEN** it does not list `eval`, `__import__`, "direct filesystem access", or "network access" as
  things the namespace excludes

#### Scenario: Layer 3 states the exec-is-not-a-sandbox trust boundary
- **WHEN** `dev/project/arch/security-model.md`'s Layer 3 section is read
- **THEN** it states plainly that `exec()` is not a sandbox
- **AND** it states that the security boundary is process/user/environment isolation for a trusted
  local user, not `exec()` itself
- **AND** it states that users must not feed untrusted content to an agent with OneTool access
  expecting the validator to hold

#### Scenario: Builtins-narrowing is documented as a deferred, not a V3, action
- **WHEN** `dev/project/arch/security-model.md` (or an adjacent deferred-work note) is read
- **THEN** narrowing the exec namespace's builtin set (or an alternative sandboxing approach) is
  recorded as deferred to a future release, contingent on the threat model changing
- **AND** it is not described as work already done or scheduled for the current release
