content = open('db_loaders/db_intake.py', encoding='utf-8').read()

replacements = [
    # get_canonical_account
    ('    WHERE (url = %(url)s AND url IS NOT NULL)\n              OR (id_on_platform = %(id_on_platform)s AND id_on_platform IS NOT NULL)\n           LIMIT 1""",\n        {"url": account.url, "id_on_platform": account.id_on_platform},',
     '    WHERE (url_suffix = %(url_suffix)s AND url_suffix IS NOT NULL)\n              OR (id_on_platform = %(id_on_platform)s AND id_on_platform IS NOT NULL)\n           LIMIT 1""",\n        {"url_suffix": account.url_suffix, "id_on_platform": account.id_on_platform},'),
    # store_account: identifiers
    ('    if account.url and f"url_{account.url}" not in account_identifiers:\n        account_identifiers.append(f"url_{account.url}")',
     '    if account.url_suffix and f"url_{account.url_suffix}" not in account_identifiers:\n        account_identifiers.append(f"url_{account.url_suffix}")'),
    # store_account UPDATE
    ('               SET url            = %(url)s,\n                   id_on_platform = %(id_on_platform)s,',
     '               SET url_suffix     = %(url_suffix)s,\n                   platform       = %(platform)s,\n                   id_on_platform = %(id_on_platform)s,'),
    ('"id": account.id,\n                "id_on_platform": account.id_on_platform,\n                "url": account.url,',
     '"id": account.id,\n                "id_on_platform": account.id_on_platform,\n                "url_suffix": account.url_suffix,\n                "platform": account.platform,'),
    # store_account INSERT
    ('            """INSERT INTO account (url, id_on_platform, identifiers, display_name, bio, data)\n               VALUES (%(url)s, %(id_on_platform)s, %(identifiers)s, %(display_name)s, %(bio)s, %(data)s)""",\n            {\n                "id_on_platform": account.id_on_platform,\n                "url": account.url,',
     '            """INSERT INTO account (url_suffix, platform, id_on_platform, identifiers, display_name, bio, data)\n               VALUES (%(url_suffix)s, %(platform)s, %(id_on_platform)s, %(identifiers)s, %(display_name)s, %(bio)s, %(data)s)""",\n            {\n                "id_on_platform": account.id_on_platform,\n                "url_suffix": account.url_suffix,\n                "platform": account.platform,'),
    # store_account_archive UPDATE
    ('               SET url                = %(url)s,\n                   id_on_platform     = %(id_on_platform)s,',
     '               SET url_suffix         = %(url_suffix)s,\n                   platform           = %(platform)s,\n                   id_on_platform     = %(id_on_platform)s,'),
    ('"id": existing_id,\n                "id_on_platform": account.id_on_platform,\n                "url": account.url,',
     '"id": existing_id,\n                "id_on_platform": account.id_on_platform,\n                "url_suffix": account.url_suffix,\n                "platform": account.platform,'),
    # store_account_archive INSERT
    ('            """INSERT INTO account_archive (url, id_on_platform, display_name, bio, data, archive_session_id, canonical_id)\n               VALUES (%(url)s, %(id_on_platform)s, %(display_name)s, %(bio)s, %(data)s, %(archive_session_id)s, %(canonical_id)s)""",\n            {\n                "id_on_platform": account.id_on_platform,\n                "url": account.url,',
     '            """INSERT INTO account_archive (url_suffix, platform, id_on_platform, display_name, bio, data, archive_session_id, canonical_id)\n               VALUES (%(url_suffix)s, %(platform)s, %(id_on_platform)s, %(display_name)s, %(bio)s, %(data)s, %(archive_session_id)s, %(canonical_id)s)""",\n            {\n                "id_on_platform": account.id_on_platform,\n                "url_suffix": account.url_suffix,\n                "platform": account.platform,'),
    # get_canonical_post
    ('    WHERE (url = %(url)s AND url IS NOT NULL)\n              OR (id_on_platform = %(id_on_platform)s AND id_on_platform IS NOT NULL)\n           LIMIT 1""",\n        {"url": post.url, "id_on_platform": post.id_on_platform},',
     '    WHERE (url_suffix = %(url_suffix)s AND url_suffix IS NOT NULL)\n              OR (id_on_platform = %(id_on_platform)s AND id_on_platform IS NOT NULL)\n           LIMIT 1""",\n        {"url_suffix": post.url_suffix, "id_on_platform": post.id_on_platform},'),
    # store_post: Account lookup
    ('        stored_account = get_canonical_account(\n            Account(url=post.account_url, id_on_platform=post.account_id_on_platform)\n        )',
     '        stored_account = get_canonical_account(\n            Account(url_suffix=post.account_url_suffix, id_on_platform=post.account_id_on_platform, platform=post.platform)\n        )'),
    # store_post UPDATE
    ('               SET url              = %(url)s,\n                   id_on_platform   = %(id_on_platform)s,\n                   account_id       = %(account_id)s,',
     '               SET url_suffix        = %(url_suffix)s,\n                   platform         = %(platform)s,\n                   id_on_platform   = %(id_on_platform)s,\n                   account_id       = %(account_id)s,'),
    ('"id": post.id,\n                "url": post.url,\n                "id_on_platform": post.id_on_platform,',
     '"id": post.id,\n                "url_suffix": post.url_suffix,\n                "platform": post.platform,\n                "id_on_platform": post.id_on_platform,'),
    # store_post INSERT
    ('            """INSERT INTO post (url, id_on_platform, account_id, publication_date, caption, data)\n               VALUES (%(url)s, %(id_on_platform)s, %(account_id)s, %(publication_date)s, %(caption)s, %(data)s)""",\n            {\n                "url": post.url,',
     '            """INSERT INTO post (url_suffix, platform, id_on_platform, account_id, publication_date, caption, data)\n               VALUES (%(url_suffix)s, %(platform)s, %(id_on_platform)s, %(account_id)s, %(publication_date)s, %(caption)s, %(data)s)""",\n            {\n                "url_suffix": post.url_suffix,\n                "platform": post.platform,'),
    # store_post_archive UPDATE
    ('               SET url                    = %(url)s,\n                   id_on_platform         = %(id_on_platform)s,',
     '               SET url_suffix              = %(url_suffix)s,\n                   platform               = %(platform)s,\n                   id_on_platform         = %(id_on_platform)s,'),
    ('                   account_url            = %(account_url)s,',
     '                   account_url_suffix     = %(account_url_suffix)s,'),
    ('"id": existing_id,\n                "url": post.url,\n                "id_on_platform": post.id_on_platform,',
     '"id": existing_id,\n                "url_suffix": post.url_suffix,\n                "platform": post.platform,\n                "id_on_platform": post.id_on_platform,'),
    ('"account_url": post.account_url,\n                "account_id_on_platform": post.account_id_on_platform,\n            },\n            return_type="none"\n        )\n        return existing_id\n    else:\n        return db.execute_query(\n            """INSERT INTO post_archive',
     '"account_url_suffix": post.account_url_suffix,\n                "account_id_on_platform": post.account_id_on_platform,\n            },\n            return_type="none"\n        )\n        return existing_id\n    else:\n        return db.execute_query(\n            """INSERT INTO post_archive'),
    # store_post_archive INSERT
    ('                   (url, id_on_platform, publication_date, caption, data,\n                    archive_session_id, canonical_id, account_url, account_id_on_platform)',
     '                   (url_suffix, platform, id_on_platform, publication_date, caption, data,\n                    archive_session_id, canonical_id, account_url_suffix, account_id_on_platform)'),
    ('                   (%(url)s, %(id_on_platform)s, %(publication_date)s, %(caption)s, %(data)s,\n                    %(archive_session_id)s, %(canonical_id)s, %(account_url)s, %(account_id_on_platform)s)""",',
     '                   (%(url_suffix)s, %(platform)s, %(id_on_platform)s, %(publication_date)s, %(caption)s, %(data)s,\n                    %(archive_session_id)s, %(canonical_id)s, %(account_url_suffix)s, %(account_id_on_platform)s)""",'),
    ('"url": post.url,\n                "id_on_platform": post.id_on_platform,\n                "publication_date":',
     '"url_suffix": post.url_suffix,\n                "platform": post.platform,\n                "id_on_platform": post.id_on_platform,\n                "publication_date":'),
    ('"account_url": post.account_url,\n                "account_id_on_platform": post.account_id_on_platform,\n            },\n            return_type="id"',
     '"account_url_suffix": post.account_url_suffix,\n                "account_id_on_platform": post.account_id_on_platform,\n            },\n            return_type="id"'),
]

for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        print(f"OK: {old[:60]!r}")
    else:
        print(f"MISSING: {old[:75]!r}")

open('db_loaders/db_intake.py', 'w', encoding='utf-8').write(content)
print('Done')
