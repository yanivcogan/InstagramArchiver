import asyncio
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from logging.handlers import RotatingFileHandler

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from browsing_platform.server.routes import account, post, media, media_part, archiving_session, login, search, \
    permissions, tags, annotate, share, upload, incorporate, tag_management
from browsing_platform.server.services.file_tokens import decrypt_file_token, FileTokenError
from browsing_platform.server.services.sharing_manager import get_link_permissions
from browsing_platform.server.services.token_manager import check_token
from utils.db import DbError

load_dotenv()
is_production = os.getenv("ENVIRONMENT") == "production"

# Security check: prevent dev mode from being enabled in production
if is_production and os.getenv("BROWSING_PLATFORM_DEV") == "1":
    raise RuntimeError(
        "FATAL: BROWSING_PLATFORM_DEV=1 is set in production environment. "
        "This would bypass all authentication. Refusing to start."
    )

def _is_strong_db_password(pw: str) -> bool:
    """Return True only if the password is long enough and sufficiently varied.
    Requirements: 20+ chars, characters from at least 3 of the 4 standard classes.
    A randomly generated 20-char alphanumeric password has ~119 bits of entropy."""
    if len(pw) < 20:
        return False
    classes = sum([
        bool(re.search(r'[a-z]', pw)),
        bool(re.search(r'[A-Z]', pw)),
        bool(re.search(r'[0-9]', pw)),
        bool(re.search(r'[^a-zA-Z0-9]', pw)),
    ])
    return classes >= 3


if is_production and not _is_strong_db_password(os.getenv("DB_PASSWORD", "")):
    raise RuntimeError(
        "FATAL: DB_PASSWORD does not meet minimum strength requirements "
        "(20+ characters, 3+ character classes). "
        "Refusing to start in production with a weak database password."
    )

# Security check: FILE_TOKEN_SECRET must be set in production (without it all
# file requests return 401 silently rather than failing loudly at startup)
if is_production and not os.getenv("FILE_TOKEN_SECRET"):
    raise RuntimeError(
        "FATAL: FILE_TOKEN_SECRET is not set in production environment. "
        "All file requests will return 401. Refusing to start."
    )

# SERVER_HOST must be set in production — without it local_files_root is None,
# which causes all media/thumbnail URLs to be built as /None/thumbnails/... or
# /None/archives/... making them 404.
if is_production and not os.getenv("SERVER_HOST"):
    raise RuntimeError(
        "FATAL: SERVER_HOST is not set in production environment. "
        "All media URLs will be broken. Refusing to start."
    )


# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Configure logging to file (and console only in dev)
log_handler = RotatingFileHandler(
    "logs/1debug.log",
    maxBytes=10_000_000,  # 10MB
    backupCount=5
)
log_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

handlers = [log_handler]
if not is_production:
    handlers.append(logging.StreamHandler())

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=handlers
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    from browsing_platform.server.services import ws_manager
    from browsing_platform.server.services.incorporation_service import cleanup_stale_jobs
    ws_manager.set_event_loop(asyncio.get_event_loop())
    cleanup_stale_jobs()
    yield


app = FastAPI(lifespan=lifespan)


@app.exception_handler(DbError)
async def db_error_handler(request: Request, exc: DbError):
    logger.error("Unhandled database error during %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# CORS configuration
ALLOWED_ORIGINS = [
    "http://localhost:3000",      # Local React dev server
    "http://localhost:4444",      # Local API
]
if is_production:
    ALLOWED_ORIGINS = [
        "https://evidenceplatform.org",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # TUS protocol requires these response headers to be readable cross-origin
    expose_headers=["Location", "Upload-Offset", "Upload-Length", "Tus-Resumable", "Tus-Version", "Tus-Extension"],
)

# Serve the 'archives' directory statically
# middleware wraps all requests regardless of order
app.mount(
    "/archives",
    StaticFiles(directory="archives"),
    name="archives",
)
app.mount(
    "/thumbnails",
    StaticFiles(directory="thumbnails"),
    name="thumbnails"
)


class StaticFilesAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # BaseHTTPMiddleware cannot handle WebSocket upgrades — pass them straight through.
        if request.scope.get("type") == "websocket":
            return await call_next(request)
        start_time = time.time()
        if request.url.path.startswith("/archives") or request.url.path.startswith("/thumbnails"):
            # Prefer per-file token 'ft' which is bound to the file path and cannot be reused for other files.
            file_token = request.query_params.get("ft")
            try:
                # Use the request path (including leading slash) as the file_path binding.
                payload = decrypt_file_token(file_token, request.url.path)
            except FileTokenError as e:
                logger.warning(f"File token validation failed for {request.url.path}: {e}")
                return Response("Unauthorized", status_code=401)
            # access is allowed if the user supplied a valid login token or a share token
            # share tokens can be used to access static media even if the entities the media is attached to is beyond the share scope
            # this is fine because a user can not generate an encrypted payload containing their share token for arbitrary files without knowing the server secret
            if not check_token(payload.login_token).valid and not get_link_permissions(payload.login_token).view:
                logger.warning(f"Invalid embedded login token for {request.url.path}")
                return Response("Unauthorized", status_code=401)
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "media-src 'self' blob:; "
            "connect-src 'self'; "
            "font-src 'self' data:; "
            "form-action 'self'; "
            "frame-ancestors 'none';"
        )
        if is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        if is_production:
            duration_ms = (time.time() - start_time) * 1000
            client_ip = request.headers.get("X-Real-IP", request.client.host if request.client else "unknown")
            logger.info(f"{client_ip} - {request.method} {request.url.path} - {response.status_code} - {duration_ms:.1f}ms")

        return response


app.add_middleware(StaticFilesAuthMiddleware)
for r in [
    account.router,
    post.router,
    media.router,
    media_part.router,
    annotate.router,
    tags.router,
    archiving_session.router,
    search.router,
    login.router,
    permissions.router,
    share.router,
    upload.router,
    incorporate.router,
    tag_management.router,
]:
    app.include_router(r, prefix="/api")

# # # SPA catch-all route (must be last)
@app.api_route("/{full_path:path}", methods=["GET"])
async def serve_spa(request: Request, full_path: str):
    # Don't intercept broken API routes - let them 404 properly
    if full_path.startswith("api/"):
        logger.info(f"SPA catch-all: API route not found -> {full_path}")
        return Response('{"detail":"Not Found"}', status_code=404, media_type="application/json")

    build_dir = os.path.abspath("browsing_platform/client/dist")
    file_path = os.path.abspath(os.path.join(build_dir, full_path))

    # Prevent path traversal: reject any resolved path outside the build directory.
    # os.path.join discards earlier components when given an absolute path (e.g.
    # "c:/Windows/system.ini"), so we must check after resolving the full path.
    if not file_path.startswith(build_dir + os.sep) and file_path != build_dir:
        logger.warning(f"SPA catch-all: path traversal attempt blocked -> {full_path!r}")
        return Response("Not Found", status_code=404)

    # Serve actual static files if they exist
    if full_path and os.path.isfile(file_path):
        return FileResponse(file_path)

    # If it looks like a file request (has extension) but doesn't exist, return 404
    # This prevents returning index.html with 200 for missing .json, .js, .css, etc.
    if full_path and '.' in full_path.split('/')[-1]:
        logger.debug(f"SPA catch-all: File not found -> {full_path}")
        return Response('Not Found', status_code=404)

    # Otherwise, serve index.html for SPA client-side routing (e.g., /account/123)
    return FileResponse(os.path.join(build_dir, "index.html"))

if __name__ == "__main__":
    reload = not is_production
    uvicorn.run("browsing_platform.server.server:app", host="127.0.0.1", port=4444, reload=reload)
