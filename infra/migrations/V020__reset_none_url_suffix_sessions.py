"""
V020 — Reset archive sessions affected by the None url_suffix merging bug

A bug in page_posts_to_entities caused owner.username=None to produce the string
"None/" as url_suffix for extracted accounts. batch_get_canonicals_url_and_id then
matched all such accounts to the same canonical, incorrectly merging distinct accounts
and linking their posts to a single wrong canonical account.

This migration:
  1. Identifies canonical account rows with url_suffix = 'None/'
  2. Removes all FK-dependent rows that block deletion (account_tag, account_relation
     and its archive rows, then nullable FK references set to NULL)
  3. Deletes the bad canonical account rows
  4. Resets the affected archive_sessions to 'parsed' so entity extraction re-runs
     with the fixed extraction code
"""


def run(cnx):
    cur = cnx.cursor()
    try:
        # ------------------------------------------------------------------ #
        # Step 1: Collect bad canonical account IDs
        # ------------------------------------------------------------------ #
        cur.execute("SELECT id FROM account WHERE url_suffix = 'None/'")
        bad_account_ids = [row[0] for row in cur.fetchall()]

        if not bad_account_ids:
            print("    V020: no canonical accounts with url_suffix='None/' found — nothing to do")
            return

        print(f"    V020: found {len(bad_account_ids)} bad canonical account(s) with url_suffix='None/'")
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
        print(f"    V020: {len(affected_session_ids)} archive session(s) will be reset to 'parsed'")

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
            print(f"    V020: deleted {len(bad_relation_ids)} account_relation row(s) and their archives")

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
        print(f"    V020: deleted {len(bad_account_ids)} bad canonical account(s)")

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
            print(f"    V020: reset {cur.rowcount} archive session(s) to 'parsed'")

        cnx.commit()
        print("    V020: done")

    finally:
        cur.close()
