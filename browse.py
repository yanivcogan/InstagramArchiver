from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

import db
from summarizers.entities_summary_generator import summarize_nested_entities
from extractors.entity_types import ExtractedEntitiesFlattened, Account, Post, Media
from extractors.structures_to_entities import nest_entities
from utils import ROOT_DIR

app = FastAPI()

# Serve the 'archives' directory statically
app.mount("/archives", StaticFiles(directory="archives"), name="archives")


def get_account_by_url(url:str) -> Optional[Account]:
    account = db.execute_query(
        """SELECT * FROM account WHERE url LIKE %(url)s""",
        {"url": url},
        return_type="single_row"
    )
    if account is None:
        return None
    return Account(**account)


def get_posts_by_account(account: Account) -> list[Post]:
    post = db.execute_query(
        """SELECT * FROM post WHERE account_url LIKE %(account_url)s""",
        {"account_url": f"{account.url}%"},
        return_type="rows"
    )
    return [Post(**p) for p in post]


def get_media_by_posts(posts: list[Post]) -> list[Media]:
    if not posts or len(posts) == 0:
        return []
    query_args = {f"post_url_{i}": f"{post.url}" for i, post in enumerate(posts)}
    query_in_clause = ', '.join([f"%(post_url_{i})s" for i in range(len(posts))])
    media = db.execute_query(
        f"""SELECT * FROM media WHERE post_url IN ({query_in_clause})""",
        query_args,
        return_type="rows"
    )
    return [Media(**m) for m in media]


@app.get("/account/{url:path}", response_class=HTMLResponse)
async def account_view(url: str, request: Request):
    # Extract account, posts, and media using db.py helpers
    account = get_account_by_url(url)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    posts = get_posts_by_account(account)
    media = get_media_by_posts(posts)

    # Flatten and nest entities
    flattened_entities = ExtractedEntitiesFlattened(
        accounts=[account],
        posts=posts,
        media=media
    )
    nested_entities = nest_entities(flattened_entities)
    metadata = {}  # Add any metadata you want to pass
    html = summarize_nested_entities(nested_entities, metadata)
    print(ROOT_DIR)
    html = html.replace(ROOT_DIR.replace("\\", "/"), "http://127.0.0.1:4444")
    html = html.replace('src="ytmb', 'src="https://glan-ytbm.fra1.cdn.digitaloceanspaces.com/ytmb')
    html = html.replace('href="ytmb', 'href="https://glan-ytbm.fra1.cdn.digitaloceanspaces.com/ytmb')
    html = html.replace('src="pal', 'src="https://glan.fra1.cdn.digitaloceanspaces.com/pal')
    html = html.replace('href="pal', 'href="https://glan.fra1.cdn.digitaloceanspaces.com/pal')
    return HTMLResponse(content=html)

if __name__ == "__main__":
    uvicorn.run("browse:app", host="127.0.0.1", port=4444, reload=True)