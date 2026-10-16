# Home-side setup

| Host | Needs |
|---|---|
| backup host (`tag:backup`) | user `edge-backup`; `authorized_keys` line printed by the deploy run: `restrict,command="rrsync -wo ~/headscale" ssh-ed25519 …`; then put `ssh-keyscan backup.ts.natanddavehouse.com` output into `backup_host_known_hosts` |
| Proxmox (`tag:pve`) | systemd timer, every 60 s: `curl -fsS -X POST -H "Authorization: Bearer $TOKEN" "https://status.ts.natanddavehouse.com/api/v1/endpoints/home_proxmox-heartbeat/external?success=true"` (`$TOKEN` = `gatus_heartbeat_pve_token` from `secrets/edge.sops.yaml`); silence for 3 min alerts |
| app VM (`tag:app`, hostname `app`) | xstockstrat env: `AGENT_PUBLIC_URL=https://xstockstrat.natanddavehouse.com/agent`, `UI_BASE_URL`/`APP_URL=https://xstockstrat.natanddavehouse.com`; config key `agent.oauth.allowed_redirect_uris=https://claude.ai/api/mcp/auth_callback,https://claude.com/api/mcp/auth_callback` |
| DB host (`tag:db`) | pgBackRest **2.59.2** running its own TLS server on 8432 (the edge pulls backups) and pushing WAL with `repo1-host=edge.ts.natanddavehouse.com`, `repo1-host-type=tls`; client cert/key + CA from `secrets/edge.sops.yaml` (`pgbackrest_tls_client_*`, CN `db-pgbackrest`). Backup schedule on the edge is pending the PG version and data dir. |
