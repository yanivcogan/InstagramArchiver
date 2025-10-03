from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

from browsing_platform.server.routes import account, post, media, archiving_session

app = FastAPI()

# Serve the 'archives' directory statically
app.mount("/archives", StaticFiles(directory="archives"), name="archives")
for r in [
    account.router,
    post.router,
    media.router,
    archiving_session.router,
]:
    app.include_router(r, prefix="/api")


if __name__ == "__main__":
    uvicorn.run("browse:app", host="127.0.0.1", port=4444, reload=True)