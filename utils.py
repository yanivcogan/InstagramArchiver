import psutil
import socket

def get_local_ip():
    for iface, addrs in psutil.net_if_addrs().items():
        for addr in addrs:
            if (
                    addr.family == socket.AF_INET
                    and not addr.address.startswith('127.')
                    and not addr.address.startswith('10.')
                    and not addr.address.startswith('192.168.')
                    and not addr.address.startswith('172.')
            ):
                return addr.address
    return '127.0.0.1'