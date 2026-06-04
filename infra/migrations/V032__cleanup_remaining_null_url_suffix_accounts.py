"""
V032 — Clean up the null-like url_suffix accounts that V020 missed

V020 attempted to break up the accounts merged by the owner.username=None
extraction bug, but its predicate matched only the exact literal 'None/'.

The Account.normalize_url_suffix validator, however, strips the trailing slash
before storing (`v.strip().split('?')[0].rstrip('/')`), so an extracted
"None/" is actually persisted as "None". V020 therefore caught only the rows
written before that validator existed (notably the original giant pre-existing
canonical, whose frozen url_suffix stayed "None/") and left every later bad row
— stored as "None", or as NULL when neither username nor id was available —
untouched.

This migration repeats V020's cleanup using the SAME null-like test the
ingestion guard uses (_is_valid_identifier: NULL, '', 'None', 'None/'):
  1. Identify canonical account rows with a null-like url_suffix
  2. Remove / NULL all FK-dependent rows (account_relation[_archive],
     account_tag, then nullable FK references)
  3. Delete the bad canonical account rows
  4. Reset the contributing archive_sessions to 'parsed' so entity extraction
     re-runs with the fixed extractors (see account_url_suffix() in
     structures_to_entities), which no longer emit the "None" sentinel.

Note: accounts that are genuinely unidentifiable in the HAR (no username AND no
id anywhere) will re-extract to a NULL url_suffix again — but they will no
longer MERGE, because the ingestion guard refuses to match on a null-like
identifier. The merge-magnet problem is resolved either way.
"""

# Matches db_intake._is_valid_identifier: NULL, empty string, 'None', or 'None/'.
NULL_LIKE_URL_SUFFIX = (
    "(url_suffix IS NULL "
    "OR url_suffix = '' "
    "OR TRIM(TRAILING '/' FROM url_suffix) = 'None')"
)


def run(cnx):
    cur = cnx.cursor()
    try:
        # ------------------------------------------------------------------ #
        # Step 1: Collect bad canonical account IDs
        # ------------------------------------------------------------------ #
        cur.execute(f"SELECT id FROM account WHERE {NULL_LIKE_URL_SUFFIX}")
        bad_account_ids = [row[0] for row in cur.fetchall()]

        if not bad_account_ids:
            print("    V032: no canonical accounts with a null-like url_suffix found — nothing to do")
            return

        print(f"    V032: found {len(bad_account_ids)} bad canonical account(s) with a null-like url_suffix")
        ph = ','.join(['%s'] * len(bad_account_ids))

        # ------------------------------------------------------------------ #
        # Step 2: Collect affected archive session IDs BEFORE deleting
        #         account_archive rows (we need them to identify sessions)
        # ------------------------------------------------------------------ #
        cur.execute(
            f"""SELECT DISTINCT aa.archive_session_id
                FROM account_archive aa
                JOIN archive_session s ON s.id = aa.archive_session_id
                WHERE aa.canonical_id IN ({ph})
                  AND s.incorporation_status = 'done'""",
            bad_account_ids,
        )
        affected_session_ids = [row[0] for row in cur.fetchall()]
        print(f"    V032: {len(affected_session_ids)} archive session(s) will be reset to 'parsed'")

        # ------------------------------------------------------------------ #
        # Step 3: Delete account_relation_archive rows that reference
        #         account_relation rows involving the bad accounts
        #         (must go first because account_relation_archive.canonical_id
        #          → account_relation.id, which is NOT NULL constrained)
        # ------------------------------------------------------------------ #
        cur.execute(
            f"""SELECT id FROM account_relation
                WHERE followed_account_id IN ({ph})
                   OR follower_account_id IN ({ph})""",
            bad_account_ids + bad_account_ids,
        )
        bad_relation_ids = [row[0] for row in cur.fetchall()]

        if bad_relation_ids:
            ph_rel = ','.join(['%s'] * len(bad_relation_ids))
            cur.execute(
                f"DELETE FROM account_relation_archive WHERE canonical_id IN ({ph_rel})",
                bad_relation_ids,
            )
            cur.execute(
                f"DELETE FROM account_relation WHERE id IN ({ph_rel})",
                bad_relation_ids,
            )
            print(f"    V032: deleted {len(bad_relation_ids)} account_relation row(s) and their archives")

        # ------------------------------------------------------------------ #
        # Step 4: Delete account_tag rows (account_tag.account_id is NOT NULL)
        # ------------------------------------------------------------------ #
        cur.execute(f"DELETE FROM account_tag WHERE account_id IN ({ph})", bad_account_ids)

        # ------------------------------------------------------------------ #
        # Step 5: Null out nullable FK references to the bad accounts
        # ------------------------------------------------------------------ #
        for table, col in [
            ('post', 'account_id'),
            ('media', 'account_id'),
            ('comment', 'account_id'),
            ('post_like', 'account_id'),
            ('tagged_account', 'tagged_account_id'),
        ]:
            cur.execute(
                f"UPDATE `{table}` SET `{col}` = NULL WHERE `{col}` IN ({ph})",
                bad_account_ids,
            )

        # ------------------------------------------------------------------ #
        # Step 6: Delete account_archive rows for the bad canonicals
        # ------------------------------------------------------------------ #
        cur.execute(f"DELETE FROM account_archive WHERE canonical_id IN ({ph})", bad_account_ids)

        # ------------------------------------------------------------------ #
        # Step 7: Delete the bad canonical account rows themselves
        # ------------------------------------------------------------------ #
        cur.execute(f"DELETE FROM account WHERE id IN ({ph})", bad_account_ids)
        print(f"    V032: deleted {len(bad_account_ids)} bad canonical account(s)")

        # ------------------------------------------------------------------ #
        # Step 8: Reset affected archive sessions to 'parsed'
        # ------------------------------------------------------------------ #
        if affected_session_ids:
            ph_s = ','.join(['%s'] * len(affected_session_ids))
            cur.execute(
                f"""UPDATE archive_session
                    SET incorporation_status = 'parsed'
                    WHERE id IN ({ph_s})
                      AND incorporation_status = 'done'""",
                affected_session_ids,
            )
            print(f"    V032: reset {cur.rowcount} archive session(s) to 'parsed'")

        cnx.commit()
        print("    V032: done")

    finally:
        cur.close()
