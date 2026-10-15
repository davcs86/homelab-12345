#!/usr/bin/env bash
# Join (up) or leave (down) the tailnet from a GitHub runner as an ephemeral tag:deploy node.
# up prints the edge's tailnet IPv4 to $GITHUB_OUTPUT as edge_ip. Requires SOPS_AGE_SSH_PRIVATE_KEY_FILE.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
login_server="https://hs.$(awk '/^domain:/{print $2}' "$repo_root/inventories/prod/group_vars/all/main.yml")"

case "${1:?up|down}" in
  up)
    authkey="$(sops decrypt --extract '["tailscale_deploy_authkey"]' "$repo_root/secrets/deploy-authkey.sops.yaml")"
    echo "::add-mask::$authkey"
    sudo mkdir -p /run/tailscale
    # shellcheck disable=SC2024  # the log belongs to the runner user on purpose
    sudo tailscaled --state=mem: --socket=/run/tailscale/tailscaled.sock >"$RUNNER_TEMP/tailscaled.log" 2>&1 &
    for _ in $(seq 1 20); do sudo tailscale status >/dev/null 2>&1 && break; sleep 1; done
    sudo tailscale up --login-server "$login_server" --auth-key "$authkey" \
      --hostname "gha-deploy-${GITHUB_RUN_ID}-${GITHUB_RUN_ATTEMPT}" --accept-dns=false --timeout 60s
    edge_ip="$(sudo tailscale ip -4 edge)"
    echo "edge_ip=$edge_ip" >>"$GITHUB_OUTPUT"
    echo "joined tailnet; edge at $edge_ip"
    ;;
  down)
    # Ephemeral node: logout deletes it from headscale immediately.
    sudo tailscale logout 2>/dev/null || true
    sudo pkill tailscaled 2>/dev/null || true
    ;;
esac
