#!/usr/bin/env python3
"""
One-off: set platform superuser flag in MariaDB for a user (e.g. soude017).

Reads DATABASE_URL from the environment (same as the app). Optionally load
project-root .env if python-dotenv is installed.

Usage:
  export DATABASE_URL='mysql://user:pass@host:3306/pipeline'
  uv run python scripts/set_superuser_mariadb.py --match soude017

  # Exact user id (from Platform → Users or DB):
  uv run python scripts/set_superuser_mariadb.py --user-id <uuid>

  # Dry run (show who would be updated):
  uv run python scripts/set_superuser_mariadb.py --match soude017 --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from urllib.parse import unquote, urlparse

try:
    import pymysql
except ImportError as e:
    print("Install pymysql (e.g. uv sync / pip install pymysql).", file=sys.stderr)
    raise SystemExit(1) from e

try:
    from dotenv import load_dotenv

    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    load_dotenv(os.path.join(_root, ".env"), override=False)
    load_dotenv(os.path.join(_root, ".env.production"), override=False)
except ImportError:
    pass


def _parse_mysql_url(url: str) -> dict:
    u = urlparse(url.strip())
    if u.scheme not in ("mysql", "mariadb"):
        raise ValueError(f"Expected mysql:// or mariadb:// URL, got scheme={u.scheme!r}")
    user = unquote(u.username or "")
    password = unquote(u.password or "")
    host = u.hostname or "localhost"
    port = int(u.port or 3306)
    db = (u.path or "/").strip("/").split("?")[0]
    if not db:
        raise ValueError("DATABASE_URL must include a database name in the path")
    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": db,
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Set is_superuser=1 for a MariaDB users row.")
    p.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="Override DATABASE_URL env (default: env DATABASE_URL)",
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument(
        "--match",
        metavar="SUBSTRING",
        help="Match users where email, google_id, or name contains this substring (case-insensitive)",
    )
    g.add_argument("--user-id", metavar="UUID", help="Set superuser for this exact users.id")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print matching rows; do not update",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="If multiple rows match --match, abort unless this flag is set (then updates all matches)",
    )
    args = p.parse_args()
    url = (args.database_url or "").strip()
    if not url:
        print("DATABASE_URL is not set. Export it or pass --database-url.", file=sys.stderr)
        raise SystemExit(2)

    conn = pymysql.connect(**_parse_mysql_url(url))
    try:
        with conn.cursor() as cur:
            if args.user_id:
                cur.execute(
                    "SELECT id, email, name, google_id, is_superuser FROM users WHERE id = %s",
                    (args.user_id.strip(),),
                )
                rows = cur.fetchall()
            else:
                needle = f"%{args.match.strip()}%"
                cur.execute(
                    """
                    SELECT id, email, name, google_id, is_superuser
                    FROM users
                    WHERE LOWER(email) LIKE LOWER(%s)
                       OR LOWER(google_id) LIKE LOWER(%s)
                       OR LOWER(name) LIKE LOWER(%s)
                    ORDER BY email
                    """,
                    (needle, needle, needle),
                )
                rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        print("No matching users found.", file=sys.stderr)
        raise SystemExit(3)

    print("Matching users:")
    for r in rows:
        su = "yes" if r.get("is_superuser") else "no"
        print(f"  id={r['id']} email={r['email']!r} name={r['name']!r} superuser={su}")

    if len(rows) > 1 and not args.yes and not args.user_id:
        print(
            "\nMultiple matches. Re-run with --user-id <id> or add --yes to update all listed rows.",
            file=sys.stderr,
        )
        raise SystemExit(4)

    if args.dry_run:
        print("\nDry run: no changes made.")
        return

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    conn2 = pymysql.connect(**_parse_mysql_url(url))
    try:
        with conn2.cursor() as cur:
            for r in rows:
                cur.execute(
                    "UPDATE users SET is_superuser = 1, updated_at = %s WHERE id = %s",
                    (now, r["id"]),
                )
        conn2.commit()
    finally:
        conn2.close()

    print(f"\nUpdated is_superuser=1 for {len(rows)} user(s).")


if __name__ == "__main__":
    main()
