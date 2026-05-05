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


def _column_is_not_null(cur, table, column):
    cur.execute(
        "SELECT IS_NULLABLE FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
        (table, column),
    )
    row = cur.fetchone()
    return row is not None and row[0] == 'NO'


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
        print(f"    {table}: renamed index {old_name} → {new_name}", flush=True)


# ---------------------------------------------------------------------------
# Sub-phase A: Schema rename + add platform
# ---------------------------------------------------------------------------

def _row_count(cur, table):
    cur.execute(f"SELECT COUNT(*) FROM `{table}`")
    return cur.fetchone()[0]


def _phase_a(cur):
    """Rename url columns and add platform ENUM. One ALTER per table for efficiency."""
    import time

    # Tables with a single `url` column → url_suffix
    # media_archive also has post_url — handled separately below
    simple_tables_no_extra = ['account', 'post', 'media', 'comment', 'account_archive']

    for tbl in simple_tables_no_extra:
        n = _row_count(cur, tbl)
        print(f"    {tbl}: {n} rows", flush=True)
        if not _column_exists(cur, tbl, 'url_suffix'):
            print(f"    {tbl}: renaming url→url_suffix, adding platform ...", flush=True)
            t0 = time.perf_counter()
            cur.execute(
                f"ALTER TABLE `{tbl}` "
                f"RENAME COLUMN `url` TO `url_suffix`, "
                f"ADD COLUMN `platform` {_PLATFORM_ENUM}"
            )
            print(f"    {tbl}: done ({time.perf_counter()-t0:.1f}s)", flush=True)
        else:
            print(f"    {tbl}: url_suffix already exists, skipping schema", flush=True)

    # archive_session: archived_url → archived_url_suffix
    n = _row_count(cur, 'archive_session')
    print(f"    archive_session: {n} rows", flush=True)
    if not _column_exists(cur, 'archive_session', 'archived_url_suffix'):
        print("    archive_session: renaming archived_url→archived_url_suffix, adding platform ...", flush=True)
        t0 = time.perf_counter()
        cur.execute(
            f"ALTER TABLE `archive_session` "
            f"RENAME COLUMN `archived_url` TO `archived_url_suffix`, "
            f"ADD COLUMN `platform` {_PLATFORM_ENUM}"
        )
        print(f"    archive_session: done ({time.perf_counter()-t0:.1f}s)", flush=True)
    else:
        print("    archive_session: archived_url_suffix already exists, skipping schema", flush=True)

    # media_archive: url → url_suffix, post_url → post_url_suffix
    n = _row_count(cur, 'media_archive')
    print(f"    media_archive: {n} rows", flush=True)
    if not _column_exists(cur, 'media_archive', 'url_suffix'):
        print("    media_archive: renaming url→url_suffix, post_url→post_url_suffix, adding platform ...", flush=True)
        t0 = time.perf_counter()
        cur.execute(
            f"ALTER TABLE `media_archive` "
            f"RENAME COLUMN `url` TO `url_suffix`, "
            f"RENAME COLUMN `post_url` TO `post_url_suffix`, "
            f"ADD COLUMN `platform` {_PLATFORM_ENUM}"
        )
        print(f"    media_archive: done ({time.perf_counter()-t0:.1f}s)", flush=True)
    else:
        print("    media_archive: url_suffix already exists, skipping schema", flush=True)

    # post_archive: url → url_suffix, account_url → account_url_suffix
    n = _row_count(cur, 'post_archive')
    print(f"    post_archive: {n} rows", flush=True)
    if not _column_exists(cur, 'post_archive', 'url_suffix'):
        print("    post_archive: renaming url→url_suffix, account_url→account_url_suffix, adding platform ...", flush=True)
        t0 = time.perf_counter()
        cur.execute(
            f"ALTER TABLE `post_archive` "
            f"RENAME COLUMN `url` TO `url_suffix`, "
            f"RENAME COLUMN `account_url` TO `account_url_suffix`, "
            f"ADD COLUMN `platform` {_PLATFORM_ENUM}"
        )
        print(f"    post_archive: done ({time.perf_counter()-t0:.1f}s)", flush=True)
    else:
        print("    post_archive: url_suffix already exists, skipping schema", flush=True)

    # comment_archive: url, post_url, account_url
    n = _row_count(cur, 'comment_archive')
    print(f"    comment_archive: {n} rows", flush=True)
    if not _column_exists(cur, 'comment_archive', 'url_suffix'):
        print("    comment_archive: renaming url/post_url/account_url → *_suffix, adding platform ...", flush=True)
        t0 = time.perf_counter()
        cur.execute(
            f"ALTER TABLE `comment_archive` "
            f"RENAME COLUMN `url` TO `url_suffix`, "
            f"RENAME COLUMN `post_url` TO `post_url_suffix`, "
            f"RENAME COLUMN `account_url` TO `account_url_suffix`, "
            f"ADD COLUMN `platform` {_PLATFORM_ENUM}"
        )
        print(f"    comment_archive: done ({time.perf_counter()-t0:.1f}s)", flush=True)
    else:
        print("    comment_archive: url_suffix already exists, skipping schema", flush=True)

    # account_relation_archive: followed_account_url, follower_account_url
    n = _row_count(cur, 'account_relation_archive')
    print(f"    account_relation_archive: {n} rows", flush=True)
    if not _column_exists(cur, 'account_relation_archive', 'followed_account_url_suffix'):
        print("    account_relation_archive: renaming url columns → *_suffix, adding platform ...", flush=True)
        t0 = time.perf_counter()
        cur.execute(
            f"ALTER TABLE `account_relation_archive` "
            f"RENAME COLUMN `followed_account_url` TO `followed_account_url_suffix`, "
            f"RENAME COLUMN `follower_account_url` TO `follower_account_url_suffix`, "
            f"ADD COLUMN `platform` {_PLATFORM_ENUM}"
        )
        print(f"    account_relation_archive: done ({time.perf_counter()-t0:.1f}s)", flush=True)
    else:
        print("    account_relation_archive: followed_account_url_suffix already exists, skipping schema", flush=True)

    # post_like_archive: post_url, account_url
    n = _row_count(cur, 'post_like_archive')
    print(f"    post_like_archive: {n} rows", flush=True)
    if not _column_exists(cur, 'post_like_archive', 'post_url_suffix'):
        print("    post_like_archive: renaming post_url/account_url → *_suffix, adding platform ...", flush=True)
        t0 = time.perf_counter()
        cur.execute(
            f"ALTER TABLE `post_like_archive` "
            f"RENAME COLUMN `post_url` TO `post_url_suffix`, "
            f"RENAME COLUMN `account_url` TO `account_url_suffix`, "
            f"ADD COLUMN `platform` {_PLATFORM_ENUM}"
        )
        print(f"    post_like_archive: done ({time.perf_counter()-t0:.1f}s)", flush=True)
    else:
        print("    post_like_archive: post_url_suffix already exists, skipping schema", flush=True)

    # tagged_account_archive: tagged_account_url, context_post_url, context_media_url
    n = _row_count(cur, 'tagged_account_archive')
    print(f"    tagged_account_archive: {n} rows", flush=True)
    if not _column_exists(cur, 'tagged_account_archive', 'tagged_account_url_suffix'):
        print("    tagged_account_archive: renaming url columns → *_suffix, adding platform ...", flush=True)
        t0 = time.perf_counter()
        cur.execute(
            f"ALTER TABLE `tagged_account_archive` "
            f"RENAME COLUMN `tagged_account_url` TO `tagged_account_url_suffix`, "
            f"RENAME COLUMN `context_post_url` TO `context_post_url_suffix`, "
            f"RENAME COLUMN `context_media_url` TO `context_media_url_suffix`, "
            f"ADD COLUMN `platform` {_PLATFORM_ENUM}"
        )
        print(f"    tagged_account_archive: done ({time.perf_counter()-t0:.1f}s)", flush=True)
    else:
        print("    tagged_account_archive: tagged_account_url_suffix already exists, skipping schema", flush=True)

    # Make url_suffix nullable on tables where the original url column was NOT NULL.
    # The RENAME COLUMN above preserves NOT NULL, but url_suffix must accept NULL
    # for entities that are constructed from partial data (e.g. account referenced
    # only by id_on_platform, media without a captured CDN URL).
    nullable_cols = [
        ('account',         'url_suffix', 'VARCHAR(200)'),
        ('account_archive', 'url_suffix', 'VARCHAR(200)'),
        ('media',           'url_suffix', 'VARCHAR(250)'),
        ('media_archive',   'url_suffix', 'VARCHAR(250)'),
    ]
    print("    Checking nullable constraints ...", flush=True)
    for tbl, col, col_type in nullable_cols:
        if _column_is_not_null(cur, tbl, col):
            print(f"    {tbl}.{col}: making nullable ...", flush=True)
            t0 = time.perf_counter()
            cur.execute(f"ALTER TABLE `{tbl}` MODIFY COLUMN `{col}` {col_type} NULL")
            print(f"    {tbl}.{col}: done ({time.perf_counter()-t0:.1f}s)", flush=True)
        else:
            print(f"    {tbl}.{col}: already nullable, skipping", flush=True)


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


_PHASE_B_BATCH_SIZE = 10_000


def _batched_update(cur, cnx, tbl, sets, guard, label):
    """Run UPDATE ... WHERE guard LIMIT batch in a loop, committing each batch."""
    import time
    t0 = time.perf_counter()
    total = 0
    batch = 0
    while True:
        cur.execute(
            f"UPDATE `{tbl}` SET {sets} WHERE {guard} LIMIT {_PHASE_B_BATCH_SIZE}"
        )
        n = cur.rowcount
        if n == 0:
            break
        cnx.commit()
        total += n
        batch += 1
        print(f"    {tbl} {label}: batch {batch}, {n} rows ({total} total, {time.perf_counter()-t0:.1f}s)", flush=True)
    print(f"    {tbl} {label}: done — {total} row(s) in {batch} batch(es) ({time.perf_counter()-t0:.1f}s)", flush=True)


def _phase_b(cur, cnx):
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
        guard = ' OR '.join(f"`{c}` LIKE '{_INSTAGRAM_PAGE_PFX}%'" for c in cols)
        _batched_update(cur, cnx, tbl, sets, guard, "strip page prefix")

    # --- CDN media URL columns ---
    _batched_update(
        cur, cnx, 'media',
        f"`url_suffix` = {_strip_cdn('url_suffix')}, `platform` = 'instagram'",
        f"`url_suffix` LIKE '{_INSTAGRAM_CDN_PFX}%'",
        "strip CDN prefix",
    )

    _batched_update(
        cur, cnx, 'media_archive',
        f"`url_suffix` = {_strip_cdn('url_suffix')}, "
        f"`post_url_suffix` = {_strip_page('post_url_suffix')}, "
        f"`platform` = 'instagram'",
        f"`url_suffix` LIKE '{_INSTAGRAM_CDN_PFX}%' OR `post_url_suffix` LIKE '{_INSTAGRAM_PAGE_PFX}%'",
        "strip CDN+page prefixes",
    )

    _batched_update(
        cur, cnx, 'tagged_account_archive',
        f"`context_media_url_suffix` = {_strip_cdn('context_media_url_suffix')}",
        f"`context_media_url_suffix` LIKE '{_INSTAGRAM_CDN_PFX}%'",
        "strip CDN prefix from context_media_url_suffix",
    )


# ---------------------------------------------------------------------------
# Sub-phase C: Rename indexes to match new column names
# ---------------------------------------------------------------------------

def _phase_c(cur):
    print("    Phase C: renaming indexes ...", flush=True)
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

    print("    Phase D: recomputing url_parts ...", flush=True)
    cur.execute(
        f"UPDATE `account` SET `url_parts` = {parts_expr('url_suffix')} WHERE `url_suffix` IS NOT NULL"
    )
    print(f"    account.url_parts recomputed for {cur.rowcount} row(s)", flush=True)

    print("    Updating archive_session.archived_url_parts ...", flush=True)
    cur.execute(
        f"UPDATE `archive_session` SET `archived_url_parts` = {parts_expr('archived_url_suffix')} "
        f"WHERE `archived_url_suffix` IS NOT NULL"
    )
    print(f"    archive_session.archived_url_parts recomputed for {cur.rowcount} row(s)", flush=True)


# ---------------------------------------------------------------------------
# Sub-phase E: Rewrite account.identifiers entries
# ---------------------------------------------------------------------------

_PAGE_PFX_RE = re.compile(r'^url_https://www\.instagram\.com/(.+)$')
_PHASE_E_BATCH_SIZE = 1000


def _phase_e(cur, cnx):
    print("    Phase E: scanning account.identifiers rows ...", flush=True)
    updated = 0
    offset = 0
    batch_num = 0
    while True:
        cur.execute(
            "SELECT id, identifiers FROM account WHERE identifiers IS NOT NULL "
            "ORDER BY id LIMIT %s OFFSET %s",
            (_PHASE_E_BATCH_SIZE, offset),
        )
        rows = cur.fetchall()
        if not rows:
            break

        batch_num += 1
        batch_updated = 0
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
                batch_updated += 1

        if batch_updated > 0:
            cnx.commit()

        updated += batch_updated
        print(f"    Phase E batch {batch_num}: processed {len(rows)} rows, updated {batch_updated}", flush=True)
        offset += _PHASE_E_BATCH_SIZE

    print(f"    account.identifiers rewritten for {updated} row(s)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(cnx):
    import time
    cur = cnx.cursor()
    t_total = time.perf_counter()
    try:
        t0 = time.perf_counter()
        print("  Phase A: schema rename + platform column", flush=True)
        _phase_a(cur)
        cnx.commit()
        print(f"  Phase A complete ({time.perf_counter()-t0:.1f}s)", flush=True)

        t0 = time.perf_counter()
        print("  Phase B: strip URL prefixes, set platform = instagram", flush=True)
        _phase_b(cur, cnx)
        print(f"  Phase B complete ({time.perf_counter()-t0:.1f}s)", flush=True)

        t0 = time.perf_counter()
        print("  Phase C: rename indexes", flush=True)
        _phase_c(cur)
        cnx.commit()
        print(f"  Phase C complete ({time.perf_counter()-t0:.1f}s)", flush=True)

        t0 = time.perf_counter()
        print("  Phase D: recompute url_parts", flush=True)
        _phase_d(cur)
        cnx.commit()
        print(f"  Phase D complete ({time.perf_counter()-t0:.1f}s)", flush=True)

        t0 = time.perf_counter()
        print("  Phase E: rewrite account.identifiers", flush=True)
        _phase_e(cur, cnx)
        print(f"  Phase E complete ({time.perf_counter()-t0:.1f}s)", flush=True)

        print(f"  V019 total elapsed: {time.perf_counter()-t_total:.1f}s", flush=True)
    finally:
        cur.close()
