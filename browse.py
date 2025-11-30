import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from browsing_platform.server.routes import account, post, media, media_part, archiving_session, login, search, \
    permissions, tags, annotate
from browsing_platform.server.services.token_manager import check_token

load_dotenv()
is_dev = os.getenv("BROWSING_PLATFORM_DEV", "")
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the 'archives' directory statically
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


class TokenAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not is_dev:
            if request.url.path.startswith("/archives") or request.url.path.startswith("/thumbnails"):
                token = request.query_params.get("token")
                if not token or not check_token(token):
                    return Response("Unauthorized", status_code=401)
        return await call_next(request)


app.add_middleware(TokenAuthMiddleware)
for r in [
    account.router,
    post.router,
    media.router,
    media_part.router,
    annotate.router,
    archiving_session.router,
    search.router,
    login.router,
    permissions.router,
    tags.router
]:
    app.include_router(r, prefix="/api")

if __name__ == "__main__":
    uvicorn.run("browse:app", host="127.0.0.1", port=4444, reload=True)
