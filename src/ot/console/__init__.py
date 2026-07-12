"""Console message models, metadata state, disk bodies, and outbox protocol.

Message metadata stays in bounded process memory while preview and inline
payload bodies are written through to session-scoped project state. The
outbox retains body-free entries and hydrates protocol events when polled.
"""

from __future__ import annotations
