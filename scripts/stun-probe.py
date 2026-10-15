#!/usr/bin/env python3
"""STUN binding request in Tailscale's format; prints the mapped address per target, exits 1 if any target fails.

headscale's embedded STUN server (tailscale.com/net/stun) only answers requests that carry SOFTWARE "tailnode"
and end in a FINGERPRINT; a bare RFC 5389 request is silently dropped.
Usage: stun-probe.py HOST [HOST...]   (port 3478)
"""
import ipaddress
import os
import socket
import struct
import sys
import zlib

MAGIC = 0x2112A442


def request(txid: bytes) -> bytes:
    software = b"tailnode"
    attrs_len = (4 + len(software)) + 8
    b = struct.pack("!HHI", 0x0001, attrs_len, MAGIC) + txid + struct.pack("!HH", 0x8022, len(software)) + software
    return b + struct.pack("!HHI", 0x8028, 4, zlib.crc32(b) ^ 0x5354554E)


def mapped_address(resp: bytes) -> str:
    key = struct.pack("!I", MAGIC) + resp[8:20]  # XOR key: magic cookie, then transaction ID for IPv6
    i = 20
    while i + 4 <= len(resp):
        typ, length = struct.unpack("!HH", resp[i:i + 4])
        val = resp[i + 4:i + 4 + length]
        if typ == 0x0020 and len(val) >= 8:  # XOR-MAPPED-ADDRESS
            port = struct.unpack("!H", val[2:4])[0] ^ (MAGIC >> 16)
            raw = bytes(a ^ b for a, b in zip(val[4:], key))
            addr = ipaddress.ip_address(raw)
            if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:  # server listens on [::]
                addr = addr.ipv4_mapped
            return f"[{addr}]:{port}" if addr.version == 6 else f"{addr}:{port}"
        i += 4 + length + (-length % 4)
    return "?"


def probe(host: str) -> bool:
    txid = os.urandom(12)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(5)
        try:
            s.sendto(request(txid), (host, 3478))
            resp, src = s.recvfrom(2048)
        except OSError as e:
            print(f"{host}: {type(e).__name__} {e}")
            return False
    ok = resp[:2] == b"\x01\x01" and resp[8:20] == txid
    print(f"{host}: {'binding success' if ok else 'unexpected reply'} from {src[0]}, mapped {mapped_address(resp)}")
    return ok


if __name__ == "__main__":
    results = [probe(h) for h in sys.argv[1:]]
    sys.exit(0 if results and all(results) else 1)
