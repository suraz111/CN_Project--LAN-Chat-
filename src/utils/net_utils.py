"""
Network Utility Functions (IP resolution, Subnet Broadcast Calculation).
"""

import ipaddress
import socket
from typing import List


def get_local_ip() -> str:
    """
    Resolves the primary local IP address of the active network interface.
    Prioritizes active local Wi-Fi / LAN IP addresses (192.168.x.x, 10.x.x.x, 172.16-31.x.x).
    """
    # 1. Connect to dummy UDP socket to query default route
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        if not ip.startswith("127.") and not ip.startswith("169.254."):
            return ip
    except Exception:
        pass
    finally:
        s.close()

    # 2. Check gethostbyname_ex for standard private LAN IPs
    try:
        hostname = socket.gethostname()
        ips = socket.gethostbyname_ex(hostname)[2]
        # Prefer typical Wi-Fi / home router subnets (192.168.x.x)
        for ip in ips:
            if ip.startswith("192.168."):
                return ip
        # Prefer 10.x.x.x or 172.x.x.x
        for ip in ips:
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                return ip
    except Exception:
        pass

    return "127.0.0.1"


def get_broadcast_address() -> str:
    """
    Calculates the broadcast address for peer discovery.
    Defaults to 255.255.255.255, or 127.255.255.255 on loopback.
    """
    local_ip = get_local_ip()
    if local_ip == "127.0.0.1":
        return "127.255.255.255"

    return "255.255.255.255"


def get_all_network_interfaces() -> List[dict]:
    """
    Enumerates all active local network interfaces (Wi-Fi, Ethernet, Hotspot, Loopback)
    with their IPv4 addresses, identification labels, and primary status.
    Uses pure Python standard library without external dependencies.
    """
    interfaces = []
    seen_ips = set()
    primary_ip = get_local_ip()

    try:
        hostname = socket.gethostname()
        host_ips = socket.gethostbyname_ex(hostname)[2]
        for ip in host_ips:
            if ip not in seen_ips and not ip.startswith("127."):
                seen_ips.add(ip)
                interfaces.append({
                    "name": f"Local LAN Adapter ({ip})",
                    "ip": ip,
                    "is_primary": (ip == primary_ip),
                    "broadcast": "255.255.255.255",
                    "status": "Active",
                })
    except Exception:
        pass

    # Ensure primary IP is included even if gethostbyname_ex misses it
    if primary_ip not in seen_ips and primary_ip != "127.0.0.1":
        seen_ips.add(primary_ip)
        interfaces.append({
            "name": f"Primary Adapter ({primary_ip})",
            "ip": primary_ip,
            "is_primary": True,
            "broadcast": "255.255.255.255",
            "status": "Active",
        })

    # Always include Loopback interface
    interfaces.append({
        "name": "Loopback (Localhost)",
        "ip": "127.0.0.1",
        "is_primary": (primary_ip == "127.0.0.1"),
        "broadcast": "127.255.255.255",
        "status": "Active",
    })

    return interfaces
