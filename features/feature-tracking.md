# Feature tracking

`features.yaml` is the source of truth for every current, surviving OneTool feature. It replaces the old feature workbook and its approach/changelog docs — git history of the YAML file is the update record.

## Schema

One entry per feature, newest first:

| field | meaning |
|---|---|
| `feature` | short name |
| `pack` | canonical pack name (from the module's `pack =` declaration, not aliases) |
| `date` | when it landed |
| `release` | release version it ships in |
| `description` | what it does, one to three sentences |
| `examples` | representative calls |
| `value` | subjective 1–10 usefulness score |
| `loc` | approximate cloc over the feature's source area; rows sharing an area share the number — never sum the column |

The top-level `coverage` key is the git hash the file is current through.

## Updating

1. `git log --reverse --oneline <coverage>..HEAD`
2. For each feature-bearing commit, add an entry at the top of `features`. Skip docs, chores, and internal refactors unless they are visible as stability, security, performance, or usability improvements.
3. If a commit materially changed an existing feature area, refresh that area's `loc` with cloc over its source paths (all entries sharing the area get the same number).
4. Remove entries whose feature no longer exists in current source — removed features must not be listed.
5. Set `coverage` to the new HEAD hash.

Per-release totals when needed:

```bash
uv run python -c "
import yaml, collections
d = yaml.safe_load(open('features/features.yaml'))
t = collections.Counter(); v = collections.Counter()
for f in d['features']: t[f['release']] += 1; v[f['release']] += f['value']
[print(f'{r}: {t[r]} features / {v[r]} value') for r in sorted(t, reverse=True)]
print(f'total: {sum(t.values())} features / {sum(v.values())} value')"
```
