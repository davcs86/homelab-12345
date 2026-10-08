"""Normalise DigitalOcean Cloud Firewall specs so desired and live state compare.

digitalocean.cloud.firewall (1.9.0) is create-only: it never updates rules on an
existing firewall. The firewall is our security boundary, so drift must be
detected and corrected; the do_edge role therefore manages it through the API
and uses this filter to decide whether a PUT is required.
"""

_ENDPOINT_KEYS = ("addresses", "droplet_ids", "load_balancer_uids", "tags", "kubernetes_ids")


def _norm_ports(protocol, ports):
    if protocol == "icmp":
        return "0"
    ports = str(ports if ports not in (None, "") else "0")
    return "0" if ports == "all" else ports


def _norm_endpoints(ep):
    ep = ep or {}
    return tuple((k, tuple(sorted(str(v) for v in ep.get(k) or []))) for k in _ENDPOINT_KEYS)


def _norm_rules(rules, side):
    out = []
    for r in rules or []:
        proto = str(r.get("protocol", "")).lower()
        out.append((proto, _norm_ports(proto, r.get("ports")), _norm_endpoints(r.get(side))))
    return sorted(out)


def do_firewall_normalize(fw):
    """Return a hashable, order-independent representation of a firewall spec."""
    if not fw:
        return None
    return repr((
        tuple(sorted(fw.get("tags") or [])),
        tuple(sorted(int(i) for i in fw.get("droplet_ids") or [])),
        tuple(_norm_rules(fw.get("inbound_rules"), "sources")),
        tuple(_norm_rules(fw.get("outbound_rules"), "destinations")),
    ))


class FilterModule(object):
    def filters(self):
        return {"do_firewall_normalize": do_firewall_normalize}
