# DNS: nrdc.house (AWS Route 53)

`nrdc.house` is registered with Route 53 and its DNS is hosted there too. Registering the domain creates the hosted zone and sets its name servers automatically.

## Registration settings

| Setting | Value | Why |
|---|---|---|
| Auto-renew | **on** | If the domain lapses, every node loses its control plane |
| Transfer lock | **on** | Blocks a hijack by transfer |
| Privacy protection | **on** | |
| DNSSEC signing | off for now | Turn it on once everything is stable. A misconfiguration takes the whole domain offline. |

## Hostnames (proposed, awaiting confirmation)

| Purpose | Name | Public DNS |
|---|---|---|
| headscale `server_url` | `hs.nrdc.house` | A → reserved IPv4 |
| Public MCP route `/agent` | `agent.nrdc.house` | A → reserved IPv4 |
| MagicDNS `base_domain` and `extra_records` | `ts.nrdc.house` | **never published** |

- **The headscale hostname is effectively permanent.** Every node stores it as its login server, so renaming it later means re-registering every node.
- **`hs.` must not sit inside `ts.`.** headscale requires the `server_url` host to be outside `base_domain`.
- **`ts.` is a real subdomain** that only the tailnet resolves. Internal services can still get Let's Encrypt certificates through DNS-01, because the challenge only needs a TXT record in this zone.

## Records

The A records take their value from the reserved IPv4, which is allocated on the first `make provision`. That IP stays the same across blue/green cutovers, so these records never change on a cutover.

| Name | Type | TTL | Value | Purpose |
|---|---|---|---|---|
| `hs.nrdc.house` | A | 300 | reserved IPv4 | headscale |
| `agent.nrdc.house` | A | 300 | reserved IPv4 | public `/agent` |
| `nrdc.house` | CAA | 3600 | `0 issue "letsencrypt.org"` | Only Let's Encrypt may issue certificates |
| `nrdc.house` | CAA | 3600 | `0 issuewild ";"` | No wildcard certificates |
| `nrdc.house` | MX | 3600 | `0 .` | Null MX: the domain never receives mail |
| `nrdc.house` | TXT | 3600 | `"v=spf1 -all"` | Nothing may send mail as this domain |
| `_dmarc.nrdc.house` | TXT | 3600 | `"v=DMARC1; p=reject; adkim=s; aspf=s"` | Receivers reject spoofed mail |

**Never create:**
- AAAA records. These wait until a reserved IPv6 moves with cutover (decisions D4a).
- Wildcard records.
- Anything under `ts.nrdc.house`.
- `_acme-challenge` records by hand. Caddy creates and deletes those itself.
- Any record that points at the home network.

**Later hardening:** once the Let's Encrypt account exists, narrow the CAA record to:

`0 issue "letsencrypt.org; validationmethods=dns-01; accounturi=<account URL>"` (RFC 8657)

## Certificate credential (DNS-01): TXT-only IAM user

1. Create the IAM user `homelab-acme` with no console access.
2. Attach the inline policy [`route53-acme-policy.json`](route53-acme-policy.json), with `ZONEID` replaced by the hosted zone ID.

With that policy, a leaked key can only create, update or delete `_acme-challenge.*` TXT records in this one zone.

**Storage:** the access key is stored only in `secrets/aws-acme.sops.yaml`. Encrypt it yourself with `sops` once the age recipients are set in `.sops.yaml`. It never goes into chat, logs or plain-text files.

**Rotation (zero downtime):**
1. Create a second access key.
2. `sops secrets/aws-acme.sops.yaml` and replace the key.
3. Redeploy.
4. Confirm a certificate renewal works.
5. Deactivate, then delete, the old key.

## Open decision: who maintains the static records

The TXT-only credential cannot manage the A, CAA, MX or TXT records above.

- **(a) Recommended:** create them by hand once. They are static because the reserved IP never changes. Ansible adds a read-only check that fails if live DNS differs from this file.
- **(b)** Ansible manages them with `amazon.aws.route53`, using a second, broader credential that the operator supplies only at run time and that is never stored on the droplet.
