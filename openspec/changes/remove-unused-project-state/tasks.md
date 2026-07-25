## 1. Remove the generic state surface

- [x] 1.1 Delete the `otpack.state` module, public imports, and `__all__` entries without a compatibility path.
- [x] 1.2 Remove the dedicated generic-state tests and current architecture/tool-author documentation examples.
- [x] 1.3 Preserve `get_project_state_dir` and verify all active consumers remain unchanged.

## 2. Reconcile contracts and verification

- [x] 2.1 Add the validated `otpack-project-paths` specification to the main spec set and index.
- [x] 2.2 Prove the removed names survive only in historical OpenSpec artifacts and run the focused `otpack` and project-path tests.
- [x] 2.3 Run strict OpenSpec validation and the repository-wide `just check`.
