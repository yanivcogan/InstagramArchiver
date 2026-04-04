content = open('db_loaders/db_intake.py', encoding='utf-8').read()

replacements = [
    # get_canonical_media
    ('    WHERE (url = %(url)s AND url IS NOT NULL)\n              OR (id_on_platform = %(id_on_platform)s AND id_on_platform IS NOT NULL)\n           LIMIT 1""",\n        {"url": media.url, "id_on_platform": media.id_on_platform},',
     '    WHERE (url_suffix = %(url_suffix)s AND url_suffix IS NOT NULL)\n              OR (id_on_platform = %(id_on_platform)s AND id_on_platform IS NOT NULL)\n           LIMIT 1""",\n        {"url_suffix": media.url_suffix, "id_on_platform": media.id_on_platform},'),
    # store_media: post lookup
    ('        stored_post = get_canonical_post(\n            Post(url=media.post_url, id_on_platform=media.post_id_on_platform)\n        )',
     '        stored_post = get_canonical_post(\n            Post(url_suffix=media.post_url_suffix, id_on_platform=media.post_id_on_platform, platform=media.platform, media_type="image")\n        )'),
    # store_media UPDATE
    ('               SET url              = %(url)s,\n                   id_on_platform   = %(id_on_platform)s,\n                   post_id          = %(post_id)s,',
     '               SET url_suffix        = %(url_suffix)s,\n                   platform         = %(platform)s,\n                   id_on_platform   = %(id_on_platform)s,\n                   post_id          = %(post_id)s,'),
    ('"id": media.id,\n                "url": media.url,\n                "id_on_platform": media.id_on_platform,',
     '"id": media.id,\n                "url_suffix": media.url_suffix,\n                "platform": media.platform,\n                "id_on_platform": media.id_on_platform,'),
    # store_media INSERT
    ('            """INSERT INTO media (url, id_on_platform, post_id, local_url, media_type, data, thumbnail_status)\n               VALUES (%(url)s, %(id_on_platform)s, %(post_id)s, %(local_url)s, %(media_type)s, %(data)s, %(thumbnail_status)s)""",\n            {\n                "url": media.url,',
     '            """INSERT INTO media (url_suffix, platform, id_on_platform, post_id, local_url, media_type, data, thumbnail_status)\n               VALUES (%(url_suffix)s, %(platform)s, %(id_on_platform)s, %(post_id)s, %(local_url)s, %(media_type)s, %(data)s, %(thumbnail_status)s)""",\n            {\n                "url_suffix": media.url_suffix,\n                "platform": media.platform,'),
    # store_media_archive UPDATE
    ('               SET url                 = %(url)s,\n                   id_on_platform      = %(id_on_platform)s,',
     '               SET url_suffix           = %(url_suffix)s,\n                   platform            = %(platform)s,\n                   id_on_platform      = %(id_on_platform)s,'),
    ('                   post_url            = %(post_url)s,\n                   post_id_on_platform = %(post_id_on_platform)s\n               WHERE id = %(id)s""",',
     '                   post_url_suffix     = %(post_url_suffix)s,\n                   post_id_on_platform = %(post_id_on_platform)s\n               WHERE id = %(id)s""",'),
    ('"id": existing_id,\n                "url": media.url,\n                "id_on_platform": media.id_on_platform,',
     '"id": existing_id,\n                "url_suffix": media.url_suffix,\n                "platform": media.platform,\n                "id_on_platform": media.id_on_platform,'),
    ('"post_url": media.post_url,\n                "post_id_on_platform": media.post_id_on_platform,\n            },\n            return_type="none"\n        )\n        return existing_id\n    else:\n        return db.execute_query(\n            """INSERT INTO media_archive',
     '"post_url_suffix": media.post_url_suffix,\n                "post_id_on_platform": media.post_id_on_platform,\n            },\n            return_type="none"\n        )\n        return existing_id\n    else:\n        return db.execute_query(\n            """INSERT INTO media_archive'),
    # store_media_archive INSERT
    ('                   (url, id_on_platform, local_url, media_type, data,\n                    archive_session_id, canonical_id, post_url, post_id_on_platform)',
     '                   (url_suffix, platform, id_on_platform, local_url, media_type, data,\n                    archive_session_id, canonical_id, post_url_suffix, post_id_on_platform)'),
    ('                   (%(url)s, %(id_on_platform)s, %(local_url)s, %(media_type)s, %(data)s,\n                    %(archive_session_id)s, %(canonical_id)s, %(post_url)s, %(post_id_on_platform)s)""",',
     '                   (%(url_suffix)s, %(platform)s, %(id_on_platform)s, %(local_url)s, %(media_type)s, %(data)s,\n                    %(archive_session_id)s, %(canonical_id)s, %(post_url_suffix)s, %(post_id_on_platform)s)""",'),
    ('"url": media.url,\n                "id_on_platform": media.id_on_platform,',
     '"url_suffix": media.url_suffix,\n                "platform": media.platform,\n                "id_on_platform": media.id_on_platform,'),
    ('"post_url": media.post_url,\n                "post_id_on_platform": media.post_id_on_platform,\n            },\n            return_type="id"',
     '"post_url_suffix": media.post_url_suffix,\n                "post_id_on_platform": media.post_id_on_platform,\n            },\n            return_type="id"'),
    # get_canonical_comment
    ('           WHERE (id_on_platform = %(id_on_platform)s AND id_on_platform IS NOT NULL)\n              OR (url = %(url)s AND url IS NOT NULL)\n           LIMIT 1""",\n        {"id_on_platform": comment.id_on_platform, "url": comment.url},',
     '           WHERE (id_on_platform = %(id_on_platform)s AND id_on_platform IS NOT NULL)\n              OR (url_suffix = %(url_suffix)s AND url_suffix IS NOT NULL)\n           LIMIT 1""",\n        {"id_on_platform": comment.id_on_platform, "url_suffix": comment.url_suffix},'),
    # store_comment: post lookup
    ('        stored_post = get_canonical_post(Post(url=comment.post_url, id_on_platform=comment.post_id_on_platform))',
     '        stored_post = get_canonical_post(Post(url_suffix=comment.post_url_suffix, id_on_platform=comment.post_id_on_platform, platform=comment.platform, account_url_suffix=None))'),
    # store_comment: account url lookup
    ('            "SELECT id FROM account WHERE url = %(url)s LIMIT 1",\n            {"url": comment.account_url},',
     '            "SELECT id FROM account WHERE url_suffix = %(url_suffix)s LIMIT 1",\n            {"url_suffix": comment.account_url_suffix},'),
    # store_comment UPDATE
    ('               SET id_on_platform                = %(id_on_platform)s,\n                   url                           = %(url)s,\n                   post_id                       = %(post_id)s,',
     '               SET id_on_platform                = %(id_on_platform)s,\n                   url_suffix                    = %(url_suffix)s,\n                   platform                      = %(platform)s,\n                   post_id                       = %(post_id)s,'),
    ('"id": comment.id,\n                "id_on_platform": comment.id_on_platform,\n                "url": comment.url,',
     '"id": comment.id,\n                "id_on_platform": comment.id_on_platform,\n                "url_suffix": comment.url_suffix,\n                "platform": comment.platform,'),
    # store_comment INSERT
    ('            """INSERT INTO comment\n                   (id_on_platform, url, post_id, account_id, parent_comment_id_on_platform,\n                    text, publication_date, data)\n               VALUES\n                   (%(id_on_platform)s, %(url)s, %(post_id)s, %(account_id)s,',
     '            """INSERT INTO comment\n                   (id_on_platform, url_suffix, platform, post_id, account_id, parent_comment_id_on_platform,\n                    text, publication_date, data)\n               VALUES\n                   (%(id_on_platform)s, %(url_suffix)s, %(platform)s, %(post_id)s, %(account_id)s,'),
    ('"id_on_platform": comment.id_on_platform,\n                "url": comment.url,\n                "post_id":',
     '"id_on_platform": comment.id_on_platform,\n                "url_suffix": comment.url_suffix,\n                "platform": comment.platform,\n                "post_id":'),
]

for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        print(f"OK: {old[:60]!r}")
    else:
        print(f"MISSING: {old[:75]!r}")

open('db_loaders/db_intake.py', 'w', encoding='utf-8').write(content)
print('Done')
