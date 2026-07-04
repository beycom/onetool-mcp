#!/usr/bin/env bash
# Demo 3 (required, launch): "We just committed our secrets file" — and it's fine.
# Encrypt secrets.yaml in place, commit the age1enc: ciphertext, and show the
# keychain-backed decrypt succeeding on the next server boot.
# Usage: ./03-secrets-commit.sh [PORT]
#
# Prereq: run the guided `onetool init` secrets step (or ot_secrets.init()) once so
# an age identity exists in the OS keychain. Depends on p14-guided-encrypted-secrets.
set -euo pipefail
PORT="${1:-8765}"
run() { onetool direct run --port "$PORT" "$1" --format raw; }
say() { run "narrator.speak(text=$1)"; }

say "'Watch us commit our secrets file to git, on purpose.'"

say "'Store a secret. It is encrypted in place against the keychain identity.'"
run "ot_secrets.set(key='DEMO_API_KEY', value='sk-demo-not-a-real-key-000000000000')"

say "'Encrypt any remaining plaintext values in the file.'"
run "ot_secrets.encrypt()"

say "'Audit confirms every value is now age1enc ciphertext — safe to commit.'"
run "ot_secrets.audit()"

say "'Status shows the identity is keychain-backed. Decrypt happens transparently on load.'"
run "ot_secrets.status()"

say "'Encrypted secrets. Committed without fear.'"
