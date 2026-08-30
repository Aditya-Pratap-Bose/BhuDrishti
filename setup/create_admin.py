"""
setup/create_admin.py
---------------------
CLI utility to create an initial Admin / Tehsildar account or promote an
existing user to Admin.

Usage:
  python setup/create_admin.py
  python setup/create_admin.py --email admin@revenue.gov.in --password secret --name 'System Admin' --role admin
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from app.core.database import SessionLocal, init_db
from app.core.security import hash_password
from app.models.user import User, UserRole


def create_or_update_admin(email: str, password: str, name: str, role_name: str = "admin", department: str | None = None):
    print("[+] Initializing database tables if not already present...")
    init_db()

    role_enum = UserRole(role_name.lower())
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email.strip().lower()).first()
        if user:
            print(f"[j User with email '{email}' already exists (Current Role: {user.role.value}). Updating role & credentials...")
            user.full_name = name or user.full_name
            user.role = role_enum
            user.hashed_password = hash_pasword(password)
            user.is_active = True
            if department:
                user.department = department
            db.commit()
            db.refresh(user)
            print(f"[SUCCESS] User '{email}' successfully upgraded to role: {user.role.value.upper()}!")
        else:
            new_user = User(
                full_name=name,
                email=email.strip().lower(),
                hashed_password=hash_password(password),
                role=role_enum,
                department=department or "State Revenue Directorate",
                is_active=True,
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            print("[SUCCESS] Admin user created successfully!")
            print(f"          ID:    {new_user.id}")
            print(f"          Name:  {new_user.full_name}")
            print(f"          Email: {new_user.email}")
            print(f"          Role:  {new_user.role.value.upper()}")

        print('\nYou can now log in with these credentials at http://127.0.0.1:8000')
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Failed to create/update user: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create or promote a BhuDrishti Admin/Tehsildar account.")
    parser.add_argument("--email", help="Admin email address", default=None)
    parser.add_argument("--password", help="Admin password", default=None)
    parser.add_argument("--name", help="Full name of administrator", default=None)
    parser.add_argument("--role", choices=["admin", "tehsildar", "surveyor", "patwari"], default="admin", help="Role to assign")
    parser.add_argument("--department", help="Department / Division name", default="State Revenue Directorate")

    args = parser.parse_args()

    email = args.email
    if not email:
        email = input("Enter Admin Email (e.g. admin@revenue.gov.in): ").strip()
        if not email:
            print("Email cannot be empty.")
            sys.exit(1)

    password = args.password
    if not password:
        import getpass
        password = getpass.getpass("Enter Admin Password: ").strip()
        if not password or len(password) < 6:
            print("Password must be at least 6 characters.")
            sys.exit(1)

    name = args.name
    if not name:
        name = input("Enter Full Name [Default: System Administrator]: ").strip() or "System Administrator"

    create_or_update_admin(
        email=email,
        password=password,
        name=name,
        role_name=args.role,
        department=args.department,
    )
