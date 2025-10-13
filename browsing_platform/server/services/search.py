from pydantic import BaseModel
from typing import Literal, Optional

import db
from browsing_platform.server.services.archiving_session import ArchiveSession

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
    else:
        print(f"Search mode {query.search_mode} not implemented yet.")
        return []

def search_archive_sessions(query: ISearchQuery) -> list[SearchResult]:
    results = db.execute_query(
        """SELECT * 
           FROM archive_session 
           WHERE
               archived_url LIKE %(search_term)s OR
               metadata LIKE %(search_term)s
           ORDER BY create_date DESC
           LIMIT %(limit)s OFFSET %(offset)s""",
        {
            "search_term": f"%{query.search_term}%",
            "limit": query.page_size,
            "offset": (query.page_number - 1) * query.page_size,
        }
    )
    sessions = [ArchiveSession(**row) for row in results]
    return [SearchResult(
        page="archive",
        id=s.id,
        title=f"Archive Session {s.id}",
        details=f"{s.archived_url}"
    ) for s in sessions]
