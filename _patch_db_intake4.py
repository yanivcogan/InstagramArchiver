content = open('db_loaders/db_intake.py', encoding='utf-8').read()

replacements = [
    # Fix erroneous media_type="image" in Post() constructor
    ('Post(url_suffix=media.post_url_suffix, id_on_platform=media.post_id_on_platform, platform=media.platform, media_type="image")',
     'Post(url_suffix=media.post_url_suffix, id_on_platform=media.post_id_on_platform, platform=media.platform)'),
    # store_comment_archive UPDATE
    ('               SET id_on_platform                = %(id_on_platform)s,\n                   url                           = %(url)s,\n                   post_url                      = %(post_url)s,\n                   post_id_on_platform           = %(post_id_on_platform)s,\n                   account_id_on_platform        = %(account_id_on_platform)s,\n                   account_url                   = %(account_url)s,',
     '               SET id_on_platform                = %(id_on_platform)s,\n                   url_suffix                    = %(url_suffix)s,\n                   platform                      = %(platform)s,\n                   post_url_suffix               = %(post_url_suffix)s,\n                   post_id_on_platform           = %(post_id_on_platform)s,\n                   account_id_on_platform        = %(account_id_on_platform)s,\n                   account_url_suffix            = %(account_url_suffix)s,'),
    ('"id": existing_id,\n                "id_on_platform": comment.id_on_platform,\n                "url": comment.url,\n                "post_url": comment.post_url,',
     '"id": existing_id,\n                "id_on_platform": comment.id_on_platform,\n                "url_suffix": comment.url_suffix,\n                "platform": comment.platform,\n                "post_url_suffix": comment.post_url_suffix,'),
    ('"account_url": comment.account_url,\n                "parent_comment_id_on_platform": comment.parent_comment_id_on_platform,\n                "text": comment.text,\n                "publication_date": comment.publication_date.isoformat() if comment.publication_date else None,\n                "data": json.dumps(comment.data) if comment.data else None,\n                "archive_session_id": archive_session_id,\n                "canonical_id": canonical_id,\n            },\n            return_type="none"\n        )\n        return existing_id\n    else:\n        return db.execute_query(\n            """INSERT INTO comment_archive',
     '"account_url_suffix": comment.account_url_suffix,\n                "parent_comment_id_on_platform": comment.parent_comment_id_on_platform,\n                "text": comment.text,\n                "publication_date": comment.publication_date.isoformat() if comment.publication_date else None,\n                "data": json.dumps(comment.data) if comment.data else None,\n                "archive_session_id": archive_session_id,\n                "canonical_id": canonical_id,\n            },\n            return_type="none"\n        )\n        return existing_id\n    else:\n        return db.execute_query(\n            """INSERT INTO comment_archive'),
    # store_comment_archive INSERT
    ('                   (id_on_platform, url, post_url, post_id_on_platform, account_id_on_platform,\n                    account_url, parent_comment_id_on_platform, text, publication_date, data,\n                    archive_session_id, canonical_id)',
     '                   (id_on_platform, url_suffix, platform, post_url_suffix, post_id_on_platform, account_id_on_platform,\n                    account_url_suffix, parent_comment_id_on_platform, text, publication_date, data,\n                    archive_session_id, canonical_id)'),
    ('                   (%(id_on_platform)s, %(url)s, %(post_url)s, %(post_id_on_platform)s,\n                    %(account_id_on_platform)s, %(account_url)s, %(parent_comment_id_on_platform)s,',
     '                   (%(id_on_platform)s, %(url_suffix)s, %(platform)s, %(post_url_suffix)s, %(post_id_on_platform)s,\n                    %(account_id_on_platform)s, %(account_url_suffix)s, %(parent_comment_id_on_platform)s,'),
    ('"id_on_platform": comment.id_on_platform,\n                "url": comment.url,\n                "post_url": comment.post_url,',
     '"id_on_platform": comment.id_on_platform,\n                "url_suffix": comment.url_suffix,\n                "platform": comment.platform,\n                "post_url_suffix": comment.post_url_suffix,'),
    ('"account_url": comment.account_url,\n                "parent_comment_id_on_platform": comment.parent_comment_id_on_platform,\n                "text": comment.text,\n                "publication_date": comment.publication_date.isoformat() if comment.publication_date else None,\n                "data": json.dumps(comment.data) if comment.data else None,\n                "archive_session_id": archive_session_id,\n                "canonical_id": canonical_id,\n            },\n            return_type="id"',
     '"account_url_suffix": comment.account_url_suffix,\n                "parent_comment_id_on_platform": comment.parent_comment_id_on_platform,\n                "text": comment.text,\n                "publication_date": comment.publication_date.isoformat() if comment.publication_date else None,\n                "data": json.dumps(comment.data) if comment.data else None,\n                "archive_session_id": archive_session_id,\n                "canonical_id": canonical_id,\n            },\n            return_type="id"'),
    # store_post_like: post lookup
    ('        stored_post = get_canonical_post(Post(url=like.post_url, id_on_platform=like.post_id_on_platform))',
     '        stored_post = get_canonical_post(Post(url_suffix=like.post_url_suffix, id_on_platform=like.post_id_on_platform, platform=like.platform))'),
    # store_post_like: account url lookup
    ('            "SELECT id FROM account WHERE url = %(url)s LIMIT 1",\n            {"url": like.account_url},',
     '            "SELECT id FROM account WHERE url_suffix = %(url_suffix)s LIMIT 1",\n            {"url_suffix": like.account_url_suffix},'),
    # store_post_like_archive UPDATE
    ('               SET id_on_platform         = %(id_on_platform)s,\n                   post_id_on_platform    = %(post_id_on_platform)s,\n                   post_url               = %(post_url)s,\n                   account_id_on_platform = %(account_id_on_platform)s,\n                   account_url            = %(account_url)s,',
     '               SET id_on_platform         = %(id_on_platform)s,\n                   post_id_on_platform    = %(post_id_on_platform)s,\n                   post_url_suffix        = %(post_url_suffix)s,\n                   platform               = %(platform)s,\n                   account_id_on_platform = %(account_id_on_platform)s,\n                   account_url_suffix     = %(account_url_suffix)s,'),
    ('"id": existing_id,\n                "id_on_platform": like.id_on_platform,\n                "post_id_on_platform": like.post_id_on_platform,\n                "post_url": like.post_url,',
     '"id": existing_id,\n                "id_on_platform": like.id_on_platform,\n                "post_id_on_platform": like.post_id_on_platform,\n                "post_url_suffix": like.post_url_suffix,\n                "platform": like.platform,'),
    ('"account_url": like.account_url,\n                "data": json.dumps(like.data) if like.data else None,\n                "archive_session_id": archive_session_id,\n                "canonical_id": canonical_id,\n            },\n            return_type="none"\n        )\n        return existing_id\n    else:\n        return db.execute_query(\n            """INSERT INTO post_like_archive',
     '"account_url_suffix": like.account_url_suffix,\n                "data": json.dumps(like.data) if like.data else None,\n                "archive_session_id": archive_session_id,\n                "canonical_id": canonical_id,\n            },\n            return_type="none"\n        )\n        return existing_id\n    else:\n        return db.execute_query(\n            """INSERT INTO post_like_archive'),
    # store_post_like_archive INSERT
    ('                   (id_on_platform, post_id_on_platform, post_url, account_id_on_platform,\n                    account_url, data, archive_session_id, canonical_id)',
     '                   (id_on_platform, post_id_on_platform, post_url_suffix, platform, account_id_on_platform,\n                    account_url_suffix, data, archive_session_id, canonical_id)'),
    ('                   (%(id_on_platform)s, %(post_id_on_platform)s, %(post_url)s,\n                    %(account_id_on_platform)s, %(account_url)s, %(data)s,',
     '                   (%(id_on_platform)s, %(post_id_on_platform)s, %(post_url_suffix)s, %(platform)s,\n                    %(account_id_on_platform)s, %(account_url_suffix)s, %(data)s,'),
    ('"id_on_platform": like.id_on_platform,\n                "post_id_on_platform": like.post_id_on_platform,\n                "post_url": like.post_url,',
     '"id_on_platform": like.id_on_platform,\n                "post_id_on_platform": like.post_id_on_platform,\n                "post_url_suffix": like.post_url_suffix,\n                "platform": like.platform,'),
    ('"account_url": like.account_url,\n                "data": json.dumps(like.data) if like.data else None,\n                "archive_session_id": archive_session_id,\n                "canonical_id": canonical_id,\n            },\n            return_type="id"',
     '"account_url_suffix": like.account_url_suffix,\n                "data": json.dumps(like.data) if like.data else None,\n                "archive_session_id": archive_session_id,\n                "canonical_id": canonical_id,\n            },\n            return_type="id"'),
]

for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        print(f"OK: {old[:60]!r}")
    else:
        print(f"MISSING: {old[:75]!r}")

open('db_loaders/db_intake.py', 'w', encoding='utf-8').write(content)
print('Done')
