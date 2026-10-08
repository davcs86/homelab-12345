# Decision log

Each entry gives the decision, who made it, and why. "Owner" means the repository owner decided it. "Proposed" means it is awaiting the owner's confirmation.

## D1. Infrastructure as code: Ansible only (Owner)

Ansible creates the DigitalOcean resources and configures the host. Terraform and cloud-init are not used, so there is a single toolchain.

- **DigitalOcean collection:** `digitalocean.cloud` 1.9.0, the official collection built on pydo. `community.digitalocean` was rejected because it has had no release since 2024-08.
- **Firewall:** `digitalocean.cloud.firewall` 1.9.0 only creates firewalls; it never updates rules on an existing one. The Cloud Firewall is the security boundary, so `roles/do_edge` manages it directly through the API. `filter_plugins/do_firewall.py` normalises the desired and live rules and compares them. Any drift, such as an extra public SSH rule, is overwritten with a PUT. Unit tests live in `ansible/tests/`.

## D2. Process supervision: Docker Compose + systemd, not supervisord (Owner: "best for our use case")

The target is a DigitalOcean droplet, deployed from GitHub Actions with blue/green deploys.

- **Blue/green happens at the droplet level** (see D4), so the process manager on each droplet only has to keep a fixed set of containers healthy.
- **Compose already does that:** restart policies, healthchecks, `depends_on: service_healthy`, pinned images. dockerd uses `live-restore`, so containers keep running while dockerd itself restarts.
- **systemd** owns the Compose project: boot ordering after `docker.service` and the tailnet, plus the journal.
- **Supervisord would be redundant.** Running `docker compose` under supervisord means two restart loops fighting each other. Running supervisord inside a container (the deleted App Platform template) hides process failures from Docker healthchecks.
- **Supervisord's remaining place:** a small project that is not containerised can still run under supervisord on another host or in its own container. It is not on this node's critical path.

## D3. Region, volume, droplet (Owner: sfo3 and the volume; size proposed)

- **Region:** `sfo3`. The API confirmed on 2026-10-08 that it offers Basic sizes and block storage.
- **Volume:** the pgBackRest repository goes on a 15 GB Block Storage volume.
  - It is independent of the droplet's lifecycle, so it survives a rebuild or a cutover.
  - It is excluded from droplet backups.
  - A full repository cannot fill the root disk that headscale's SQLite database lives on.
- **Size:** `sfo3` does not offer the generic `s-1vcpu-2gb`; it offers only the `-amd`/`-intel` variants. The size is pending (see `pending.yml`). Recommended: `s-1vcpu-2gb-amd` (2 GB RAM, 50 GB disk, $14/mo).

## D4. Blue/green model (Proposed; implemented in a later round)

- **Colours:** two droplets, `edge-blue` and `edge-green`. Each has the tags `homelab_edge` and `homelab_edge_<colour>`.
- **Shared, colour-independent resources:** the Cloud Firewall (attached by tag), the reserved IPv4 and the data volume.
- **Provisioning only attaches shared resources that are free.** It never takes them from the live colour.
- **Cutover playbook** (to come):
  1. Freeze headscale writes on the live colour.
  2. Take the final encrypted state export and restore it on the standby colour.
  3. Run the standby colour's health checks.
  4. Move the reserved IP and the data volume.
  5. Verify.
  6. Keep the old colour for rollback, then destroy it.
- **headscale is a single-writer SQLite service,** so blue and green are never active together. The cutover has a short control-plane write gap. Tunnels that already exist keep forwarding traffic throughout.
- **Reserved IP:** blue/green therefore requires the reserved IP (`edge_reserved_ip_enabled: true`). A reserved IP is free while it is assigned.

## D5. Version pinning policy (Proposed)

- **Exact pins:** everything we choose is pinned exactly. That covers Docker Engine, containerd, the Compose and buildx plugins, Ansible and its collections, GitHub Actions (by commit SHA), and container images (by tag and digest, in a later round). Docker packages are also apt-held, so unattended-upgrades cannot move them.
- **Ubuntu archive packages are not version-pinned.** This covers chrony, fail2ban and openssh. Pinning them would block unattended security upgrades, which deliverable 3 requires. The two requirements conflict, and security wins here. Reproducibility for these packages comes from the LTS release and its security pocket.

| Component | Version | Why |
|---|---|---|
| ansible-core | 2.21.5 | Latest stable at authoring time |
| digitalocean.cloud | 1.9.0 | Official, maintained DigitalOcean collection |
| ansible.posix / community.general | 2.2.2 / 13.5.0 | Latest stable |
| docker-ce / cli | 5:29.8.2-1 | Latest stable in download.docker.com for noble and resolute |
| containerd.io | 2.3.6-1 | Paired with docker-ce 29.8.2 in the same repository snapshot |
| docker-compose-plugin | 5.6.0-1 | Same snapshot |
| docker-buildx-plugin | 0.38.0-1 | Same snapshot |
| actions/checkout | v7.0.1 (SHA-pinned) | Latest release |
| actions/setup-python | v7.0.0 (SHA-pinned) | Latest release |

## D6. Hardening defaults (Technical defaults; override if desired)

- **SSH:** a drop-in named `00-` so it wins over cloud-init's `50-`. Public-key authentication only, no root login, `AllowUsers <admin>`, no forwarding of agents, X11 or tunnels.
- **Admin sudo:** NOPASSWD. The account has a locked password because access is key-only.
- **journald:** capped at 300 MB, keeps 2 GB of disk free, 1-month retention.
- **unattended-upgrades:** security pockets only, no automatic reboot. This is the single control-plane node, so reboots are an operator or blue/green decision.
- **fail2ban:** sshd jail on the systemd backend using nftables. The tailnet ranges are never banned.
- **chrony:** used for time sync, with the host on UTC.
- **Docker daemon:** `local` log driver capped at 3 × 10 MB per container, `live-restore`, `no-new-privileges`, `icc=false`, no userland proxy.
