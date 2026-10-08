# homelab edge: headscale control node on DigitalOcean

This repository holds the infrastructure-as-code (Ansible only) for the public edge of a homelab overlay network. The home network sits behind CGNAT, so every home node dials out to this VPS and nothing listens at home.

Two things are public on this node: the headscale control plane and the `/agent` MCP route. Everything else is reachable only over the tailnet.

> **Status: round 1 (foundation).** This round builds the DigitalOcean resources, OS hardening, Docker Engine and the pgBackRest data volume. The headscale/Caddy/monitoring stack, the policy, backups and blue/green cutover come next. They are blocked on open decisions (see [Open items](#open-items)).
> Design decisions and version rationale are in [`docs/decisions.md`](docs/decisions.md).

## Layout

```
ansible/
  ansible.cfg, requirements.{txt,yml}    pinned tooling + collections
  inventories/prod/
    digitalocean.yml                     dynamic inventory (tag homelab_edge)
    group_vars/all/main.yml              decided values
    group_vars/all/pending.yml           UNDECIDED values (preflight blocks until set)
  playbooks/
    provision.yml   DO droplet (per colour), Cloud Firewall, volume, reserved IP
    bootstrap.yml   first root login: admin user + sshd hardening (run once per droplet)
    site.yml        OS hardening, Docker Engine, data volume mount
  roles/{preflight,do_edge,base,docker,data_volume}
  tests/                                 unit tests (firewall drift detection)
docs/decisions.md
```

## Prerequisites

- Python 3.12 or newer and `make` on the operator machine. CI runs on GitHub Actions.
- `DIGITALOCEAN_TOKEN` exported in your shell. It is never written to the repo or logged; API tasks run with `no_log`.
- Every value in `ansible/inventories/prod/group_vars/all/pending.yml` filled in. Until then, `preflight` fails with the name of the missing value.

```bash
make deps    # .venv + pinned ansible-core, pydo, lint tools, collections
make lint    # yamllint + ansible-lint (production profile)
make test    # unit tests + playbook syntax check
```

## Runbook

### Build a colour from scratch (round 1 scope)

```bash
make provision COLOR=blue   # droplet, firewall (bootstrap SSH limited to bootstrap_ssh_cidrs), volume, reserved IP
make bootstrap COLOR=blue   # ONCE, as root: creates admin user, disables root/password SSH
make site      COLOR=blue   # converge hardening + Docker + volume mount (idempotent; re-run any time)
```

- **First provision:** the reserved IP is allocated and printed. Record it as `edge_reserved_ip` in `pending.yml` and commit it.
- **After bootstrap:** root SSH is refused, so `bootstrap.yml` cannot be re-run on that droplet. That is intended. Use `site.yml` from then on.
- **Closing public SSH:** once tailnet SSH works (round 2), set `bootstrap_ssh_cidrs: []` and re-run `make provision`. The firewall drift check removes the rule. The DO droplet console agent stays available as break-glass access.

### Pending runbook sections (round 2+)

These are written together with the components they operate on:

- Rotate the ACME DNS token.
- Create an ephemeral, tagged pre-auth key for CI.
- Add a node.
- Revoke a node.
- Blue/green cutover and rollback.
- Restore headscale from an encrypted backup.

## Open items

Asked and still unanswered (round 2):

- **Domain:** deferred by the owner. Needed for the headscale `server_url`, the agent hostname, the MagicDNS `base_domain` and the DNS-01 provider.
- **Ubuntu release:** 24.04 or 26.04. (Droplet size is decided: `s-1vcpu-2gb-amd`.)
- **Costs:** droplet backups. The reserved IP is required for blue/green and free while attached, but the owner has not explicitly confirmed it.
- **Admin access:** `admin_username`, `admin_ssh_public_keys`, and `bootstrap_ssh_cidrs` (the owner's current public IP as a /32).
- **IPv6:** check the home servers. In round 2, add a reserved IPv6 that moves at cutover; until then, publish A records only (see D4a).
- **Extra grant:** `tag:ci` → `tag:edge:22`, needed for GitHub Actions deploys.
- **Probe stack:** Uptime Kuma or Prometheus blackbox.
- **Policy and backups:** admin identity, OpenClaw tag, agent port, the extra grants the deliverables need, backup push or pull, the age recipient, DERP fallback, bootstrap SSH CIDR.
- **Secrets management:** SOPS + age is proposed, not yet confirmed.
