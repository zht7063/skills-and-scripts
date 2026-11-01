#!/usr/bin/env python3
"""[LOCAL] Application-layer UDP test through the local client's SOCKS5 UDP ASSOCIATE (mihomo/sing-box "mixed" port).

Why not just curl: curl proves TCP. This sends real UDP datagrams through the proxy and checks the answers:
  1. DNS-over-UDP : an A query for example.com to a public resolver (1.1.1.1 -> 8.8.8.8 -> 9.9.9.9 fallbacks).
                    Pass = reply has the same ID, QR=1, RCODE=0 and at least one answer.
  2. STUN         : a Binding request (RFC 5389) to a public STUN server (stun.l.google.com:19302 ->
                    stun.cloudflare.com:3478 -> stun.nextcloud.com:3478 fallbacks).
                    Pass = XOR-MAPPED-ADDRESS comes back; it is the public IP the UDP packet left from,
                    which must be the sing-box SERVER's IP (use --expect-ip SERVER_IP to assert it).
  3. [OPTIONAL] --compare-direct: the same STUN query WITHOUT the proxy, to show the two addresses differ.
                    Not meaningful when the machine itself egresses through a transparent proxy/NAT pool.
Each test passes if ANY server of its fallback list answers. Needs only the Python 3 standard library.
Exit code 0 = all selected tests passed, 1 = a test failed, 2 = could not set up UDP ASSOCIATE at all.

Usage: udp-app-test.py [--socks 127.0.0.1:7890] [--only dns|stun] [--expect-ip IP] [--compare-direct] [--timeout 5]
The SOCKS port defaults to $LOCAL_MIXED_PORT, else 7890. No credentials are used or printed.
"""
import argparse, os, random, socket, struct, sys, time

DNS_SERVERS = [("1.1.1.1", 53), ("8.8.8.8", 53), ("9.9.9.9", 53)]
STUN_SERVERS = [("stun.l.google.com", 19302), ("stun.cloudflare.com", 3478), ("stun.nextcloud.com", 3478)]
MAGIC = 0x2112A442


def dns_query(name="example.com"):
    qid = random.randrange(65536)
    q = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\0"
    return qid, struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0) + q + struct.pack(">HH", 1, 1)


def dns_ok(qid, data):
    if len(data) < 12:
        return False, "short reply"
    rid, flags, _, an = struct.unpack(">HHHH", data[:8])
    if rid != qid:
        return False, "ID mismatch"
    if not flags & 0x8000 or flags & 0xF:
        return False, f"flags=0x{flags:04x}"
    return an > 0, f"{an} answer(s)"


def stun_request():
    tid = os.urandom(12)
    return tid, struct.pack(">HHI", 0x0001, 0, MAGIC) + tid


def stun_mapped(tid, data):
    if len(data) < 20 or data[8:20] != tid:
        return None
    mtype, mlen = struct.unpack(">HH", data[:4])
    if mtype != 0x0101:
        return None
    pos = 20
    while pos + 4 <= 20 + mlen:
        atype, alen = struct.unpack(">HH", data[pos:pos + 4])
        val = data[pos + 4:pos + 4 + alen]
        if atype == 0x0020 and val[1] == 1:  # XOR-MAPPED-ADDRESS, IPv4
            return socket.inet_ntoa(bytes(b ^ m for b, m in zip(val[4:8], struct.pack(">I", MAGIC))))
        if atype == 0x0001 and val[1] == 1:  # MAPPED-ADDRESS fallback
            return socket.inet_ntoa(val[4:8])
        pos += 4 + alen + (-alen % 4)
    return None


class Socks5Udp:
    """Minimal SOCKS5 UDP ASSOCIATE client (RFC 1928). The TCP control connection must stay open."""

    def __init__(self, host, port, timeout):
        self.ctl = socket.create_connection((host, port), timeout=timeout)
        self.ctl.sendall(b"\x05\x01\x00")
        if self.ctl.recv(2) != b"\x05\x00":
            raise RuntimeError("SOCKS5 greeting refused (is a username/password set on the mixed port?)")
        self.ctl.sendall(b"\x05\x03\x00\x01\x00\x00\x00\x00\x00\x00")
        rep = self.ctl.recv(10)
        if len(rep) < 10 or rep[1] != 0:
            raise RuntimeError(f"UDP ASSOCIATE refused (reply code {rep[1] if len(rep) > 1 else '?'})")
        bnd_host = socket.inet_ntoa(rep[4:8])
        bnd_port = struct.unpack(">H", rep[8:10])[0]
        self.relay = (host if bnd_host == "0.0.0.0" else bnd_host, bnd_port)
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.settimeout(timeout)

    def exchange(self, dst, payload):
        h, p = dst
        try:
            head = b"\x00\x00\x00\x01" + socket.inet_aton(h)
        except OSError:
            head = b"\x00\x00\x00\x03" + bytes([len(h)]) + h.encode()
        self.udp.sendto(head + struct.pack(">H", p) + payload, self.relay)
        data, _ = self.udp.recvfrom(4096)
        atyp = data[3]
        off = 4 + (4 if atyp == 1 else 16 if atyp == 4 else 1 + data[4]) + 2
        return data[off:]

    def close(self):
        self.udp.close(); self.ctl.close()


def direct_exchange(dst, payload, timeout):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(timeout)
    try:
        s.sendto(payload, (socket.gethostbyname(dst[0]), dst[1]))
        return s.recvfrom(4096)[0]
    finally:
        s.close()


def main():
    ap = argparse.ArgumentParser(description="UDP application-layer test through a SOCKS5 UDP ASSOCIATE proxy")
    ap.add_argument("--socks", default=f"127.0.0.1:{os.environ.get('LOCAL_MIXED_PORT', '7890')}")
    ap.add_argument("--only", choices=["dns", "stun"])
    ap.add_argument("--expect-ip", help="the sing-box server's public IP; STUN must report it")
    ap.add_argument("--compare-direct", action="store_true", help="[OPTIONAL] also run STUN without the proxy")
    ap.add_argument("--timeout", type=float, default=5.0)
    a = ap.parse_args()
    host, port = a.socks.rsplit(":", 1)
    try:
        c = Socks5Udp(host, int(port), a.timeout)
    except (OSError, RuntimeError) as e:
        print(f"SETUP FAIL: {e}"); return 2
    print(f"UDP ASSOCIATE ok via {a.socks}, relay {c.relay[0]}:{c.relay[1]}")
    failed = False
    if a.only in (None, "dns"):
        ok = False
        for srv in DNS_SERVERS:
            qid, q = dns_query()
            t0 = time.time()
            try:
                good, info = dns_ok(qid, c.exchange(srv, q))
            except OSError as e:
                print(f"  dns   {srv[0]}:{srv[1]} no reply ({e.__class__.__name__})"); continue
            print(f"  dns   {srv[0]}:{srv[1]} {'ok' if good else 'BAD'} {info} {int((time.time()-t0)*1000)}ms")
            if good: ok = True; break
        print("PASS dns-over-udp" if ok else "FAIL dns-over-udp"); failed |= not ok
    if a.only in (None, "stun"):
        ok = False; seen = None
        for srv in STUN_SERVERS:
            tid, req = stun_request()
            t0 = time.time()
            try:
                seen = stun_mapped(tid, c.exchange(srv, req))
            except OSError as e:
                print(f"  stun  {srv[0]}:{srv[1]} no reply ({e.__class__.__name__})"); continue
            print(f"  stun  {srv[0]}:{srv[1]} mapped={seen} {int((time.time()-t0)*1000)}ms")
            if seen: break
        if seen and a.expect_ip and seen != a.expect_ip:
            print(f"FAIL stun: UDP left from {seen}, expected the server {a.expect_ip}"); failed = True
        elif seen:
            print(f"PASS stun (UDP egress IP {seen}" + (", matches --expect-ip)" if a.expect_ip else "; give --expect-ip to assert it is the server)"))
        else:
            print("FAIL stun"); failed = True
        if a.compare_direct and seen:
            for srv in STUN_SERVERS:
                tid, req = stun_request()
                try:
                    d = stun_mapped(tid, direct_exchange(srv, req, a.timeout))
                except OSError:
                    continue
                if d:
                    print(f"  [optional] direct STUN IP {d} vs proxied {seen}: " + ("differ (good)" if d != seen else "SAME (proxy not in the path, or transparent egress)"))
                    break
            else:
                print("  [optional] direct STUN: no reply (UDP blocked without the proxy?)")
    c.close()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
