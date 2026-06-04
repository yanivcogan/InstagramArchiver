"""
V032 — Clean up the 'None' url_suffix accounts and archive rows that V020 missed

V020 attempted to break up the accounts merged by the owner.username=None
extraction bug, but its predicate matched only the exact literal 'None/'.

The Account.normalize_url_suffix validator, however, strips the trailing slash
before storing (`v.strip().split('?')[0].rstrip('/')`), so an extracted "None/"
is actually persisted as "None". V020 therefore caught only the rows written
before that validator existed (notably the original giant pre-existing canonical,
whose frozen url_suffix stayed "None/") and left every later bad row — stored as
"None" — untouched.

This migration repeats V020's cleanup using the string sentinels left by the bug
('None', 'None/', and the empty string), and additionally re-queues sessions
whose account_ARCHIVE rows carry the sentinel even when their canonical account
is fine (a session whose buggy run contributed "None" while another run supplied
the real username — the canonical is correct but its provenance row is wrong).

  1. Identify canonical account rows whose url_suffix is a sentinel
  2. Identify sessions that contributed a sentinel account_archive row
  3. Remove / NULL all FK-dependent rows for the bad canonicals, then delete them
  4. Reset every affected archive_session to 'parsed' so entity extraction
     re-runs with the fixed extractors (account_url_suffix() in
     structures_to_entities) AND the fixed validator (collapse_null_like_suffix
     in entity_types), which together (a) stop emitting the sentinel and (b) let
     the re-extracted suffix overwrite the stale "None" archive row.

SQL NULL is deliberately EXCLUDED from the sentinel test. A NULL url_suffix is
the legitimate shape of an id-only account (known by id_on_platform, no
username); deleting those would destroy valid canonical entities whose internal
ids are referenced by the browsing platform. Genuinely unidentifiable accounts
(no username AND no id) likewise keep their NULL suffix but no longer merge,
because the ingestion guard refuses to match on a null-like identifier.
"""


def _sentinel(col: str) -> str:
    """Match the non-NULL null-like url_suffix values the bug produced: the empty
    string, 'None', or 'None/' (trailing slash stripped to 'None')."""
    return f"({col} = '' OR TRIM(TRAILING '/' FROM {col}) = 'None')"


def run(cnx):
    cur = cnx.cursor()
    try:
        # ------------------------------------------------------------------ #
        # Step 1: Collect bad canonical account IDs (sentinel url_suffix)
        # ------------------------------------------------------------------ #
        cur.execute(f"SELECT id FROM account WHERE {_sentinel('url_suffix')}")
        bad_account_ids = [row[0] for row in cur.fetchall()]
        print(f"    V032: found {len(bad_account_ids)} canonical account(s) with a sentinel url_suffix")

        # ------------------------------------------------------------------ #
        # Step 2: Collect affected archive session IDs BEFORE any deletion.
        #   (a) sessions linked to a bad canonical, and
        #   (b) sessions that contributed a sentinel account_archive row even
        #       under an otherwise-correct canonical.
        # Restricted to 'done' sessions — only those have already been extracted
        # and so can carry stale entities worth re-deriving.
        # ------------------------------------------------------------------ #
        affected_session_ids: set = set()

        if bad_account_ids:
            ph = ','.join(['%s'] * len(bad_account_ids))
            cur.execute(
                f"""SELECT DISTINCT aa.archive_session_id
                    FROM account_archive aa
                    JOIN archive_session s ON s.id = aa.archive_session_id
                    WHERE aa.canonical_id IN ({ph})
                      AND s.incorporation_status = 'done'""",
                bad_account_ids,
            )
            affected_session_ids.update(row[0] for row in cur.fetchall())

        cur.execute(
            f"""SELECT DISTINCT aa.archive_session_id
                FROM account_archive aa
                JOIN archive_session s ON s.id = aa.archive_session_id
                WHERE {_sentinel('aa.url_suffix')}
                  AND s.incorporation_status = 'done'"""
        )
        affected_session_ids.update(row[0] for row in cur.fetchall())
        print(f"    V032: {len(affected_session_ids)} archive session(s) will be reset to 'parsed'")

        if not bad_account_ids and not affected_session_ids:
            print("    V032: no sentinel accounts or archive rows found — nothing to do")
            return

        # ------------------------------------------------------------------ #
        # Step 3: Break up the bad canonicals (only if any were found)
        # ------------------------------------------------------------------ #
        if bad_account_ids:
            ph = ','.join(['%s'] * len(bad_account_ids))

            # 3a: account_relation_archive rows must go before account_relation
            #     (account_relation_archive.canonical_id → account_relation.id is
            #     NOT NULL constrained).
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

            # 3b: account_tag.account_id is NOT NULL — delete those rows.
            cur.execute(f"DELETE FROM account_tag WHERE account_id IN ({ph})", bad_account_ids)

            # 3c: NULL out nullable FK references to the bad accounts.
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

            # 3d: account_archive rows for the bad canonicals, then the canonicals.
            cur.execute(f"DELETE FROM account_archive WHERE canonical_id IN ({ph})", bad_account_ids)
            cur.execute(f"DELETE FROM account WHERE id IN ({ph})", bad_account_ids)
            print(f"    V032: deleted {len(bad_account_ids)} bad canonical account(s)")

        # ------------------------------------------------------------------ #
        # Step 4: Reset affected archive sessions to 'parsed'
        # ------------------------------------------------------------------ #
        if affected_session_ids:
            ids = list(affected_session_ids)
            ph_s = ','.join(['%s'] * len(ids))
            cur.execute(
                f"""UPDATE archive_session
                    SET incorporation_status = 'parsed'
                    WHERE id IN ({ph_s})
                      AND incorporation_status = 'done'""",
                ids,
            )
            print(f"    V032: reset {cur.rowcount} archive session(s) to 'parsed'")

        cnx.commit()
        print("    V032: done")

    finally:
        cur.close()
