import string
from datetime import datetime
from secrets import choice
from typing import Optional

from pydantic import BaseModel

from browsing_platform.server.services.entities_hierarchy import T_Entities
from browsing_platform.server.services.media import get_media_by_id
from browsing_platform.server.services.media_part import get_media_part_by_id
from browsing_platform.server.services.post import get_post_by_id
from utils import db

_MIN_SHARE_PASSWORD_LEN = 6

SHARE_LINK_LENGTH = 24


class EntityShare(BaseModel):
    entity: T_Entities
    entity_id: int


class EntityShareLink(EntityShare):
    id: Optional[int]
    create_date: Optional[datetime] = None
    update_date: Optional[datetime] = None
    created_by_user_id: int
    valid: bool
    link_suffix: str
    include_screen_recordings: bool = True
    include_har: bool = True
    password_hash: Optional[str] = None
    password_alg: Optional[str] = None
    password_protected: bool = False  # derived field, always safe to expose


def generate_suffix() -> str:
    """Generate a random token string of TOKEN_LENGTH characters."""
    return ''.join(choice(string.ascii_letters + string.digits) for _ in range(SHARE_LINK_LENGTH))


class SharePermissions(BaseModel):
    view: bool = False
    edit: bool = False
    censored_session_properties: Optional[list[str]] = None
    include_screen_recordings: bool = True
    include_har: bool = True
    password_protected: bool = False


class EntitySharePermissions(SharePermissions):
    shared_entity: Optional[EntityShare] = None


class ShareLinkCreationResult(BaseModel):
    success: bool
    link_suffix: Optional[str] = None
    error: Optional[str] = None


class SetPasswordRequest(BaseModel):
    password: Optional[str] = None


_ENTITY_TABLE: dict[str, str] = {
    "account": "account",
    "post": "post",
    "media": "media",
    "media_part": "media_part",
    "archiving_session": "archive_session",
}


def entity_exists(entity: T_Entities, entity_id: int) -> bool:
    """Return True if a row with the given ID exists for the entity type."""
    table = _ENTITY_TABLE.get(entity)
    if not table:
        return False
    row = db.execute_query(
        f"SELECT id FROM `{table}` WHERE id = %(id)s",
        {"id": entity_id},
        return_type="single_row",
    )
    return row is not None


def create_share_link(scope: EntitySharePermissions, user_id: int) -> ShareLinkCreationResult:
    try:
        suffix = generate_suffix()
        db.execute_query(
            '''INSERT INTO entity_share_link
            (created_by_user_id, entity, entity_id, valid, link_suffix,
             include_screen_recordings, include_har)
            VALUES (%(created_by_user_id)s, %(entity)s, %(entity_id)s, TRUE, %(link_suffix)s,
                    %(include_screen_recordings)s, %(include_har)s)'''
            , {
                "created_by_user_id": user_id,
                "entity": scope.shared_entity.entity,
                "entity_id": scope.shared_entity.entity_id,
                "link_suffix": suffix,
                "include_screen_recordings": int(scope.include_screen_recordings),
                "include_har": int(scope.include_har),
            }, "none"
        )
        return ShareLinkCreationResult(
            success=True,
            link_suffix=suffix,
        )
    except Exception as e:
        return ShareLinkCreationResult(
            success=False,
            error=str(e)
        )


def get_existing_share_link(entity: T_Entities, entity_id: int) -> Optional[EntityShareLink]:
    link_share = db.execute_query(
        '''SELECT * FROM entity_share_link
        WHERE entity = %(entity)s AND entity_id = %(entity_id)s
        ORDER BY create_date DESC
        LIMIT 1'''
        , {"entity": entity, "entity_id": entity_id}, "single_row"
    )
    if not link_share or not isinstance(link_share, dict):
        return None
    link = EntityShareLink(**link_share)
    link.password_protected = link.password_hash is not None
    link.password_hash = None  # never expose the hash to callers
    return link


def set_link_password(link_suffix: str, password: Optional[str]):
    if password is None:
        db.execute_query(
            'UPDATE entity_share_link SET password_hash = NULL, password_alg = NULL '
            'WHERE link_suffix = %(link_suffix)s',
            {"link_suffix": link_suffix},
            "none",
        )
    else:
        if len(password) < _MIN_SHARE_PASSWORD_LEN:
            raise ValueError(f"Password must be at least {_MIN_SHARE_PASSWORD_LEN} characters")
        from browsing_platform.server.services.password_authenticator import hash_raw
        h, alg = hash_raw(password)
        db.execute_query(
            'UPDATE entity_share_link SET password_hash = %(h)s, password_alg = %(alg)s '
            'WHERE link_suffix = %(link_suffix)s',
            {"h": h, "alg": alg, "link_suffix": link_suffix},
            "none",
        )


def verify_share_link_password(link_suffix: str, password: str) -> Optional[str]:
    """Verify a password for a share link. Returns a signed token on success, None on failure."""
    row = db.execute_query(
        'SELECT password_hash, valid FROM entity_share_link WHERE link_suffix = %(s)s',
        {"s": link_suffix},
        "single_row",
    )
    if not row or not isinstance(row, dict):
        return None
    if not row.get("valid"):
        return None
    stored_hash = row.get("password_hash")
    if not stored_hash:
        return None  # link has no password — no token needed
    from browsing_platform.server.services.password_authenticator import verify_password
    from browsing_platform.server.services.share_password_tokens import generate_password_token
    result = verify_password(stored_hash, password)
    if result is False:
        return None
    if isinstance(result, str):
        # Hash needs upgrading; persist the new hash
        db.execute_query(
            'UPDATE entity_share_link SET password_hash = %(h)s WHERE link_suffix = %(s)s',
            {"h": result, "s": link_suffix},
            "none",
        )
    return generate_password_token(link_suffix)


def set_link_attachment_access(link_suffix: str, include_screen_recordings: bool, include_har: bool):
    db.execute_query(
        '''UPDATE entity_share_link
           SET include_screen_recordings = %(include_screen_recordings)s,
               include_har = %(include_har)s
           WHERE link_suffix = %(link_suffix)s''',
        {
            "include_screen_recordings": int(include_screen_recordings),
            "include_har": int(include_har),
            "link_suffix": link_suffix,
        },
        "none"
    )


def set_link_validity(link_suffix: str, valid: bool):
    db.execute_query(
        'UPDATE entity_share_link SET valid = %(valid)s WHERE link_suffix = %(link_suffix)s',
        {"valid": valid, "link_suffix": link_suffix},
        "none"
    )


def get_link_permissions(link_suffix: str, password_token: Optional[str] = None, skip_password_check: bool = False) -> EntitySharePermissions:
    try:
        if not link_suffix:
            return EntitySharePermissions(view=False)
        token_check = db.execute_query(
            '''SELECT * FROM entity_share_link
            WHERE link_suffix = %(token)s'''
            , {"token": link_suffix}, "single_row"
        )
        if not token_check or not isinstance(token_check, dict):
            return EntitySharePermissions(view=False)
        share_link = EntityShareLink(**token_check)
        if not share_link.valid:
            return EntitySharePermissions(view=False)
        if share_link.password_hash and not skip_password_check:
            from browsing_platform.server.services.share_password_tokens import validate_password_token
            if not password_token or not validate_password_token(link_suffix, password_token):
                return EntitySharePermissions(view=False, password_protected=True)
        return EntitySharePermissions(
            view=True,
            shared_entity=EntityShare(entity=share_link.entity, entity_id=share_link.entity_id),
            include_screen_recordings=share_link.include_screen_recordings,
            include_har=share_link.include_har,
        )
    except Exception:
        return EntitySharePermissions(view=False)


def check_share_permissions(link_suffix: str, requested_entity: T_Entities, requested_entity_id: int, password_token: Optional[str] = None) -> SharePermissions:
    share_scope = get_link_permissions(link_suffix, password_token)
    share_permissions = SharePermissions(**share_scope.model_dump(exclude={"shared_entity"}))
    shared_entity = share_scope.shared_entity
    if not shared_entity:
        return SharePermissions(view=False)
    if shared_entity.entity == requested_entity and shared_entity.entity_id == requested_entity_id:
        return share_permissions
    if shared_entity.entity == "account":
        if requested_entity == "post":
            post = get_post_by_id(requested_entity_id)
            if post and post.account_id == shared_entity.entity_id:
                return share_permissions
        elif requested_entity == "media":
            media = get_media_by_id(requested_entity_id)
            if media:
                post = get_post_by_id(media.post_id)
                if post and post.account_id == shared_entity.entity_id:
                    return share_permissions
        elif requested_entity == "media_part":
            media_part = get_media_part_by_id(requested_entity_id)
            if media_part and media_part.media_id:
                media = get_media_by_id(media_part.media_id)
                if media:
                    post = get_post_by_id(media.post_id)
                    if post and post.account_id == shared_entity.entity_id:
                        return share_permissions
    if shared_entity.entity == "post":
        if requested_entity == "media":
            media = get_media_by_id(requested_entity_id)
            if media and media.post_id == shared_entity.entity_id:
                return share_permissions
        elif requested_entity == "media_part":
            media_part = get_media_part_by_id(requested_entity_id)
            if media_part and media_part.media_id:
                media = get_media_by_id(media_part.media_id)
                if media and media.post_id == shared_entity.entity_id:
                    return share_permissions
    if shared_entity.entity == "media":
        if requested_entity == "media_part":
            media_part = get_media_part_by_id(requested_entity_id)
            if media_part and media_part.media_id == shared_entity.entity_id:
                return share_permissions
    return SharePermissions(view=False)



def invalidate_suffix(link_suffix: str):
    db.execute_query(
        '''UPDATE entity_share_link SET valid = FALSE WHERE link_suffix = %(link_suffix)s'''
        , {"link_suffix": link_suffix}, "none"
    )
    return True
