import socket

import requests


def get_my_private_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Connect to a public IP, doesn't have to be reachable
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def get_my_public_ip():
    try:
        response = requests.get('https://api.ipify.org?format=text', timeout=5)
        response.raise_for_status()
        return response.text.strip()
    except Exception:
        return '0.0.0.0'

if __name__ == "__main__":
    private_ip = get_my_private_ip()
    public_ip = get_my_public_ip()
    print(f"My Private IP: {private_ip}")
    print(f"My Public IP: {public_ip}")