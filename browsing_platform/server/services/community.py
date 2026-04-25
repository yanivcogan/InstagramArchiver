import json
from typing import Optional

from pydantic import BaseModel

from browsing_platform.server.services.media import get_media_thumbnail_path
from browsing_platform.server.services.search import SearchResultTransform, sign_thumbnail_path
from browsing_platform.server.services.tag import ITagWithType
from browsing_platform.server.services.tag_management import IQuickAccessTypeDropdown, ITagHierarchyEntry
from utils import db

TOP_N = 50
SUGGESTED_RELATION_TYPE = 'suggested'
DEFAULT_TIE_WEIGHTS: dict[str, float] = {
    'follow': 1.0,
    'suggested': 0.0,
    'like': 1.0,
    'comment': 1.0,
    'tag': 1.0,
}


class TieWeights(BaseModel):
    follow: float = DEFAULT_TIE_WEIGHTS['follow']
    suggested: float = DEFAULT_TIE_WEIGHTS['suggested']
    like: float = DEFAULT_TIE_WEIGHTS['like']
    comment: float = DEFAULT_TIE_WEIGHTS['comment']
    tag: float = DEFAULT_TIE_WEIGHTS['tag']


class CommunityCandidatesRequest(BaseModel):
    kernel_ids: list[int]
    excluded_ids: list[int] = []
    weights: TieWeights = TieWeights()


class CandidateAccount(BaseModel):
    id: int
    url_suffix: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    is_verified: Optional[bool] = None
    score: float
    kernel_connections: int
    thumbnails: list[str] = []
    media_count: int = 0


class CommunityCandidatesResponse(BaseModel):
    candidates: list[CandidateAccount]


class TagKernelAccount(BaseModel):
    id: int
    url_suffix: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    thumbnails: list[str] = []
    media_count: int = 0
    applied_tags: list[ITagWithType] = []


class TagKernelResponse(BaseModel):
    accounts: list[TagKernelAccount]
    dropdown: IQuickAccessTypeDropdown


def _parse_is_verified(data) -> Optional[bool]:
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            return None
    if isinstance(data, dict):
        v = data.get('is_verified')
        if isinstance(v, bool):
            return v
    return None


def compute_candidates(
        req: CommunityCandidatesRequest,
        transform: Optional[SearchResultTransform] = None,
) -> CommunityCandidatesResponse:
    if not req.kernel_ids:
        return CommunityCandidatesResponse(candidates=[])

    kernel_ids = req.kernel_ids
    all_excluded = list(set(kernel_ids) | set(req.excluded_ids))

    k_args = {f"k_{i}": kid for i, kid in enumerate(kernel_ids)}
    k_in = ", ".join(f"%(k_{i})s" for i in range(len(kernel_ids)))
    ex_args = {f"ex_{i}": eid for i, eid in enumerate(all_excluded)}
    ex_in = ", ".join(f"%(ex_{i})s" for i in range(len(all_excluded)))

    query_args = {
        **k_args,
        **ex_args,
        "follow_w": req.weights.follow,
        "suggested_w": req.weights.suggested,
        "like_w": req.weights.like,
        "comment_w": req.weights.comment,
        "tag_w": req.weights.tag,
        "top_n": TOP_N,
    }

    # Each tie type is split into two directional sub-selects so MySQL can use
    # the indexed column directly without an OR on two different columns.
    # The two GROUP BY stages (pair_strength then candidate_scores) run entirely
    # in MySQL; only TOP_N rows are returned to Python.
    score_rows = db.execute_query(  # nosec B608 - k_in / ex_in contain only %(key)s placeholders
        f"""
        WITH ties AS (
            -- follow: kernel member is the follower
            SELECT ar.followed_account_id AS candidate_id,
                   ar.follower_account_id AS kernel_id,
                   %(follow_w)s           AS weight
            FROM account_relation ar
            WHERE ar.follower_account_id IN ({k_in})
              AND ar.followed_account_id NOT IN ({ex_in})
              AND (ar.relation_type IS NULL OR ar.relation_type != %(suggested_type)s)

            UNION ALL

            -- follow: kernel member is the followed account
            SELECT ar.follower_account_id AS candidate_id,
                   ar.followed_account_id AS kernel_id,
                   %(follow_w)s           AS weight
            FROM account_relation ar
            WHERE ar.followed_account_id IN ({k_in})
              AND ar.follower_account_id NOT IN ({ex_in})
              AND (ar.relation_type IS NULL OR ar.relation_type != %(suggested_type)s)

            UNION ALL

            -- suggested: kernel member is follower_account_id
            SELECT ar.followed_account_id, ar.follower_account_id, %(suggested_w)s
            FROM account_relation ar
            WHERE ar.follower_account_id IN ({k_in})
              AND ar.followed_account_id NOT IN ({ex_in})
              AND ar.relation_type = %(suggested_type)s

            UNION ALL

            -- suggested: kernel member is followed_account_id
            SELECT ar.follower_account_id, ar.followed_account_id, %(suggested_w)s
            FROM account_relation ar
            WHERE ar.followed_account_id IN ({k_in})
              AND ar.follower_account_id NOT IN ({ex_in})
              AND ar.relation_type = %(suggested_type)s

            UNION ALL

            -- like: kernel member authored the liked post
            SELECT pl.account_id, p.account_id, %(like_w)s
            FROM post_like pl
            JOIN post p ON pl.post_id = p.id
            WHERE p.account_id IN ({k_in})
              AND pl.account_id IS NOT NULL
              AND pl.account_id NOT IN ({ex_in})

            UNION ALL

            -- like: kernel member liked someone else's post
            SELECT p.account_id, pl.account_id, %(like_w)s
            FROM post_like pl
            JOIN post p ON pl.post_id = p.id
            WHERE pl.account_id IN ({k_in})
              AND p.account_id IS NOT NULL
              AND p.account_id NOT IN ({ex_in})

            UNION ALL

            -- comment: kernel member authored the commented post
            SELECT c.account_id, p.account_id, %(comment_w)s
            FROM comment c
            JOIN post p ON c.post_id = p.id
            WHERE p.account_id IN ({k_in})
              AND c.account_id IS NOT NULL
              AND c.account_id NOT IN ({ex_in})

            UNION ALL

            -- comment: kernel member left the comment
            SELECT p.account_id, c.account_id, %(comment_w)s
            FROM comment c
            JOIN post p ON c.post_id = p.id
            WHERE c.account_id IN ({k_in})
              AND p.account_id IS NOT NULL
              AND p.account_id NOT IN ({ex_in})

            UNION ALL

            -- tag: kernel member tagged someone in a post
            SELECT ta.tagged_account_id, p.account_id, %(tag_w)s
            FROM tagged_account ta
            JOIN post p ON ta.post_id = p.id
            WHERE p.account_id IN ({k_in})
              AND ta.tagged_account_id IS NOT NULL
              AND ta.tagged_account_id NOT IN ({ex_in})

            UNION ALL

            -- tag: kernel member tagged someone in media
            SELECT ta.tagged_account_id, m.account_id, %(tag_w)s
            FROM tagged_account ta
            JOIN media m ON ta.media_id = m.id
            WHERE m.account_id IN ({k_in})
              AND ta.tagged_account_id IS NOT NULL
              AND ta.tagged_account_id NOT IN ({ex_in})

            UNION ALL

            -- tag: kernel member was tagged in a post
            SELECT p.account_id, ta.tagged_account_id, %(tag_w)s
            FROM tagged_account ta
            JOIN post p ON ta.post_id = p.id
            WHERE ta.tagged_account_id IN ({k_in})
              AND p.account_id IS NOT NULL
              AND p.account_id NOT IN ({ex_in})

            UNION ALL

            -- tag: kernel member was tagged in media
            SELECT m.account_id, ta.tagged_account_id, %(tag_w)s
            FROM tagged_account ta
            JOIN media m ON ta.media_id = m.id
            WHERE ta.tagged_account_id IN ({k_in})
              AND m.account_id IS NOT NULL
              AND m.account_id NOT IN ({ex_in})
        ),
        pair_strength AS (
            SELECT candidate_id, kernel_id, MAX(weight) AS strength
            FROM ties
            GROUP BY candidate_id, kernel_id
        ),
        candidate_scores AS (
            SELECT candidate_id,
                   SUM(strength)             AS score,
                   COUNT(DISTINCT kernel_id) AS kernel_connections
            FROM pair_strength
            GROUP BY candidate_id
            HAVING score > 0
        )
        SELECT candidate_id, score, kernel_connections
        FROM candidate_scores
        ORDER BY score DESC
        LIMIT %(top_n)s
        """,
        {**query_args, "suggested_type": SUGGESTED_RELATION_TYPE},
        return_type="rows",
    )

    if not score_rows:
        return CommunityCandidatesResponse(candidates=[])

    top_ids = []
    score_map: dict[int, float] = {}
    connections_map: dict[int, int] = {}
    for row in score_rows:
        cid = row["candidate_id"]
        top_ids.append(cid)
        score_map[cid] = row["score"]
        connections_map[cid] = row["kernel_connections"]

    cand_args = {f"c_{i}": cid for i, cid in enumerate(top_ids)}
    cand_in = ", ".join(f"%(c_{i})s" for i in range(len(top_ids)))

    account_rows = db.execute_query(  # nosec B608
        f"SELECT id, url_suffix, display_name, bio, data FROM account WHERE id IN ({cand_in})",
        cand_args,
        return_type="rows",
    )
    account_map = {r["id"]: r for r in account_rows}

    thumb_rows = db.execute_query(  # nosec B608
        f"""SELECT account_id, thumbnail_path, local_url, media_count
            FROM (
                SELECT account_id, thumbnail_path, local_url,
                       COUNT(*) OVER (PARTITION BY account_id) AS media_count,
                       ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY publication_date DESC) AS rn
                FROM media
                WHERE account_id IN ({cand_in})
                  AND local_url IS NOT NULL
            ) ranked
            WHERE rn <= 8""",
        cand_args,
        return_type="rows",
    )

    thumb_map: dict[int, list[str]] = {}
    media_count_map: dict[int, int] = {}
    should_sign = transform is not None and transform.access_token is not None
    for t in thumb_rows:
        aid = t["account_id"]
        media_count_map[aid] = t["media_count"]
        path = get_media_thumbnail_path(t["thumbnail_path"], t["local_url"])
        if path:
            if should_sign:
                path = sign_thumbnail_path(path, transform)
            thumb_map.setdefault(aid, []).append(path)

    candidates = []
    for cid in top_ids:
        acct = account_map.get(cid)
        if not acct:
            continue
        candidates.append(CandidateAccount(
            id=cid,
            url_suffix=acct.get("url_suffix"),
            display_name=acct.get("display_name"),
            bio=acct.get("bio"),
            is_verified=_parse_is_verified(acct.get("data")),
            score=score_map[cid],
            kernel_connections=connections_map[cid],
            thumbnails=thumb_map.get(cid, []),
            media_count=media_count_map.get(cid, 0),
        ))

    return CommunityCandidatesResponse(candidates=candidates)


# ── Tag-based kernel helpers ──────────────────────────────────────────────────

_TAG_COLS = """
    t.id, t.name, t.description, t.tag_type_id,
    tt.name AS tag_type_name,
    tt.description AS tag_type_description,
    tt.notes AS tag_type_notes,
    tt.entity_affinity AS tag_type_entity_affinity
"""


def get_community_tag_dropdown(tag_id: int) -> IQuickAccessTypeDropdown:
    """Return an IQuickAccessTypeDropdown for the tag and all its descendants."""
    tag_rows = db.execute_query(  # nosec B608
        f"""WITH RECURSIVE tag_desc AS (
                SELECT id FROM tag WHERE id = %(tag_id)s
                UNION ALL
                SELECT th.sub_tag_id FROM tag_hierarchy th
                JOIN tag_desc td ON th.super_tag_id = td.id
            )
            SELECT {_TAG_COLS}
            FROM tag_desc td
            JOIN tag t ON t.id = td.id
            LEFT JOIN tag_type tt ON t.tag_type_id = tt.id""",
        {"tag_id": tag_id},
        return_type="rows",
    )
    if not tag_rows:
        return IQuickAccessTypeDropdown(type_id=tag_id, type_name="", tags=[], hierarchy=[])

    tag_id_set = {r["id"] for r in tag_rows}
    root_name = next((r["name"] for r in tag_rows if r["id"] == tag_id), "")

    if len(tag_id_set) > 1:
        h_ids = list(tag_id_set)
        h_args = {f"h_{i}": tid for i, tid in enumerate(h_ids)}
        h_in = ", ".join(f"%(h_{i})s" for i in range(len(h_ids)))
        hierarchy_rows = db.execute_query(  # nosec B608
            f"SELECT super_tag_id, sub_tag_id FROM tag_hierarchy WHERE super_tag_id IN ({h_in}) AND sub_tag_id IN ({h_in})",
            h_args,
            return_type="rows",
        )
    else:
        hierarchy_rows = []

    return IQuickAccessTypeDropdown(
        type_id=tag_id,
        type_name=root_name,
        tags=[ITagWithType(**row) for row in tag_rows],
        hierarchy=[ITagHierarchyEntry(super_tag_id=h["super_tag_id"], sub_tag_id=h["sub_tag_id"]) for h in hierarchy_rows],
    )


def get_tag_kernel_accounts(
        tag_id: int,
        transform: Optional[SearchResultTransform] = None,
) -> TagKernelResponse:
    """Return all accounts tagged with tag_id or any of its descendants, with applied tags."""
    dropdown = get_community_tag_dropdown(tag_id)

    if not dropdown.tags:
        return TagKernelResponse(accounts=[], dropdown=dropdown)

    tag_by_id: dict[int, ITagWithType] = {t.id: t for t in dropdown.tags}
    d_args = {f"d_{i}": tid for i, tid in enumerate(tag_by_id)}
    d_in = ", ".join(f"%(d_{i})s" for i in range(len(tag_by_id)))

    tag_account_rows = db.execute_query(  # nosec B608
        f"SELECT account_id, tag_id FROM account_tag WHERE tag_id IN ({d_in})",
        d_args,
        return_type="rows",
    )
    if not tag_account_rows:
        return TagKernelResponse(accounts=[], dropdown=dropdown)

    applied_tags_map: dict[int, list[ITagWithType]] = {}
    for r in tag_account_rows:
        tag = tag_by_id.get(r["tag_id"])
        if tag:
            applied_tags_map.setdefault(r["account_id"], []).append(tag)

    account_ids = list(applied_tags_map.keys())
    cand_args = {f"c_{i}": aid for i, aid in enumerate(account_ids)}
    cand_in = ", ".join(f"%(c_{i})s" for i in range(len(account_ids)))

    account_rows = db.execute_query(  # nosec B608
        f"SELECT id, url_suffix, display_name, bio FROM account WHERE id IN ({cand_in})",
        cand_args,
        return_type="rows",
    )
    account_map = {r["id"]: r for r in account_rows}

    thumb_rows = db.execute_query(  # nosec B608
        f"""SELECT account_id, thumbnail_path, local_url, media_count
            FROM (
                SELECT account_id, thumbnail_path, local_url,
                       COUNT(*) OVER (PARTITION BY account_id) AS media_count,
                       ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY publication_date DESC) AS rn
                FROM media
                WHERE account_id IN ({cand_in})
                  AND local_url IS NOT NULL
            ) ranked
            WHERE rn <= 8""",
        cand_args,
        return_type="rows",
    )

    thumb_map: dict[int, list[str]] = {}
    media_count_map: dict[int, int] = {}
    should_sign = transform is not None and transform.access_token is not None
    for t in thumb_rows:
        aid = t["account_id"]
        media_count_map[aid] = t["media_count"]
        path = get_media_thumbnail_path(t["thumbnail_path"], t["local_url"])
        if path:
            if should_sign:
                path = sign_thumbnail_path(path, transform)
            thumb_map.setdefault(aid, []).append(path)

    accounts = []
    for aid in account_ids:
        acct = account_map.get(aid)
        if not acct:
            continue
        accounts.append(TagKernelAccount(
            id=aid,
            url_suffix=acct.get("url_suffix"),
            display_name=acct.get("display_name"),
            bio=acct.get("bio"),
            thumbnails=thumb_map.get(aid, []),
            media_count=media_count_map.get(aid, 0),
            applied_tags=applied_tags_map[aid],
        ))

    return TagKernelResponse(accounts=accounts, dropdown=dropdown)
