import os
import sys

from auth import bootstrap_admin
from database import init_database


def main():
    init_database()
    name = os.getenv("ADMITCREW_ADMIN_NAME")
    email = os.getenv("ADMITCREW_ADMIN_EMAIL")
    password = os.getenv("ADMITCREW_ADMIN_PASSWORD")
    if not name or not email or not password:
        raise SystemExit(
            "Set ADMITCREW_ADMIN_NAME, ADMITCREW_ADMIN_EMAIL, and "
            "ADMITCREW_ADMIN_PASSWORD before running bootstrap."
        )

    result = bootstrap_admin(name, email, password)
    if result.get("error"):
        messages = {
            "email_belongs_to_non_admin": "The configured email already belongs to a non-admin staff account.",
            "active_admin_already_exists": "An active admin already exists; bootstrap only creates the first admin.",
            "name_required": "Admin name must not be blank.",
            "invalid_email": "Admin email is invalid.",
            "invalid_password": "Admin password must contain 12-1024 UTF-8 bytes.",
        }
        raise SystemExit(messages.get(result["error"], "Admin bootstrap failed."))

    if result["created"]:
        print(f"Initial admin created (staff ID {result['staff_id']}).")
    else:
        print(f"Admin already exists (staff ID {result['staff_id']}).")


if __name__ == "__main__":
    main()
