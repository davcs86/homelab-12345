# homelab edge (DigitalOcean control node)

Self-hosted [headscale](https://github.com/juanfont/headscale) control plane, embedded DERP/STUN relay, and the only
public entry point into a homelab behind CGNAT. Everything is Ansible, run from GitHub Actions; secrets are SOPS.

```
                       internet                                   tailnet (WireGuard, default-deny grants)
 Claude.ai ──https──► xstockstrat.natanddavehouse.com ─┐
                                                       │  Caddy (only reverse proxy, DNS-01 certs)
 devices ──https──► hs.natanddavehouse.com ────────────┼──► headscale :8080 (+ STUN 3478/udp)
                                                       │
                       edge-sfo3-01 (tag:edge) ────────┴──► app.ts… :3000/:9000 (tag:app) ──► db.ts… :5432 (tag:db)
                       Kuma · ntfy (tailnet-only)            ▲ heartbeat from pve (tag:pve)      │ pgBackRest TLS :8432 → edge
                       nightly age backup ───rsync/rrsync──► backup.ts… (tag:backup)
```

Public exposure is exactly **80/tcp, 443/tcp, 3478/udp** (DO Cloud Firewall). SSH is reachable only over the tailnet
(`tag:deploy` runners and admin devices). On `xstockstrat.natanddavehouse.com` the internet gets only the MCP endpoint
and the OAuth login routes; tailnet clients get the whole app through the same name (split-horizon DNS).

## Repository map

| Path | What |
|---|---|
| `playbooks/provision.yml` | DO droplet, reserved IPv4, Cloud Firewall (API via `uri`) |
| `playbooks/bootstrap-users.yml` | first contact as root: admin + deploy users |
| `playbooks/site.yml` | everything on the host: hardening, Docker, stack, tailscale, alerts, backups, pgBackRest repo, deploy key |
| `playbooks/verify-tailnet.yml` | ephemeral `tag:ci` test node: join, list, extra-record DNS, removal when offline |
| `playbooks/backup-now.yml` | run backup + restore drill now |
| `playbooks/node-admin.yml` | register / tag / expire / delete nodes, mint CI key |
| `policy/policy.hujson` | headscale grants + `tests` (tests run in CI only; see Notes) |
| `roles/stack/templates/` | `Caddyfile`, headscale `config.yaml`, ntfy `server.yml`, `compose.yml` |
| `inventories/prod/group_vars/all/` | `main.yml` (settings), `versions.yml` (every pin), `generated.yml` (reserved IP) |
| `secrets/` | SOPS files only |
| `.github/workflows/` | `ci`, `deploy`, `verify`, `init-secrets`, `node-admin` |

## Versions

All pins were at least two weeks old on 2026-10-14; container images are pinned by digest, binaries by checksum.

| Component | Pin | Why this one |
|---|---|---|
| Ubuntu | 26.04 LTS (`ubuntu-26-04-x64`) | your choice; Docker, Tailscale and PGDG all publish `resolute` packages |
| Droplet | `s-1vcpu-2gb-amd`, sfo3 | 2 GB RAM headroom, 50 GB disk (30 GB budget incl. ~15 GB pgBackRest); sfo3 is closest to Hayward |
| headscale | v0.29.4 | v0.29.5 was one day old; 0.29.5's fixes only touch `via` grants, which this policy does not use |
| tailscale (edge + runners) | 1.98.10 | newest client inside headscale 0.29.4's generated capability table (≤1.98); 0.29.4 rejects < 1.80 |
| Caddy | 2.11.6 | 2.11.7 was 11 days old |
| caddy-dns/desec | v1.1.0 | latest release |
| mholt/caddy-ratelimit | commit `5625512f` (2026-06-12) | only tag (v0.1.0) is from 2024; HEAD has been quiet for 4 months |
| Uptime Kuma | 2.5.5 | 2.5.6 was 5 days old |
| ntfy | v2.28.0 | v2.29/2.30 under two weeks; 2.28 already has declarative users/ACLs/tokens |
| Docker CE / CLI | 29.8.2 | 29.9.x under two weeks |
| containerd.io / compose / buildx | 2.3.6 / 5.5.1 / 0.37.1 | newest ≥ 2 weeks for 26.04 |
| pgBackRest | 2.59.2 (PGDG) | 2.59.3 under two weeks; **must equal the DB host's version** |
| ansible-core | 2.21.4 | 2.21.5 under two weeks |
| collections | general 13.4.0, docker 5.3.0, posix 2.2.2, sops 2.4.0, crypto 3.4.0 | newest ≥ 2 weeks |
| sops | 3.13.3 | SSH-key age recipients need ≥ 3.10 |
| age (on edge) | Ubuntu archive 1.2.1 | supports ssh-ed25519 recipients |
| actions/checkout, setup-python | v7.0.1, v7.0.0 by commit | newest ≥ 2 weeks |

Ubuntu-archive packages (fail2ban, chrony, sqlite3, age, …) are pinned by the release and receive security updates
through unattended-upgrades. Third-party packages (Docker, Tailscale, pgBackRest) are pinned and `apt-mark hold`, and
unattended-upgrades is told not to touch them.

## Rebuild from scratch

Everything below except steps 1, 4 and the device logins is a button in GitHub Actions; every workflow touching
the VPS waits for approval on the `production` environment.

1. **Keys** (once): five ed25519 keys — `sops_admin`, `backup`, `sops_deploy`, `id_ed25519_admin`, `id_ed25519_deploy`.
   Public halves go into `.sops.yaml` (`sops_admin`, `sops_deploy`), `group_vars/all/main.yml`
   (`admin_ssh_public_keys`, `deploy_ssh_public_key`, `backup_age_recipients`). Private halves: see `secrets/README.md`.
2. **GitHub → Settings → Environments → `production`**: required reviewer `davcs86`; secrets
   `DIGITALOCEAN_TOKEN` (custom scopes: droplet, firewall, reserved_ip, ssh_key, tag; read regions/sizes/images),
   `DEPLOY_SSH_KEY`, `SOPS_AGE_SSH_PRIVATE_KEY`.
3. **Actions → deploy → `provision`**. Creates the droplet and reserved IPv4 and commits `generated.yml`.
4. **DNS and tokens** (needs the reserved IP from `generated.yml`):
   - Cloudflare (`natanddavehouse.com`, all **DNS-only / grey cloud**):

     | Name | Type | Value |
     |---|---|---|
     | `hs` | A | reserved IPv4 |
     | `xstockstrat` | A | reserved IPv4 |
     | `_acme-challenge.hs` | CNAME | `hs.acme.natanddavehouse.com` |
     | `_acme-challenge.xstockstrat` | CNAME | `xstockstrat.acme.natanddavehouse.com` |
     | `_acme-challenge.ts` | CNAME | `ts.acme.natanddavehouse.com` (wildcard `*.ts…`) |

   - deSEC: create a token that can only write those three TXT RRsets, only from the reserved IP (see
     [Rotate the ACME token](#rotate-the-acme-token)). Store it as environment secret `DESEC_TOKEN`.
   - healthchecks.io: one check, period 5 min, grace 10 min, email to you; ping URL → secret `HC_PING_URL`.
   - Choose and store (≥ 16 chars, also in your password manager): `ADMIN_CONSOLE_PASSWORD`, `NTFY_DAVID_PASSWORD`.
5. **Actions → init-secrets**. Generates ntfy publisher credentials and the pgBackRest mTLS PKI, encrypts everything
   into `secrets/edge.sops.yaml`, commits it.
6. **Actions → deploy → `bootstrap`**. Opens 22/tcp to the runner's IP only, pins the host key in
   `inventories/prod/known_hosts`, configures everything, mints the `tag:deploy` key, then **closes 22/tcp and proves
   it from the runner** (also on failure). From here on use mode `tailnet`.
7. **Actions → verify**. External scan + HTTPS/routing/rate-limit checks, then the tailnet test node and a backup drill.
8. **Home side**: see [Home-side setup](#home-side-setup).

Rebuilding onto a new droplet: delete the old droplet in DO, run `provision` (re-attaches the same reserved IP, so no
DNS change), delete the `edge-sfo3-01` line from `known_hosts`, run `bootstrap`, then
[restore headscale](#restore-headscale-from-backup) so existing nodes keep working.

## Runbook

### Rotate the ACME token

The token lives in deSEC, can write only `TXT` at `hs`, `xstockstrat`, `ts` in `acme.natanddavehouse.com`, and is
accepted only from the reserved IP. In the deSEC web UI create a temporary token with *Can manage tokens*, then
(`$T` = that temporary token, `$IP` = reserved IP):

```sh
API=https://desec.io/api/v1/auth/tokens
NEW=$(curl -fsS -X POST $API/ -H "Authorization: Token $T" -H 'Content-Type: application/json' \
  -d "{\"name\":\"caddy-edge-$(date +%Y%m%d)\",\"allowed_subnets\":[\"$IP/32\"],\"max_unused_period\":\"100 00:00:00\"}")
ID=$(echo "$NEW" | jq -r .id); echo "$NEW" | jq -r .token   # -> GitHub secret DESEC_TOKEN (shown once)
P="$API/$ID/policies/rrsets/"
curl -fsS -X POST $P -H "Authorization: Token $T" -H 'Content-Type: application/json' \
  -d '{"domain":null,"subname":null,"type":null,"perm_write":false}'
for s in hs xstockstrat ts; do
  curl -fsS -X POST $P -H "Authorization: Token $T" -H 'Content-Type: application/json' \
    -d "{\"domain\":\"acme.natanddavehouse.com\",\"subname\":\"$s\",\"type\":\"TXT\",\"perm_write\":true}"
done
```

Then update secret `DESEC_TOKEN`, run **init-secrets** with `overwrite` (this also rotates ntfy publisher credentials
and the pgBackRest PKI — re-issue the DB host's client cert afterwards) — or, to rotate only this value, edit it in place:
`sops set secrets/edge.sops.yaml '["desec_token"]' '"<token>"'` — and run **deploy** (`tailnet`). Delete the old token
and the temporary token in deSEC. `max_unused_period` is 100 days because Caddy only touches it at renewal (~every 60).

### Create an ephemeral tagged pre-auth key for CI

- From GitHub: **node-admin → `ci-key`** mints a reusable, ephemeral `tag:ci` key (24 h) and commits it encrypted to
  `secrets/ci-authkey.sops.yaml`; the CI job decrypts it with its SOPS key and runs
  `tailscale up --login-server https://hs.natanddavehouse.com --auth-key "$KEY" --hostname ci-$RUN_ID`.
  Ephemeral nodes are deleted on logout, or 5 minutes after going offline.
- From an admin device (over the tailnet):
  `ssh david_admin@edge 'sudo docker compose -f /opt/edge/compose.yml exec -T headscale headscale preauthkeys create --tags tag:ci --ephemeral --expiration 1h'`

`tag:ci` can reach only `tag:app:22`.

### Add a node

1. On the device: `tailscale up --login-server https://hs.natanddavehouse.com` (Android/iOS: Tailscale app →
   *Use an alternate server*). It shows a URL ending in `hskey-authreq-…`.
2. **node-admin → `register`** with that ID and `user` = `david` or `david_admin`.
3. Servers: then **node-admin → `tag`** (e.g. `tag:app`). Tagged nodes become owned by headscale's `tagged-devices`.
   For unattended servers prefer a single-use tagged key (`preauthkeys create --tags tag:x --expiration 1h`).

### Revoke a node

- **node-admin → `delete`** with the node name: removes it and its key immediately; it must re-register to return.
- **node-admin → `expire`**: forces re-authentication but keeps the record.
- Lost admin device: also remove its key from `admin_ssh_public_keys` and run **deploy**.

### Restore headscale from backup

Archives (`edge-<UTC>.tar.age`) are on the backup host and in `/var/backups/edge` (7 days). Decrypt with the
**offline** backup key: `age -d -i backup edge-….tar.age | tar -x` → `headscale/{db.sqlite,noise_private.key,derp_server_private.key,…}`.
On the edge: `docker compose -f /opt/edge/compose.yml stop headscale`, copy `db.sqlite` and both keys into
`/var/lib/docker/volumes/edge_headscale-data/_data/`, start headscale. The noise key is what lets existing clients
reconnect without re-registering. The nightly job already restores every archive into a network-less scratch
headscale and compares nodes and noise key with production; a failure alerts via ntfy.

### Break glass

If headscale is down, SSH over the tailnet is too. Use the DigitalOcean web console (Droplet → Access → Recovery/Droplet
Console), log in as `david_admin` with the console password (SSH stays key-only), and `sudo docker compose -f /opt/edge/compose.yml up -d`.
Last resort: `deploy` → `bootstrap` only works on a fresh droplet (root login is disabled afterwards).

## Home-side setup

| Host | Needs |
|---|---|
| backup host (`tag:backup`) | user `edge-backup`; `authorized_keys` line printed by the deploy run: `restrict,command="rrsync -wo ~/headscale" ssh-ed25519 …`; then put `ssh-keyscan backup.ts.natanddavehouse.com` output into `backup_host_known_hosts` |
| Proxmox (`tag:pve`) | systemd timer, every 60 s: `curl -fsS https://kuma.ts.natanddavehouse.com/api/push/<token>` (push token from the Kuma monitor) |
| app VM (`tag:app`, hostname `app`) | xstockstrat env: `AGENT_PUBLIC_URL=https://xstockstrat.natanddavehouse.com/agent`, `UI_BASE_URL`/`APP_URL=https://xstockstrat.natanddavehouse.com`; config key `agent.oauth.allowed_redirect_uris=https://claude.ai/api/mcp/auth_callback,https://claude.com/api/mcp/auth_callback` |
| DB host (`tag:db`) | pgBackRest **2.59.2**, `repo1-host=edge.ts.natanddavehouse.com`, `repo1-host-type=tls`, client cert/key + CA from `secrets/edge.sops.yaml` (`pgbackrest_tls_client_*`, CN `db-pgbackrest`) |

## Notes and decisions

- **Policy tests run in CI only.** headscale re-runs a policy's `tests` on every reload and would reject updates while
  tagged nodes are missing (fresh tailnet, rebuilt node). The edge receives the policy with `tests` stripped;
  `scripts/policy-test.sh` registers one fake node per user/tag in a throwaway headscale and runs them.
- **The edge reaches its own control plane on 127.0.0.1** (`/etc/hosts`), so nothing depends on hairpinning through
  the reserved IP. Direct WireGuard to the edge uses hole punching (no inbound UDP besides 3478); DERP is the fallback.
- **Caddy uses host networking** so rate limits and the tailnet split see real client IPs. Upstreams resolve via
  MagicDNS (`100.100.100.100`); the edge itself runs with `--accept-dns=false`.
- **Login hardening is upstream's gap.** xstockstrat login has no lockout or MFA; the Caddy limits (5/min, 30/h per IP
  on `POST /api/auth/login`) are the only brute-force control until the app adds them.
- **Access logs** drop OAuth `code`, `state`, `txn` and `agent_cb` query values; Caddy redacts credential headers by default.
- **TODO(verify)**: source-range allowlist for the MCP endpoint, once Anthropic publishes stable connector egress
  ranges (marked in the Caddyfile).
