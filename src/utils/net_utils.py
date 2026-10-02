"""
Network Utility Functions (IP resolution, Subnet Broadcast Calculation).
"""

import ipaddress
import socket
from typing import List


def get_local_ip() -> str:
    """
    Resolves the primary local IP address of the active network interface.
    Connects to a dummy external address (does not send data) to let OS determine default route IP.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Does not actually initiate a network connection
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def get_broadcast_address() -> str:
    """
    Calculates the broadcast address for peer discovery.
    Defaults to 255.255.255.255, or 127.255.255.255 on loopback.
    """
    local_ip = get_local_ip()
    if local_ip == "127.0.0.1":
        return "127.255.255.255"

    return "255.255.255.255"
