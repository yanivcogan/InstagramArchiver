from pydantic import BaseModel
from typing import Literal, Optional

import db
from browsing_platform.server.services.archiving_session import ArchiveSession
from extractors.entity_types import Account, Post

T_Search_Mode = Literal["media", "posts", "accounts", "archive_sessions", "all"]

class ISearchQuery(BaseModel):
    search_term: str
    search_mode: T_Search_Mode
    page_number: int
    page_size: int

class SearchResult(BaseModel):
    page: str
    id: int
    title: str
    details: Optional[str]

def search_base(query: ISearchQuery) -> list[SearchResult]:
    if query.search_mode == "archive_sessions":
        return search_archive_sessions(query)
    elif query.search_mode == "accounts":
        return search_accounts(query)
    elif query.search_mode == "posts":
        return search_posts(query)
    else:
        print(f"Search mode {query.search_mode} not implemented yet.")
        return []

def default_fulltext_query(search_term: str) -> str:
    if "+" in search_term or "-" in search_term or "*" in search_term:
        return search_term
    return " ".join([f'+"{word}' for word in search_term.split() if word])

def search_archive_sessions(query: ISearchQuery) -> list[SearchResult]:
    results = db.execute_query(
        """SELECT * 
           FROM archive_session 
           WHERE
               MATCH (`archived_url`, `archived_url_parts`, `notes`) AGAINST (%(search_term)s IN BOOLEAN MODE)
           ORDER BY archiving_timestamp DESC
           LIMIT %(limit)s OFFSET %(offset)s""",
        {
            "search_term": default_fulltext_query(query.search_term),
            "limit": query.page_size,
            "offset": (query.page_number - 1) * query.page_size,
        }
    )
    sessions = [ArchiveSession(**row) for row in results]
    return [SearchResult(
        page="archive",
        id=s.id,
        title=f"Archive Session {s.id}",
        details=f"{s.archived_url}" + (f" ({s.notes})" if s.notes else "")
    ) for s in sessions]


def search_accounts(query: ISearchQuery) -> list[SearchResult]:
    results = db.execute_query(
        """SELECT * 
           FROM account 
           WHERE
               MATCH(`url`, `url_parts`, `bio`, `display_name`, `notes`) AGAINST (%(search_term)s IN BOOLEAN MODE)
           ORDER BY id DESC
           LIMIT %(limit)s OFFSET %(offset)s""",
        {
            "search_term": default_fulltext_query(query.search_term),
            "limit": query.page_size,
            "offset": (query.page_number - 1) * query.page_size,
        }
    )
    accounts = [Account(**row) for row in results]
    return [SearchResult(
        page="account",
        id=a.id,
        title=a.url + (f" ({a.display_name})" if a.display_name else ""),
        details=a.bio or ""
    ) for a in accounts]


def search_posts(query: ISearchQuery) -> list[SearchResult]:
    results = db.execute_query(
        """SELECT * 
           FROM post 
           WHERE
               MATCH(`url`, `caption`, `notes`) AGAINST (%(search_term)s IN BOOLEAN MODE)
           ORDER BY publication_date DESC
           LIMIT %(limit)s OFFSET %(offset)s""",
        {
            "search_term": default_fulltext_query(query.search_term),
            "limit": query.page_size,
            "offset": (query.page_number - 1) * query.page_size,
        }
    )
    posts = [Post(**row) for row in results]
    return [SearchResult(
        page="post",
        id=p.id,
        title=p.url,
        details=(p.caption[:100] + '...') if p.caption and len(p.caption) > 100 else (p.caption or "")
    ) for p in posts]