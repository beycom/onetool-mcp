"""Console message models, slim in-memory state, and the outbox protocol.

Only `models` (data shapes), `state` (bounded in-memory message store), and
`outbox` (the Console outbox protocol) are ported in this release. The full
display service (disk cache, file/diff previews, path resolution) ships with
the complete display pack in 3.1.
"""

from __future__ import annotations
