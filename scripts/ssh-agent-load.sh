#!/usr/bin/env bash
# Decrypt one SOPS-encrypted SSH key straight into the running ssh-agent.
# The plaintext never touches disk. Lifetime defaults to 8h.
# Usage: scripts/ssh-agent-load.sh operator [lifetime]
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
name="${1:?usage: $0 <name> [lifetime]}"
life="${2:-8h}"
[[ -n "${SSH_AUTH_SOCK:-}" ]] || { echo "no ssh-agent (SSH_AUTH_SOCK unset)" >&2; exit 1; }
cd "${repo_root}"
sops --decrypt --input-type binary --output-type binary "secrets/ssh/${name}_ed25519.sops" \
  | ssh-add -t "${life}" -
