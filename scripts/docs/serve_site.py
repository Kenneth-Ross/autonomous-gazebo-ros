#!/usr/bin/env python3
"""Serve and rebuild repository docs as sources change; no ROS or edge access."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address, ip_network
import threading

from build_site import ROOT, build


def listener_addresses(bind, tailnet_bind):
    addresses = [bind]
    if tailnet_bind:
        address = ip_address(tailnet_bind)
        if address not in ip_network("100.64.0.0/10"):
            raise ValueError("--tailnet-bind requires a specific Tailscale IPv4 address")
        if str(address) not in addresses:
            addresses.append(str(address))
    return addresses


def snapshot():
    files = [ROOT / "README.md", ROOT / "architecture.md"]
    for directory in ("docs", "plans", "deprecated"):
        files.extend((ROOT / directory).glob("*.md"))
    files.extend(p for p in (ROOT / "docs/site/assets").rglob("*") if p.is_file())
    files.append(ROOT / "server_sim/src/my_gazebo_package/my_gazebo_package_py/track_layouts.py")
    return {str(p): p.stat().st_mtime_ns for p in files}


def watch(stop, output):
    previous = snapshot()
    while not stop.wait(2):
        current = snapshot()
        if current != previous:
            try:
                build(output=output)
                print("Documentation rebuilt", flush=True)
                previous = current
            except Exception as error:
                print(f"Documentation rebuild failed: {error}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", default=8766, type=int)
    parser.add_argument("--tailnet-bind", help="Also listen on this host's specific Tailscale IPv4 address")
    args = parser.parse_args()
    output = ROOT / "docs/site/dist"
    build(output=output)
    servers = []
    try:
        for address in listener_addresses(args.bind, args.tailnet_bind):
            servers.append(ThreadingHTTPServer((address, args.port), partial(SimpleHTTPRequestHandler, directory=str(output))))
    except Exception:
        for server in servers:
            server.server_close()
        raise
    stop = threading.Event()
    thread = threading.Thread(target=watch, args=(stop, output), daemon=True)
    thread.start()
    for server in servers[1:]:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    for address in listener_addresses(args.bind, args.tailnet_bind):
        print(f"Serving: http://{address}:{args.port}", flush=True)
    try:
        servers[0].serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        for server in servers[1:]:
            server.shutdown()
        for server in servers:
            server.server_close()
