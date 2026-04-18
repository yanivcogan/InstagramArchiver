"""
Admin recovery script: disable 2FA for a user (when they have lost access to their authenticator).
Run from the project root:

    uv run browsing_platform/server/scripts/disable_2fa.py <email>
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from dotenv import load_dotenv
load_dotenv()

from browsing_platform.server.services.token_manager import remove_all_tokens_for_user
from utils import db


def disable_2fa(email: str):
    user = db.execute_query(
        "SELECT id, email, totp_configured FROM user WHERE email = %(e)s",
        {"e": email}, "single_row"
    )
    if not user:
        print(f"Error: no user found with email '{email}'")
        sys.exit(1)

    print(f"User: {user['email']} (id={user['id']}, totp_configured={user['totp_configured']})")
    confirm = input("Type 'yes' to disable 2FA and invalidate all sessions: ")
    if confirm.strip().lower() != "yes":
        print("Aborted.")
        sys.exit(0)

    db.execute_query(
        """UPDATE user
           SET totp_configured = 0,
               totp_secret = NULL,
               totp_pending_secret = NULL,
               totp_last_used_at = NULL
           WHERE id = %(uid)s""",
        {"uid": user["id"]}, "none"
    )
    remove_all_tokens_for_user(user["id"])
    print(f"Done. 2FA disabled and all sessions invalidated for {email}.")
    print("The user will be forced to set up 2FA on next login.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <email>")
        sys.exit(1)
    disable_2fa(sys.argv[1])
