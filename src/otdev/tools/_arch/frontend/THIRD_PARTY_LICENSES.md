# Architecture Explorer Third-Party Licences

The production architecture explorer bundles the following direct dependencies.
Transitive package licence declarations are verified from the locked install by
`npm run verify:dependencies`.

| Dependency | Version | Licence |
| --- | --- | --- |
| LikeC4 packages (`likec4`, `@likec4/*`) | 1.58.0 (`@likec4/icons` 1.46.4) | MIT |
| React and React DOM | 19.2.7 | MIT |
| Mantine Core and Hooks | 9.2.2 | MIT |
| AG Grid Community and React adapter | 36.0.1 | MIT |
| IBM Plex Sans Variable | 5.2.8 | SIL Open Font Licence 1.1 |
| IBM Plex Mono | 5.2.7 | SIL Open Font Licence 1.1 |

No AG Grid Enterprise package, module, licence key, or Enterprise-only feature is
included. Full dependency metadata is pinned in `package-lock.json`.
