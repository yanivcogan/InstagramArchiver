content = open('db_loaders/db_intake.py', encoding='utf-8').read()

replacements = [
    # batch_get_canonicals_url_and_id
    ("    urls = list({e.url for e in entities if getattr(e, 'url', None)})",
     "    urls = list({e.url_suffix for e in entities if getattr(e, 'url_suffix', None)})"),
    ('        rows.extend(db.execute_query(f"SELECT * FROM `{table}` WHERE url IN ({ph})", urls, return_type="rows") or [])',
     '        rows.extend(db.execute_query(f"SELECT * FROM `{table}` WHERE url_suffix IN ({ph})", urls, return_type="rows") or [])'),
    ("    by_url = {c.url: c for c in canonicals if getattr(c, 'url', None)}",
     "    by_url = {c.url_suffix: c for c in canonicals if getattr(c, 'url_suffix', None)}"),
    ("    return [by_url.get(getattr(e, 'url', None)) or by_id.get(getattr(e, 'id_on_platform', None))",
     "    return [by_url.get(getattr(e, 'url_suffix', None)) or by_id.get(getattr(e, 'id_on_platform', None))"),
    # batch_resolve_account_fks_by_url_and_id
    ('        rows = db.execute_query(f"SELECT id, url FROM account WHERE url IN ({ph})", urls, return_type="rows") or []\n        by_url = {r[\'url\']: r[\'id\'] for r in rows}',
     '        rows = db.execute_query(f"SELECT id, url_suffix FROM account WHERE url_suffix IN ({ph})", urls, return_type="rows") or []\n        by_url = {r[\'url_suffix\']: r[\'id\'] for r in rows}'),
    # batch_resolve_post_fks
    ('        rows = db.execute_query(f"SELECT id, url FROM post WHERE url IN ({ph})", urls, return_type="rows") or []\n        by_url = {r[\'url\']: r[\'id\'] for r in rows}',
     '        rows = db.execute_query(f"SELECT id, url_suffix FROM post WHERE url_suffix IN ({ph})", urls, return_type="rows") or []\n        by_url = {r[\'url_suffix\']: r[\'id\'] for r in rows}'),
    # batch_store_new_accounts
    ("    columns = ['url', 'id_on_platform', 'identifiers', 'display_name', 'bio', 'data']",
     "    columns = ['url_suffix', 'platform', 'id_on_platform', 'identifiers', 'display_name', 'bio', 'data']"),
    ('        if a.url:\n            identifiers.append(f"url_{a.url}")',
     '        if a.url_suffix:\n            identifiers.append(f"url_{a.url_suffix}")'),
    ("        rows.append([a.url, a.id_on_platform, json.dumps(identifiers), a.display_name, a.bio,",
     "        rows.append([a.url_suffix, a.platform, a.id_on_platform, json.dumps(identifiers), a.display_name, a.bio,"),
    # batch_store_new_account_archives
    ("    columns = ['url', 'id_on_platform', 'display_name', 'bio', 'data', 'archive_session_id', 'canonical_id']",
     "    columns = ['url_suffix', 'platform', 'id_on_platform', 'display_name', 'bio', 'data', 'archive_session_id', 'canonical_id']"),
    ("    rows = [[a.url, a.id_on_platform, a.display_name, a.bio,",
     "    rows = [[a.url_suffix, a.platform, a.id_on_platform, a.display_name, a.bio,"),
    # batch_store_new_posts
    ("    batch_resolve_account_fks_by_url_and_id(new_posts, 'account_url', 'account_id_on_platform', 'account_id')",
     "    batch_resolve_account_fks_by_url_and_id(new_posts, 'account_url_suffix', 'account_id_on_platform', 'account_id')"),
    ('                             f"(url={p.account_url!r}, id_on_platform={p.account_id_on_platform!r})")',
     '                             f"(url={p.account_url_suffix!r}, id_on_platform={p.account_id_on_platform!r})")'),
    ("    columns = ['url', 'id_on_platform', 'account_id', 'publication_date', 'caption', 'data']",
     "    columns = ['url_suffix', 'platform', 'id_on_platform', 'account_id', 'publication_date', 'caption', 'data']"),
    ("    rows = [[p.url, p.id_on_platform, p.account_id,",
     "    rows = [[p.url_suffix, p.platform, p.id_on_platform, p.account_id,"),
    # batch_store_new_post_archives
    ("    columns = ['url', 'id_on_platform', 'publication_date', 'caption', 'data',\n               'archive_session_id', 'canonical_id', 'account_url', 'account_id_on_platform']",
     "    columns = ['url_suffix', 'platform', 'id_on_platform', 'publication_date', 'caption', 'data',\n               'archive_session_id', 'canonical_id', 'account_url_suffix', 'account_id_on_platform']"),
    ("    rows = [[p.url, p.id_on_platform,",
     "    rows = [[p.url_suffix, p.platform, p.id_on_platform,"),
    ("             p.publication_date.isoformat() if p.publication_date else None,\n             p.caption, json.dumps(p.data) if p.data else None,\n             archive_session_id, cid, p.account_url, p.account_id_on_platform]",
     "             p.publication_date.isoformat() if p.publication_date else None,\n             p.caption, json.dumps(p.data) if p.data else None,\n             archive_session_id, cid, p.account_url_suffix, p.account_id_on_platform]"),
    # batch_store_new_media
    ("    batch_resolve_post_fks(new_media, 'post_url', 'post_id_on_platform', 'post_id')",
     "    batch_resolve_post_fks(new_media, 'post_url_suffix', 'post_id_on_platform', 'post_id')"),
    ('                             f"(url={m.post_url!r}, id_on_platform={m.post_id_on_platform!r})")',
     '                             f"(url={m.post_url_suffix!r}, id_on_platform={m.post_id_on_platform!r})")'),
    ("    columns = ['url', 'id_on_platform', 'post_id', 'local_url', 'media_type', 'data', 'thumbnail_status']",
     "    columns = ['url_suffix', 'platform', 'id_on_platform', 'post_id', 'local_url', 'media_type', 'data', 'thumbnail_status']"),
    ("    rows = [[m.url, m.id_on_platform, m.post_id, m.local_url, m.media_type,",
     "    rows = [[m.url_suffix, m.platform, m.id_on_platform, m.post_id, m.local_url, m.media_type,"),
    # batch_store_new_media_archives
    ("    columns = ['url', 'id_on_platform', 'local_url', 'media_type', 'data',\n               'archive_session_id', 'canonical_id', 'post_url', 'post_id_on_platform']",
     "    columns = ['url_suffix', 'platform', 'id_on_platform', 'local_url', 'media_type', 'data',\n               'archive_session_id', 'canonical_id', 'post_url_suffix', 'post_id_on_platform']"),
    ("    rows = [[m.url, m.id_on_platform, m.local_url, m.media_type,\n             json.dumps(m.data) if m.data else None,\n             archive_session_id, cid, m.post_url, m.post_id_on_platform]",
     "    rows = [[m.url_suffix, m.platform, m.id_on_platform, m.local_url, m.media_type,\n             json.dumps(m.data) if m.data else None,\n             archive_session_id, cid, m.post_url_suffix, m.post_id_on_platform]"),
    # batch_store_new_comments
    ("    batch_resolve_post_fks(new_comments, 'post_url', 'post_id_on_platform', 'post_id')",
     "    batch_resolve_post_fks(new_comments, 'post_url_suffix', 'post_id_on_platform', 'post_id')"),
    ('                             f"(url={c.post_url!r}, id_on_platform={c.post_id_on_platform!r})")',
     '                             f"(url={c.post_url_suffix!r}, id_on_platform={c.post_id_on_platform!r})")'),
    ("    batch_resolve_account_fks_by_url_and_id(new_comments, 'account_url', 'account_id_on_platform', 'account_id')",
     "    batch_resolve_account_fks_by_url_and_id(new_comments, 'account_url_suffix', 'account_id_on_platform', 'account_id')"),
    ("    columns = ['id_on_platform', 'url', 'post_id', 'account_id', 'parent_comment_id_on_platform',\n               'text', 'publication_date', 'data']",
     "    columns = ['id_on_platform', 'url_suffix', 'platform', 'post_id', 'account_id', 'parent_comment_id_on_platform',\n               'text', 'publication_date', 'data']"),
    ("    rows = [[c.id_on_platform, c.url, c.post_id, c.account_id, c.parent_comment_id_on_platform,",
     "    rows = [[c.id_on_platform, c.url_suffix, c.platform, c.post_id, c.account_id, c.parent_comment_id_on_platform,"),
    # batch_store_new_comment_archives
    ("    columns = ['id_on_platform', 'url', 'post_url', 'post_id_on_platform', 'account_id_on_platform',\n               'account_url', 'parent_comment_id_on_platform', 'text', 'publication_date', 'data',\n               'archive_session_id', 'canonical_id']",
     "    columns = ['id_on_platform', 'url_suffix', 'platform', 'post_url_suffix', 'post_id_on_platform', 'account_id_on_platform',\n               'account_url_suffix', 'parent_comment_id_on_platform', 'text', 'publication_date', 'data',\n               'archive_session_id', 'canonical_id']"),
    ("    rows = [[c.id_on_platform, c.url, c.post_url, c.post_id_on_platform,\n             c.account_id_on_platform, c.account_url, c.parent_comment_id_on_platform,",
     "    rows = [[c.id_on_platform, c.url_suffix, c.platform, c.post_url_suffix, c.post_id_on_platform,\n             c.account_id_on_platform, c.account_url_suffix, c.parent_comment_id_on_platform,"),
    # preserve_canonical_identifiers
    ("    if hasattr(synthesized, 'url'):\n        synthesized.url = reconcile_primitives(existing_canonical.url, synthesized.url)",
     "    if hasattr(synthesized, 'url_suffix'):\n        synthesized.url_suffix = reconcile_primitives(existing_canonical.url_suffix, synthesized.url_suffix)"),
]

for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        print(f"OK: {old[:55]!r}")
    else:
        print(f"MISSING: {old[:70]!r}")

open('db_loaders/db_intake.py', 'w', encoding='utf-8').write(content)
print('Done')
