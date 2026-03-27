"""
V008 - Drop post_engagement tables; create comment, post_like, tagged_account tables;
alter account_relation and account_relation_archive.

Drops the obsolete post_engagement, post_engagement_archive, post_engagement_tag tables
and replaces them with proper typed tables: comment, comment_archive, post_like,
post_like_archive, tagged_account, tagged_account_archive.

Also:
  - Adds id_on_platform and data columns to account_relation
  - Makes followed_account_url/follower_account_url nullable in account_relation_archive
  - Adds UNIQUE(canonical_id, archive_session_id) to account_relation_archive
"""

import time


def _table_exists(cur, table_name: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) AS cnt FROM information_schema.tables "
        "WHERE table_schema = DATABASE() AND table_name = %s",
        (table_name,)
    )
    row = cur.fetchone()
    return (row["cnt"] if isinstance(row, dict) else row[0]) > 0


def _column_exists(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) AS cnt FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
        (table_name, column_name)
    )
    row = cur.fetchone()
    return (row["cnt"] if isinstance(row, dict) else row[0]) > 0


def _column_is_nullable(cur, table_name: str, column_name: str) -> bool:
    cur.execute(
        "SELECT IS_NULLABLE FROM information_schema.columns "
        "WHERE table_schema = DATABASE() AND table_name = %s AND column_name = %s",
        (table_name, column_name)
    )
    row = cur.fetchone()
    val = row["IS_NULLABLE"] if isinstance(row, dict) else row[0]
    return val == "YES"


def _constraint_exists(cur, table: str, constraint_name: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) AS cnt FROM information_schema.table_constraints "
        "WHERE table_schema = DATABASE() AND table_name = %s AND constraint_name = %s",
        (table, constraint_name)
    )
    row = cur.fetchone()
    return (row["cnt"] if isinstance(row, dict) else row[0]) > 0


def _index_exists(cur, table: str, index_name: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) AS cnt FROM information_schema.statistics "
        "WHERE table_schema = DATABASE() AND table_name = %s AND index_name = %s",
        (table, index_name)
    )
    row = cur.fetchone()
    return (row["cnt"] if isinstance(row, dict) else row[0]) > 0


def run(cnx):
    cur = cnx.cursor(dictionary=True)

    # -------------------------------------------------------------------------
    # 1. Drop obsolete post_engagement tables (foreign-key order)
    # -------------------------------------------------------------------------
    for table in ("post_engagement_tag", "post_engagement_archive", "post_engagement"):
        if _table_exists(cur, table):
            print(f"    Dropping table '{table}' ...", flush=True)
            t = time.perf_counter()
            cur.execute(f"DROP TABLE {table}")
            print(f"    Dropped table '{table}' ({time.perf_counter() - t:.1f}s)")
        else:
            print(f"    Table '{table}' does not exist, skipping")

    # -------------------------------------------------------------------------
    # 2. Create comment table
    # -------------------------------------------------------------------------
    if not _table_exists(cur, "comment"):
        print("    Creating table 'comment' ...", flush=True)
        t = time.perf_counter()
        cur.execute("""
            CREATE TABLE comment (
                id                            int auto_increment primary key,
                create_date                   timestamp default CURRENT_TIMESTAMP not null,
                update_date                   timestamp default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP invisible,
                id_on_platform                varchar(100) null,
                url                           varchar(250) null,
                post_id                       int          null,
                account_id                    int          null,
                parent_comment_id_on_platform varchar(100) null,
                text                          text         null,
                publication_date              datetime     null,
                data                          json         null,
                notes                         text         null,
                constraint comment_post_id_fk
                    foreign key (post_id) references post (id),
                constraint comment_account_id_fk
                    foreign key (account_id) references account (id)
            ) engine = InnoDB
        """)
        cur.execute("CREATE INDEX comment_id_on_platform_index ON comment (id_on_platform)")
        cur.execute("CREATE INDEX comment_post_id_index ON comment (post_id)")
        cur.execute("CREATE INDEX comment_account_id_index ON comment (account_id)")
        print(f"    Created table 'comment' ({time.perf_counter() - t:.1f}s)")
    else:
        print("    Table 'comment' already exists, skipping")

    # -------------------------------------------------------------------------
    # 3. Create comment_archive table
    # -------------------------------------------------------------------------
    if not _table_exists(cur, "comment_archive"):
        print("    Creating table 'comment_archive' ...", flush=True)
        t = time.perf_counter()
        cur.execute("""
            CREATE TABLE comment_archive (
                id                            int auto_increment primary key,
                create_date                   timestamp default CURRENT_TIMESTAMP not null,
                update_date                   timestamp default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP invisible,
                canonical_id                  int          null,
                archive_session_id            int          null,
                id_on_platform                varchar(100) null,
                url                           varchar(250) null,
                post_url                      varchar(250) null,
                post_id_on_platform           varchar(100) null,
                account_id_on_platform        varchar(100) null,
                account_url                   varchar(200) null,
                parent_comment_id_on_platform varchar(100) null,
                text                          text         null,
                publication_date              datetime     null,
                data                          json         null,
                constraint comment_archive_canonical_fk
                    foreign key (canonical_id) references comment (id),
                constraint comment_archive_session_fk
                    foreign key (archive_session_id) references archive_session (id),
                constraint uq_comment_archive_canonical_session
                    unique (canonical_id, archive_session_id)
            ) engine = InnoDB
        """)
        cur.execute("CREATE INDEX comment_archive_canonical_id_index ON comment_archive (canonical_id)")
        cur.execute("CREATE INDEX comment_archive_session_id_index ON comment_archive (archive_session_id)")
        cur.execute("CREATE INDEX comment_archive_id_on_platform_index ON comment_archive (id_on_platform)")
        cur.execute("CREATE INDEX comment_archive_post_id_on_platform_index ON comment_archive (post_id_on_platform)")
        print(f"    Created table 'comment_archive' ({time.perf_counter() - t:.1f}s)")
    else:
        print("    Table 'comment_archive' already exists, skipping")

    # -------------------------------------------------------------------------
    # 4. Create post_like table
    # -------------------------------------------------------------------------
    if not _table_exists(cur, "post_like"):
        print("    Creating table 'post_like' ...", flush=True)
        t = time.perf_counter()
        cur.execute("""
            CREATE TABLE post_like (
                id             int auto_increment primary key,
                create_date    timestamp default CURRENT_TIMESTAMP not null,
                update_date    timestamp default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP invisible,
                id_on_platform varchar(200) null,
                post_id        int          null,
                account_id     int          null,
                data           json         null,
                notes          text         null,
                constraint post_like_post_id_fk
                    foreign key (post_id) references post (id),
                constraint post_like_account_id_fk
                    foreign key (account_id) references account (id)
            ) engine = InnoDB
        """)
        cur.execute("CREATE INDEX post_like_id_on_platform_index ON post_like (id_on_platform)")
        cur.execute("CREATE INDEX post_like_post_id_index ON post_like (post_id)")
        cur.execute("CREATE INDEX post_like_account_id_index ON post_like (account_id)")
        print(f"    Created table 'post_like' ({time.perf_counter() - t:.1f}s)")
    else:
        print("    Table 'post_like' already exists, skipping")

    # -------------------------------------------------------------------------
    # 5. Create post_like_archive table
    # -------------------------------------------------------------------------
    if not _table_exists(cur, "post_like_archive"):
        print("    Creating table 'post_like_archive' ...", flush=True)
        t = time.perf_counter()
        cur.execute("""
            CREATE TABLE post_like_archive (
                id                     int auto_increment primary key,
                create_date            timestamp default CURRENT_TIMESTAMP not null,
                update_date            timestamp default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP invisible,
                canonical_id           int          null,
                archive_session_id     int          null,
                id_on_platform         varchar(200) null,
                post_id_on_platform    varchar(100) null,
                post_url               varchar(250) null,
                account_id_on_platform varchar(100) null,
                account_url            varchar(200) null,
                data                   json         null,
                constraint post_like_archive_canonical_fk
                    foreign key (canonical_id) references post_like (id),
                constraint post_like_archive_session_fk
                    foreign key (archive_session_id) references archive_session (id),
                constraint uq_post_like_archive_canonical_session
                    unique (canonical_id, archive_session_id)
            ) engine = InnoDB
        """)
        cur.execute("CREATE INDEX post_like_archive_canonical_id_index ON post_like_archive (canonical_id)")
        cur.execute("CREATE INDEX post_like_archive_session_id_index ON post_like_archive (archive_session_id)")
        cur.execute("CREATE INDEX post_like_archive_id_on_platform_index ON post_like_archive (id_on_platform)")
        cur.execute("CREATE INDEX post_like_archive_post_id_on_platform_index ON post_like_archive (post_id_on_platform)")
        print(f"    Created table 'post_like_archive' ({time.perf_counter() - t:.1f}s)")
    else:
        print("    Table 'post_like_archive' already exists, skipping")

    # -------------------------------------------------------------------------
    # 6. Create tagged_account table
    # -------------------------------------------------------------------------
    if not _table_exists(cur, "tagged_account"):
        print("    Creating table 'tagged_account' ...", flush=True)
        t = time.perf_counter()
        cur.execute("""
            CREATE TABLE tagged_account (
                id                int auto_increment primary key,
                create_date       timestamp default CURRENT_TIMESTAMP not null,
                update_date       timestamp default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP invisible,
                id_on_platform    varchar(300) null,
                tagged_account_id int          null,
                post_id           int          null,
                media_id          int          null,
                tag_x_position    float        null,
                tag_y_position    float        null,
                data              json         null,
                notes             text         null,
                constraint tagged_account_account_id_fk
                    foreign key (tagged_account_id) references account (id),
                constraint tagged_account_post_id_fk
                    foreign key (post_id) references post (id),
                constraint tagged_account_media_id_fk
                    foreign key (media_id) references media (id)
            ) engine = InnoDB
        """)
        cur.execute("CREATE INDEX tagged_account_id_on_platform_index ON tagged_account (id_on_platform)")
        cur.execute("CREATE INDEX tagged_account_tagged_account_id_index ON tagged_account (tagged_account_id)")
        cur.execute("CREATE INDEX tagged_account_post_id_index ON tagged_account (post_id)")
        cur.execute("CREATE INDEX tagged_account_media_id_index ON tagged_account (media_id)")
        print(f"    Created table 'tagged_account' ({time.perf_counter() - t:.1f}s)")
    else:
        print("    Table 'tagged_account' already exists, skipping")

    # -------------------------------------------------------------------------
    # 7. Create tagged_account_archive table
    # -------------------------------------------------------------------------
    if not _table_exists(cur, "tagged_account_archive"):
        print("    Creating table 'tagged_account_archive' ...", flush=True)
        t = time.perf_counter()
        cur.execute("""
            CREATE TABLE tagged_account_archive (
                id                             int auto_increment primary key,
                create_date                    timestamp default CURRENT_TIMESTAMP not null,
                update_date                    timestamp default CURRENT_TIMESTAMP not null on update CURRENT_TIMESTAMP invisible,
                canonical_id                   int          null,
                archive_session_id             int          null,
                id_on_platform                 varchar(300) null,
                tagged_account_id_on_platform  varchar(100) null,
                tagged_account_url             varchar(250) null,
                context_post_url               varchar(250) null,
                context_media_url              varchar(250) null,
                context_post_id_on_platform    varchar(100) null,
                context_media_id_on_platform   varchar(100) null,
                tag_x_position                 float        null,
                tag_y_position                 float        null,
                data                           json         null,
                constraint tagged_account_archive_canonical_fk
                    foreign key (canonical_id) references tagged_account (id),
                constraint tagged_account_archive_session_fk
                    foreign key (archive_session_id) references archive_session (id),
                constraint uq_tagged_account_archive_canonical_session
                    unique (canonical_id, archive_session_id)
            ) engine = InnoDB
        """)
        cur.execute("CREATE INDEX tagged_account_archive_canonical_id_index ON tagged_account_archive (canonical_id)")
        cur.execute("CREATE INDEX tagged_account_archive_session_id_index ON tagged_account_archive (archive_session_id)")
        cur.execute("CREATE INDEX tagged_account_archive_id_on_platform_index ON tagged_account_archive (id_on_platform)")
        cur.execute("CREATE INDEX tagged_account_archive_tagged_id_on_platform_index ON tagged_account_archive (tagged_account_id_on_platform)")
        print(f"    Created table 'tagged_account_archive' ({time.perf_counter() - t:.1f}s)")
    else:
        print("    Table 'tagged_account_archive' already exists, skipping")

    # -------------------------------------------------------------------------
    # 8. Alter account_relation: add id_on_platform and data columns
    # -------------------------------------------------------------------------
    if not _column_exists(cur, "account_relation", "id_on_platform"):
        print("    account_relation: adding column 'id_on_platform' ...", flush=True)
        t = time.perf_counter()
        cur.execute("ALTER TABLE account_relation ADD COLUMN id_on_platform varchar(200) null")
        if not _index_exists(cur, "account_relation", "account_relation_id_on_platform_index"):
            cur.execute("CREATE INDEX account_relation_id_on_platform_index ON account_relation (id_on_platform)")
        print(f"    account_relation: added column 'id_on_platform' ({time.perf_counter() - t:.1f}s)")
    else:
        print("    account_relation: column 'id_on_platform' already exists, skipping")

    if not _column_exists(cur, "account_relation", "data"):
        print("    account_relation: adding column 'data' ...", flush=True)
        t = time.perf_counter()
        cur.execute("ALTER TABLE account_relation ADD COLUMN data json null")
        print(f"    account_relation: added column 'data' ({time.perf_counter() - t:.1f}s)")
    else:
        print("    account_relation: column 'data' already exists, skipping")

    # -------------------------------------------------------------------------
    # 9. Alter account_relation_archive: make URL columns nullable
    # -------------------------------------------------------------------------
    if not _column_is_nullable(cur, "account_relation_archive", "followed_account_url"):
        print("    account_relation_archive: making 'followed_account_url' nullable ...", flush=True)
        t = time.perf_counter()
        cur.execute("ALTER TABLE account_relation_archive MODIFY followed_account_url varchar(200) null")
        print(f"    account_relation_archive: made 'followed_account_url' nullable ({time.perf_counter() - t:.1f}s)")
    else:
        print("    account_relation_archive: 'followed_account_url' already nullable, skipping")

    if not _column_is_nullable(cur, "account_relation_archive", "follower_account_url"):
        print("    account_relation_archive: making 'follower_account_url' nullable ...", flush=True)
        t = time.perf_counter()
        cur.execute("ALTER TABLE account_relation_archive MODIFY follower_account_url varchar(200) null")
        print(f"    account_relation_archive: made 'follower_account_url' nullable ({time.perf_counter() - t:.1f}s)")
    else:
        print("    account_relation_archive: 'follower_account_url' already nullable, skipping")

    # -------------------------------------------------------------------------
    # 10. Add UNIQUE constraint to account_relation_archive
    # -------------------------------------------------------------------------
    if not _constraint_exists(cur, "account_relation_archive", "uq_account_relation_archive_canonical_session"):
        print("    account_relation_archive: adding UNIQUE constraint ...", flush=True)
        t = time.perf_counter()
        cur.execute(
            "ALTER TABLE account_relation_archive ADD CONSTRAINT uq_account_relation_archive_canonical_session "
            "UNIQUE (canonical_id, archive_session_id)"
        )
        print(f"    account_relation_archive: added UNIQUE constraint ({time.perf_counter() - t:.1f}s)")
    else:
        print("    account_relation_archive: UNIQUE constraint already exists, skipping")

    cur.close()
