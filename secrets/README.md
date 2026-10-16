# secrets/

Only SOPS-encrypted files live here (`*.sops.yaml`); recipients are listed in `../.sops.yaml`.

| File | Written by | Contents |
|---|---|---|
| `edge.sops.yaml` | `init-secrets` workflow (`scripts/init_secrets.py`) | deSEC token, healthchecks.io ping URL, admin console password hash, ntfy credentials, pgBackRest mTLS PKI |
| `ci-authkey.sops.yaml` | `node-admin` workflow (`mint-ci-key`) | reusable, ephemeral `tag:ci` pre-auth key (24 h default) and its expiry |
| `deploy-authkey.sops.yaml` | `deploy` workflow (`roles/deploy_key`) | reusable, ephemeral `tag:deploy` pre-auth key (90 days) |

Read a value locally:

```sh
SOPS_AGE_SSH_PRIVATE_KEY_FILE=~/keys/sops_admin sops decrypt --extract '["ntfy_alerts_token"]' secrets/edge.sops.yaml
```
