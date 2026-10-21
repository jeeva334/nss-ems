"""One-time creation of the first Admin. Run from backend/:  python -m scripts.bootstrap_admin
Password is read interactively (or BOOTSTRAP_ADMIN_PASSWORD) and never logged."""
import getpass
import os
import sys

from app.core.errors import AppError
from app.db.session import SessionLocal
from app.services.bootstrap_service import create_initial_admin


def main() -> int:
    name = input("Full name: ")
    email = input("Email: ")
    mobile = input("Mobile number: ")
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD") or getpass.getpass("Password: ")
    with SessionLocal() as db:
        try:
            user = create_initial_admin(db, name, email, mobile, password)
        except AppError as e:
            print(f"Error: {e.message}", file=sys.stderr)
            return 1
    print(f"Admin created with Employee ID {user.employee_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
