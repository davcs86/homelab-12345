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

## D3. Region, volume, droplet, image, backups, reserved IP (Owner)

- **Region:** `sfo3`. The API confirmed on 2026-10-08 that it offers Basic sizes and block storage.
- **Volume:** the pgBackRest repository goes on a 15 GB Block Storage volume.
  - It is independent of the droplet's lifecycle, so it survives a rebuild or a cutover.
  - It is excluded from droplet backups.
  - A full repository cannot fill the root disk that headscale's SQLite database lives on.
- **Size:** `s-1vcpu-2gb-amd` (1 vCPU, 2 GB RAM, 50 GB disk, 2 TB transfer, $14/mo). The owner accepted the $2/mo premium over the generic `s-1vcpu-2gb`, which `sfo3` does not offer. Rejected: moving to `sfo2` to get the generic size, and the 1 GB sizes (too little RAM for the planned stack).
- **Image:** `ubuntu-24-04-x64` (see D8).
- **Droplet backups:** off. The node is rebuilt from code, headscale state has its own encrypted nightly backup, and volumes are never included in droplet backups anyway.
- **Reserved IPv4:** on. It is free while assigned and blue/green requires it.

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

## D4a. IPv6 (Owner)

- **Decision:** `edge_ipv6: true`. The owner's home connection has native IPv6; `curl -6` succeeded from one device.
- **Still to check:** the home servers (Proxmox, the app VM, the backup host). The LAN or a VM bridge may not pass IPv6 through.
- **Changing it later:** the droplet module only acts when it creates a droplet. Changing the value therefore never alters a running droplet; it takes effect when a new colour is built and cut over.
- **Round 2:** allocate a reserved IPv6 (`digitalocean.cloud.reserved_ipv6`) and move it at cutover together with the reserved IPv4. Until then, public hostnames get **A records only, no AAAA**. Otherwise AAAA records would keep pointing at the old colour after a cutover.

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

## D7. Secrets: SOPS + age (Owner)

- **Tool:** sops 3.13.3. `make deps` installs it into `.venv/bin` and verifies its per-platform SHA-256 against the upstream checksums file.
- **Recipients** are set in `.sops.yaml`. There are two age recipients:
  - **Owner:** an age identity generated on the owner's machine. It never leaves that machine.
  - **CI:** an age identity whose private half is stored only as a GitHub Actions secret (`SOPS_AGE_KEY`), for the round-2 deploy workflow.

  The file **fails closed**: while it still holds placeholder recipients, every encrypt aborts and `seed-ssh-keys.sh` refuses to run.
- **Ansible:** reads `*.sops.yml` group/host vars transparently through `community.sops.sops` (2.5.0), which is enabled in `ansible.cfg`.
- **SSH keys:** `scripts/seed-ssh-keys.sh` generates the ed25519 keys (`-a 100`).
  - **`operator`** is for humans; **`ci`** is for GitHub Actions. They are separate so either can be revoked on its own.
  - The plaintext private key exists only in a 0700 tmpfs directory while it is encrypted; it is shredded on exit.
  - Every key is checked by decrypting it and re-deriving its public key before the script trusts the encrypted copy.
  - Existing keys are never overwritten.
  - Public keys are generated into `group_vars/all/ssh_public_keys.yml`.
  - `scripts/ssh-agent-load.sh` decrypts a key straight into `ssh-agent` with a lifetime. Plaintext never touches disk.
- **Why the owner must generate the age identity:** whoever holds it can decrypt every secret in the repository. If it were generated in a cloud session, it would have to be sent through that session, and would then exist outside the owner's control.
- **Verified in a throwaway copy with throwaway age identities:**
  - Generation is idempotent, and no plaintext key is left on disk or in tmpfs.
  - The owner identity and the CI identity can each decrypt independently.
  - A foreign identity is refused.
  - `ssh-agent` loading works.
  - Ansible decrypts a `*.sops.yml` var.
  - The placeholder guard works.

## D8. OS: Ubuntu 24.04 LTS (Owner), Debian 13 considered

- **Ubuntu 24.04 (`ubuntu-24-04-x64`):**
  - Standard security support until 2029-05; ESM until 2034 through the free Ubuntu Pro personal tier.
  - It is DigitalOcean's most-tested image for the metrics and droplet agents.
  - It has upstream Docker and Tailscale packages.
  - Livepatch is available through Pro.
- **Debian 13 (`debian-13-x64`, available in `sfo3`):**
  - Smaller base install: no snapd and no Ubuntu Pro/MOTD tooling. That saves roughly a few hundred MB of disk and some idle RAM.
  - A more conservative release cadence.
  - Upstream Docker and Tailscale packages exist as well.
  - Security support runs about 3 years, plus about 2 years of volunteer LTS. That is shorter than Ubuntu with ESM, and Debian has no livepatch.
- **Conclusion:** neither changes the architecture. Footprint is the only material difference, and 50 GB of disk with 2 GB RAM absorbs it. Ubuntu stays, as the owner decided. Switching later means changing `edge_image` and the Docker repository/suite mapping, building the other colour, and cutting over. No data migration is needed beyond the normal cutover.

## D9. Domain and DNS provider (Owner: `nrdc.house` on Route 53)

- **Registrar and DNS:** both in Route 53, which supports registering `.house`.
- **Credential scope:** Route 53 can limit a credential to TXT records named `_acme-challenge.*` in one zone, using the IAM condition keys `ChangeResourceRecordSetsRecordTypes` and `ChangeResourceRecordSetsNormalizedRecordNames`. That meets the "TXT-only token" requirement without delegating a separate challenge zone.
- **Details:** see `docs/dns.md`. The hostnames and the static-record management choice are pending.
