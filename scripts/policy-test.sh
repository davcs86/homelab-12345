#!/usr/bin/env bash
# Validates policy/policy.hujson (syntax, grants and its "tests" block) against a throwaway headscale.
# Usage: scripts/policy-test.sh [policy-file]   (requires docker)
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
policy="${1:-$repo_root/policy/policy.hujson}"
image="$(awk -F'"' '/^headscale_image:/{print $2}' "$repo_root/inventories/prod/group_vars/all/versions.yml")"
users="david david_admin"

work="$(mktemp -d)"
name="hs-policy-test-$$"
# shellcheck disable=SC2317  # invoked via trap
cleanup() { docker rm -f "$name" >/dev/null 2>&1 || true; rm -rf "$work"; }
trap cleanup EXIT

cat >"$work/config.yaml" <<'EOF'
server_url: http://127.0.0.1:8080
listen_addr: 127.0.0.1:8080
metrics_listen_addr: 127.0.0.1:9090
grpc_listen_addr: 127.0.0.1:50443
noise:
  private_key_path: /var/lib/headscale/noise_private.key
prefixes:
  v4: 100.64.0.0/10
  v6: fd7a:115c:a1e0::/48
  allocation: sequential
derp:
  server:
    enabled: true
    region_id: 999
    region_code: test
    region_name: test
    stun_listen_addr: 127.0.0.1:3478
    private_key_path: /var/lib/headscale/derp_server_private.key
    automatically_add_embedded_derp_region: true
  urls: []
  paths: []
  auto_update_enabled: false
database:
  type: sqlite
  sqlite:
    path: /var/lib/headscale/db.sqlite
dns:
  magic_dns: true
  base_domain: ts.invalid
  override_local_dns: false
policy:
  mode: file
  path: /etc/headscale/bootstrap-policy.json
unix_socket: /var/run/headscale/headscale.sock
unix_socket_permission: "0770"
disable_check_updates: true
EOF

cp "$policy" "$work/policy.hujson"
# The server loads only groups/tagOwners so tags can be assigned before the full policy (with tests) is checked.
python3 "$repo_root/scripts/hujson2json.py" "$policy" groups tagOwners >"$work/bootstrap-policy.json"
chmod -R a+rX "$work"

docker run -d --name "$name" --network none \
  -v "$work:/etc/headscale:ro" --tmpfs /var/lib/headscale --tmpfs /var/run/headscale \
  "$image" serve >/dev/null

for _ in $(seq 1 30); do
  docker exec "$name" headscale users list >/dev/null 2>&1 && break
  sleep 1
done

hs() { docker exec "$name" headscale "$@"; }

for u in $users; do
  hs users create "$u" >/dev/null
done

# Tests only evaluate against real nodes, so register one fake node per user and per tag.
register() { # <user> <node-name> [tag]
  local id
  id="hskey-authreq-$(python3 -c 'import secrets; print(secrets.token_hex(12))')"
  hs debug create-node --user "$1" --name "$2" --key "$id" >/dev/null
  hs auth register --user "$1" --auth-id "$id" >/dev/null
  if [ -n "${3:-}" ]; then
    local node_id
    node_id="$(hs nodes list -o json | python3 -c 'import json,sys; print(next(n["id"] for n in json.load(sys.stdin) if n["given_name"]==sys.argv[1]))' "$2")"
    hs nodes tag -i "$node_id" -t "$3" >/dev/null
  fi
}

for u in $users; do register "$u" "dev-${u//_/-}"; done
for t in $(python3 -c 'import json,sys; print(" ".join(sorted(json.load(sys.stdin)["tagOwners"])))' <"$work/bootstrap-policy.json"); do
  register david_admin "node-${t#tag:}" "$t"
done

hs policy check --file /etc/headscale/policy.hujson
echo "policy OK: $policy"
