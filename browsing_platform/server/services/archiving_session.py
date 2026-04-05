import json
import os
from datetime import datetime
from typing import Literal, Optional
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

from pydantic import BaseModel, computed_field, field_validator

from browsing_platform.server.services.file_tokens import generate_file_token
from db_loaders.db_intake import LOCAL_ARCHIVES_DIR_ALIAS
from extractors.entity_types import ExtractedEntitiesNested, reconstruct_url
from utils import db

SERVER_HOST = os.getenv("SERVER_HOST")


class ArchiveSession(BaseModel):
    id: Optional[int] = None
    create_date: Optional[datetime] = None
    update_date: Optional[datetime] = None
    external_id: Optional[str] = None
    archived_url_suffix: Optional[str] = None
    platform: Optional[str] = None
    archive_location: Optional[str] = None

    @computed_field
    @property
    def archived_url(self) -> Optional[str]:
        return reconstruct_url(self.archived_url_suffix, self.platform)
    summary_html: Optional[str] = None
    parse_algorithm_version: Optional[int] = None
    structures: Optional[dict] = None
    metadata: Optional[dict] = None
    attachments: Optional[dict[str, list[str]]] = None
    attachments_redacted: Optional[list[str]] = None
    extract_algorithm_version: Optional[int] = None
    archiving_timestamp: Optional[datetime] = None
    notes: Optional[str] = None
    extraction_error: Optional[str] = None
    source_type: Literal['AA_xlsx', 'local_har', 'local_wacz'] = 'local_har'
    incorporation_status: Optional[Literal['pending', 'parse_failed', 'parsed', 'extract_failed', 'done']] = None

    @field_validator('metadata', 'structures', 'attachments', mode='before')
    def parse_data(cls, v, _):
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                v = None
        return v

    @field_validator('archiving_timestamp', mode='before')
    def parse_timestamp(cls, v, _):
        if isinstance(v, str):
            try:
                v = datetime.fromisoformat(v)
            except ValueError:
                v = None
        return v


class ArchiveSessionWithEntities(BaseModel):
    session: ArchiveSession
    entities: ExtractedEntitiesNested


class ArchivingSessionTransform(BaseModel):
    local_files_root: Optional[str] = None
    access_token: Optional[str] = None
    properties_to_censor: Optional[list[str]] = None
    include_screen_recordings: bool = True
    include_har: bool = True


def get_archiving_session_structures(session_id: int) -> tuple[bool, Optional[dict]]:
    """Returns (True, structures) if the session exists, (False, None) if not found."""
    row = db.execute_query(
        "SELECT structures FROM archive_session WHERE id = %(id)s",
        {"id": session_id},
        return_type="single_row"
    )
    if row is None:
        return False, None
    structures = row["structures"]
    if isinstance(structures, str):
        try:
            structures = json.loads(structures)
        except json.JSONDecodeError:
            structures = None
    return True, structures


def get_archiving_session_by_id(session_id: int) -> Optional[ArchiveSession]:
    session = db.execute_query(
        """SELECT *
           FROM archive_session
           WHERE id = %(id)s""",
        {"id": session_id},
        return_type="single_row"
    )
    if session is None:
        return None
    return ArchiveSession(**session)


def censor_archiving_session(session: ArchiveSession, properties_to_censor: list[str]) -> ArchiveSession:
    session.structures = None
    if not session.metadata:
        return session
    for prop in properties_to_censor:
        if prop in session.metadata:
            session.metadata[prop] = "[CENSORED]"
    return session


def sign_archiving_session(session: ArchiveSession, transform: ArchivingSessionTransform) -> ArchiveSession:
    attachments = session.attachments
    if not attachments:
        return session

    # Redact attachment types the share link doesn't permit, marking them so
    # the client can show an appropriate "no access" placeholder.
    redacted: list[str] = []
    _REDACT_MAP = {
        'screen_recordings': transform.include_screen_recordings,
        'har_archives': transform.include_har,
    }
    for key, allowed in _REDACT_MAP.items():
        if not allowed and attachments.get(key):
            redacted.append(key)
            del attachments[key]
    if redacted:
        session.attachments_redacted = redacted

    for attachment_type in list(attachments.keys()):
        for i in range(len(attachments.get(attachment_type, []))):
            attachment: str = attachments.get(attachment_type)[i]
            local_path = session.archive_location + "/" + attachment
            local_path = local_path.replace(LOCAL_ARCHIVES_DIR_ALIAS, f"{transform.local_files_root}/archives", 1)
            parsed = urlparse(local_path)
            qs = dict(parse_qsl(parsed.query, keep_blank_values=True))
            qs['ft'] = generate_file_token(
                transform.access_token,
                local_path.split(f"{transform.local_files_root}")[-1]
            )
            new_query = urlencode(qs, doseq=True)
            local_signed_url = str(urlunparse(parsed._replace(query=new_query)))
            session.attachments[attachment_type][i] = local_signed_url
    return session
