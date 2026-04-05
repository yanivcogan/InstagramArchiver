"""
V019 — URL suffix + platform columns

Renames all URL columns (url → url_suffix, archived_url → archived_url_suffix, etc.)
and adds a platform ENUM column to every affected table.  Only the suffix portion of the
URL is stored after migration; the full URL is reconstructed in the application layer.

Sub-phases:
  A. Schema rename + add platform ENUM
  B. Data migration: strip prefixes, set platform = 'instagram'
  C. Rename indexes to match the new column names
  D. Recompute url_parts / archived_url_parts (remove stale prefix tokens)
  E. Rewrite account.identifiers entries of the form url_<full-url> → url_<suffix>
"""

import json
import re

_PLATFORM_ENUM = "ENUM('instagram','facebook','telegram','youtube','twitter','threads') NULL"
_INSTAGRAM_PAGE_PFX = 'https://www.instagram.com/'   # 26 chars → SUBSTRING(col, 27)
_INSTAGRAM_CDN_PFX  = 'https://scontent.cdninstagram.com/v/'  # 36 chars → SUBSTRING(col, 37)


def _column_exists(cur, table, column):
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
        (table, column),
    )
    return cur.fetchone()[0] > 0


def _index_exists(cur, table, index_name):
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.statistics "
        "WHERE table_schema = DATABASE() AND table_name = %s AND index_name = %s",
        (table, index_name),
    )
    return cur.fetchone()[0] > 0


def _rename_index_if_exists(cur, table, old_name, new_name):
    if _index_exists(cur, table, old_name) and not _index_exists(cur, table, new_name):
        cur.execute(f"ALTER TABLE `{table}` RENAME INDEX `{old_name}` TO `{new_name}`")
        print(f"    {table}: renamed index {old_name} → {new_name}")


# ---------------------------------------------------------------------------
# Sub-phase A: Schema rename + add platform
# ---------------------------------------------------------------------------

def _phase_a(cur):
    """Rename url columns and add platform ENUM. One ALTER per table for efficiency."""

    # Tables with a single `url` column → url_suffix
    simple_tables = ['account', 'post', 'media', 'comment',
                     'account_archive', 'media_archive']
    # media_archive also has post_url — handled separately below
    simple_tables_no_extra = ['account', 'post', 'media', 'comment', 'account_archive']

    for tbl in simple_tables_no_extra:
        if not _column_exists(cur, tbl, 'url_suffix'):
            cur.execute(
                f"ALTER TABLE `{tbl}` "
                f"RENAME COLUMN `url` TO `url_suffix`, "
                f"ADD COLUMN `platform` {_PLATFORM_ENUM}"
            )
            print(f"    {tbl}: url→url_suffix + platform added")
        else:
            print(f"    {tbl}: already migrated, skipping schema")

    # archive_session: archived_url → archived_url_suffix
    if not _column_exists(cur, 'archive_session', 'archived_url_suffix'):
        cur.execute(
            f"ALTER TABLE `archive_session` "
            f"RENAME COLUMN `archived_url` TO `archived_url_suffix`, "
            f"ADD COLUMN `platform` {_PLATFORM_ENUM}"
        )
        print("    archive_session: archived_url→archived_url_suffix + platform added")
    else:
        print("    archive_session: already migrated, skipping schema")

    # media_archive: url → url_suffix, post_url → post_url_suffix
    if not _column_exists(cur, 'media_archive', 'url_suffix'):
        cur.execute(
            f"ALTER TABLE `media_archive` "
            f"RENAME COLUMN `url` TO `url_suffix`, "
            f"RENAME COLUMN `post_url` TO `post_url_suffix`, "
            f"ADD COLUMN `platform` {_PLATFORM_ENUM}"
        )
        print("    media_archive: url→url_suffix, post_url→post_url_suffix + platform")
    else:
        print("    media_archive: already migrated, skipping schema")

    # post_archive: url → url_suffix, account_url → account_url_suffix
    if not _column_exists(cur, 'post_archive', 'url_suffix'):
        cur.execute(
            f"ALTER TABLE `post_archive` "
            f"RENAME COLUMN `url` TO `url_suffix`, "
            f"RENAME COLUMN `account_url` TO `account_url_suffix`, "
            f"ADD COLUMN `platform` {_PLATFORM_ENUM}"
        )
        print("    post_archive: url→url_suffix, account_url→account_url_suffix + platform")
    else:
        print("    post_archive: already migrated, skipping schema")

    # comment_archive: url, post_url, account_url
    if not _column_exists(cur, 'comment_archive', 'url_suffix'):
        cur.execute(
            f"ALTER TABLE `comment_archive` "
            f"RENAME COLUMN `url` TO `url_suffix`, "
            f"RENAME COLUMN `post_url` TO `post_url_suffix`, "
            f"RENAME COLUMN `account_url` TO `account_url_suffix`, "
            f"ADD COLUMN `platform` {_PLATFORM_ENUM}"
        )
        print("    comment_archive: url/post_url/account_url → *_suffix + platform")
    else:
        print("    comment_archive: already migrated, skipping schema")

    # account_relation_archive: followed_account_url, follower_account_url
    if not _column_exists(cur, 'account_relation_archive', 'followed_account_url_suffix'):
        cur.execute(
            f"ALTER TABLE `account_relation_archive` "
            f"RENAME COLUMN `followed_account_url` TO `followed_account_url_suffix`, "
            f"RENAME COLUMN `follower_account_url` TO `follower_account_url_suffix`, "
            f"ADD COLUMN `platform` {_PLATFORM_ENUM}"
        )
        print("    account_relation_archive: url columns → *_suffix + platform")
    else:
        print("    account_relation_archive: already migrated, skipping schema")

    # post_like_archive: post_url, account_url
    if not _column_exists(cur, 'post_like_archive', 'post_url_suffix'):
        cur.execute(
            f"ALTER TABLE `post_like_archive` "
            f"RENAME COLUMN `post_url` TO `post_url_suffix`, "
            f"RENAME COLUMN `account_url` TO `account_url_suffix`, "
            f"ADD COLUMN `platform` {_PLATFORM_ENUM}"
        )
        print("    post_like_archive: post_url/account_url → *_suffix + platform")
    else:
        print("    post_like_archive: already migrated, skipping schema")

    # tagged_account_archive: tagged_account_url, context_post_url, context_media_url
    if not _column_exists(cur, 'tagged_account_archive', 'tagged_account_url_suffix'):
        cur.execute(
            f"ALTER TABLE `tagged_account_archive` "
            f"RENAME COLUMN `tagged_account_url` TO `tagged_account_url_suffix`, "
            f"RENAME COLUMN `context_post_url` TO `context_post_url_suffix`, "
            f"RENAME COLUMN `context_media_url` TO `context_media_url_suffix`, "
            f"ADD COLUMN `platform` {_PLATFORM_ENUM}"
        )
        print("    tagged_account_archive: url columns → *_suffix + platform")
    else:
        print("    tagged_account_archive: already migrated, skipping schema")


# ---------------------------------------------------------------------------
# Sub-phase B: Data migration — strip prefixes, set platform = 'instagram'
# ---------------------------------------------------------------------------

_PAGE_PFX_LEN  = len(_INSTAGRAM_PAGE_PFX)   # 26
_CDN_PFX_LEN   = len(_INSTAGRAM_CDN_PFX)    # 36


def _strip_page(col):
    """SQL expression: strip Instagram page prefix if present (idempotent)."""
    return (f"IF(`{col}` LIKE '{_INSTAGRAM_PAGE_PFX}%', "
            f"SUBSTRING(`{col}`, {_PAGE_PFX_LEN + 1}), `{col}`)")


def _strip_cdn(col):
    """SQL expression: strip CDN prefix if present (idempotent)."""
    return (f"IF(`{col}` LIKE '{_INSTAGRAM_CDN_PFX}%', "
            f"SUBSTRING(`{col}`, {_CDN_PFX_LEN + 1}), `{col}`)")


def _phase_b(cur):
    # --- Instagram page URL columns ---
    page_url_tables = [
        ('account',          ['url_suffix']),
        ('post',             ['url_suffix']),
        ('comment',          ['url_suffix']),
        ('archive_session',  ['archived_url_suffix']),
        ('account_archive',  ['url_suffix']),
        ('post_archive',     ['url_suffix', 'account_url_suffix']),
        ('comment_archive',  ['url_suffix', 'post_url_suffix', 'account_url_suffix']),
        ('account_relation_archive', ['followed_account_url_suffix', 'follower_account_url_suffix']),
        ('post_like_archive',        ['post_url_suffix', 'account_url_suffix']),
        ('tagged_account_archive',   ['tagged_account_url_suffix', 'context_post_url_suffix']),
    ]
    for tbl, cols in page_url_tables:
        sets = ', '.join(f"`{c}` = {_strip_page(c)}" for c in cols)
        sets += ", `platform` = 'instagram'"
        # guard: only rows where at least one col still has the prefix
        guard = ' OR '.join(f"`{c}` LIKE '{_INSTAGRAM_PAGE_PFX}%'" for c in cols)
        cur.execute(f"UPDATE `{tbl}` SET {sets} WHERE {guard}")
        affected = cur.rowcount
        print(f"    {tbl}: stripped page prefix from {affected} row(s)")

    # --- CDN media URL columns ---
    cur.execute(
        f"UPDATE `media` SET "
        f"`url_suffix` = {_strip_cdn('url_suffix')}, "
        f"`platform` = 'instagram' "
        f"WHERE `url_suffix` LIKE '{_INSTAGRAM_CDN_PFX}%'"
    )
    print(f"    media: stripped CDN prefix from {cur.rowcount} row(s)")

    cur.execute(
        f"UPDATE `media_archive` SET "
        f"`url_suffix` = {_strip_cdn('url_suffix')}, "
        f"`post_url_suffix` = {_strip_page('post_url_suffix')}, "
        f"`platform` = 'instagram' "
        f"WHERE `url_suffix` LIKE '{_INSTAGRAM_CDN_PFX}%' "
        f"   OR `post_url_suffix` LIKE '{_INSTAGRAM_PAGE_PFX}%'"
    )
    print(f"    media_archive: stripped prefixes from {cur.rowcount} row(s)")

    cur.execute(
        f"UPDATE `tagged_account_archive` SET "
        f"`context_media_url_suffix` = {_strip_cdn('context_media_url_suffix')} "
        f"WHERE `context_media_url_suffix` LIKE '{_INSTAGRAM_CDN_PFX}%'"
    )
    print(f"    tagged_account_archive context_media: stripped CDN from {cur.rowcount} row(s)")


# ---------------------------------------------------------------------------
# Sub-phase C: Rename indexes to match new column names
# ---------------------------------------------------------------------------

def _phase_c(cur):
    renames = [
        ('account',                    'account_url_index',                                  'account_url_suffix_index'),
        ('account_archive',            'account_archive_url_index',                          'account_archive_url_suffix_index'),
        ('account_relation_archive',   'account_relation_archive_followed_account_url_index','account_relation_archive_followed_account_url_suffix_index'),
        ('account_relation_archive',   'account_relation_archive_follower_account_url_index','account_relation_archive_follower_account_url_suffix_index'),
        ('archive_session',            'archive_session_archived_url_index',                 'archive_session_archived_url_suffix_index'),
        ('comment',                    'comment_url_index',                                  'comment_url_suffix_index'),
        ('media',                      'media_url_index',                                    'media_url_suffix_index'),
        ('media_archive',              'media_archive_url_index',                            'media_archive_url_suffix_index'),
        ('media_archive',              'media_archive_post_url_index',                       'media_archive_post_url_suffix_index'),
        ('post',                       'post_url_index',                                     'post_url_suffix_index'),
        ('post_archive',               'post_archive_url_index',                             'post_archive_url_suffix_index'),
        ('post_archive',               'post_archive_account_url_index',                     'post_archive_account_url_suffix_index'),
    ]
    for tbl, old, new in renames:
        _rename_index_if_exists(cur, tbl, old, new)


# ---------------------------------------------------------------------------
# Sub-phase D: Recompute url_parts / archived_url_parts
# ---------------------------------------------------------------------------

def _phase_d(cur):
    def parts_expr(col):
        return (f"REPLACE(REPLACE(REPLACE(REPLACE(`{col}`, '/', ' '), '.', ' '), '?', ' '), '&', ' ')")

    cur.execute(
        f"UPDATE `account` SET `url_parts` = {parts_expr('url_suffix')} WHERE `url_suffix` IS NOT NULL"
    )
    print(f"    account.url_parts recomputed for {cur.rowcount} row(s)")

    cur.execute(
        f"UPDATE `archive_session` SET `archived_url_parts` = {parts_expr('archived_url_suffix')} "
        f"WHERE `archived_url_suffix` IS NOT NULL"
    )
    print(f"    archive_session.archived_url_parts recomputed for {cur.rowcount} row(s)")


# ---------------------------------------------------------------------------
# Sub-phase E: Rewrite account.identifiers entries
# ---------------------------------------------------------------------------

_PAGE_PFX_RE = re.compile(r'^url_https://www\.instagram\.com/(.+)$')


def _phase_e(cur, cnx):
    cur.execute("SELECT id, identifiers FROM account WHERE identifiers IS NOT NULL")
    rows = cur.fetchall()
    updated = 0
    for row in rows:
        acc_id, identifiers_raw = row
        if not identifiers_raw:
            continue
        try:
            identifiers = json.loads(identifiers_raw) if isinstance(identifiers_raw, str) else identifiers_raw
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(identifiers, list):
            continue
        new_ids = []
        changed = False
        for entry in identifiers:
            if not isinstance(entry, str):
                new_ids.append(entry)
                continue
            m = _PAGE_PFX_RE.match(entry)
            if m:
                new_ids.append(f"url_{m.group(1)}")
                changed = True
            else:
                new_ids.append(entry)
        if changed:
            cur.execute(
                "UPDATE account SET identifiers = %s WHERE id = %s",
                (json.dumps(new_ids), acc_id)
            )
            updated += 1
    if updated:
        cnx.commit()
    print(f"    account.identifiers rewritten for {updated} row(s)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(cnx):
    cur = cnx.cursor()
    try:
        print("  Phase A: schema rename + platform column")
        _phase_a(cur)
        cnx.commit()

        print("  Phase B: strip URL prefixes, set platform = instagram")
        _phase_b(cur)
        cnx.commit()

        print("  Phase C: rename indexes")
        _phase_c(cur)
        cnx.commit()

        print("  Phase D: recompute url_parts")
        _phase_d(cur)
        cnx.commit()

        print("  Phase E: rewrite account.identifiers")
        _phase_e(cur, cnx)

    finally:
        cur.close()
