"""Unit tests for the do_firewall_normalize filter (drift detection)."""
import importlib.util
import pathlib
import unittest

_SPEC = importlib.util.spec_from_file_location(
    "do_firewall",
    pathlib.Path(__file__).resolve().parents[1] / "roles/do_edge/filter_plugins/do_firewall.py",
)
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
norm = _MOD.do_firewall_normalize

ANY = {"addresses": ["0.0.0.0/0", "::/0"]}
DESIRED = {
    "name": "homelab-edge",
    "tags": ["homelab_edge"],
    "inbound_rules": [
        {"protocol": "tcp", "ports": "443", "sources": ANY},
        {"protocol": "udp", "ports": "3478", "sources": ANY},
    ],
    "outbound_rules": [
        {"protocol": "tcp", "ports": "0", "destinations": ANY},
        {"protocol": "icmp", "destinations": ANY},
    ],
}


class NormalizeTest(unittest.TestCase):
    def test_live_api_shape_equals_desired(self):
        live = {
            "id": "x", "status": "succeeded", "droplet_ids": [], "tags": ["homelab_edge"],
            "inbound_rules": [
                {"protocol": "udp", "ports": "3478", "sources": {"addresses": ["::/0", "0.0.0.0/0"]}},
                {"protocol": "tcp", "ports": "443", "sources": ANY},
            ],
            "outbound_rules": [
                {"protocol": "icmp", "ports": "0", "destinations": ANY},
                {"protocol": "tcp", "ports": "all", "destinations": ANY},
            ],
        }
        self.assertEqual(norm(live), norm(DESIRED))

    def test_extra_public_ssh_rule_is_drift(self):
        live = dict(DESIRED, inbound_rules=DESIRED["inbound_rules"] + [
            {"protocol": "tcp", "ports": "22", "sources": ANY}])
        self.assertNotEqual(norm(live), norm(DESIRED))

    def test_widened_source_is_drift(self):
        narrow = dict(DESIRED, inbound_rules=[
            {"protocol": "tcp", "ports": "22", "sources": {"addresses": ["203.0.113.10/32"]}}])
        wide = dict(DESIRED, inbound_rules=[
            {"protocol": "tcp", "ports": "22", "sources": ANY}])
        self.assertNotEqual(norm(narrow), norm(wide))

    def test_none(self):
        self.assertIsNone(norm(None))


if __name__ == "__main__":
    unittest.main()
