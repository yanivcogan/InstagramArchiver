from slowapi import Limiter
from starlette.requests import Request


def _get_real_ip(request: Request) -> str:
    # Respect reverse-proxy headers so all users behind nginx don't share one bucket
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=_get_real_ip)
