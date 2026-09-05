"""Set one shared password across all local accounts.

Demoing role-based access means signing in and out as several officers in
quick succession. Six separate generated passwords make that painful, so this
sets them all to one value for a local demonstration database.

Only ever run this against a synthetic-data instance: a shared credential
means role separation stops being a security boundary.

    python scripts_set_demo_password.py [password]
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for pkg in ("backend", "database", "ai", "graph"):
    sys.path.insert(0, str(ROOT / pkg))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password, password_strength_errors  # noqa: E402
from app.db.models import User  # noqa: E402
from app.db.seed import database_identity, write_credentials_file  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

password = sys.argv[1] if len(sys.argv) > 1 else "TrinetraDemo#2026"

errors = password_strength_errors(password)
if errors:
    raise SystemExit("Password rejected by policy:\n  " + "\n  ".join(errors))

db = SessionLocal()
users = db.scalars(select(User)).all()
if not users:
    raise SystemExit("No users found - seed the database first.")

now = datetime.now(UTC)
for user in users:
    user.password_hash = hash_password(password)
    user.password_changed_at = now
    # Clear any lockout left over from failed attempts during testing.
    user.failed_attempts = 0
    user.locked_until = None
db.commit()

print(f"Set a shared password on {len(users)} accounts:\n")
for user in sorted(users, key=lambda u: u.service_id):
    print(f"  {user.service_id:<10} {user.full_name:<20} {user.designation}")
print(f"\nPassword for all accounts: {password}")
print("Lockouts cleared. Synthetic-data instances only.")

# CREDENTIALS.md is what tests, docs and anyone reading the file trust. Leaving
# it holding the previous per-account passwords after this script overwrites
# the database is exactly the stale-credential trap that keeps recurring here.
credentials_path = ROOT / "CREDENTIALS.md"
write_credentials_file({u.service_id: password for u in users}, credentials_path)
print(f"\nCREDENTIALS.md updated to match ({database_identity()}).")
db.close()
