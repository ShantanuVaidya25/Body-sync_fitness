"""
Body Sync Fitness - Admin Account CLI Utility
Usage:
    python create_admin.py --username admin --email admin@bodysync.com --password adminpassword123
"""

import sys
import os
import argparse

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from models import Database, User, PlayerStats

def main():
    parser = argparse.ArgumentParser(description="Create or promote a user to Admin in Body Sync Fitness.")
    parser.add_argument("--username", type=str, default="admin", help="Username for admin account")
    parser.add_argument("--email", type=str, default="admin@bodysync.com", help="Email for admin account")
    parser.add_argument("--password", type=str, default="adminpassword123", help="Password for admin account")
    parser.add_argument("--god-mode", action="store_true", default=True, help="Grant max stats / Level 100")

    args = parser.parse_args()

    db = Database()
    user_mgr = User(db)
    stats_mgr = PlayerStats(db)

    print(f"⚡ Processing Admin account creation/elevation for: {args.username}...")

    # Check if user exists
    existing = user_mgr.get_user_by_username_or_email(args.username)
    if not existing:
        existing = user_mgr.get_user_by_email(args.email)

    if existing:
        user_id = existing['id']
        user_mgr.update_user_admin(user_id, existing['username'], existing['email'], is_admin=1)
        if args.password:
            user_mgr.reset_password_admin(user_id, args.password)
        print(f"✅ Existing user ID {user_id} ({existing['username']}) successfully promoted to ADMIN!")
    else:
        user_id = user_mgr.create_user(args.username, args.email, args.password)
        if user_id:
            user_mgr.update_user_admin(user_id, args.username, args.email, is_admin=1)
            print(f"✅ New ADMIN account created! ID: {user_id}, Username: {args.username}")
        else:
            print("❌ Error: Could not create admin account.")
            sys.exit(1)

    # Initialize stats if needed
    if not stats_mgr.get_player_stats(user_id):
        stats_mgr.create_player_stats(user_id, age=25, height_cm=185.0, weight_kg=80.0)

    if args.god_mode:
        stats_mgr.grant_god_mode(user_id)
        print("👑 God Mode activated! Level 100, 100 attributes, 500 stat points granted.")

    print("\n🎉 Admin Account Setup Complete!")
    print(f"Username: {args.username}")
    print(f"Email:    {args.email}")
    print(f"Password: {args.password}")

if __name__ == "__main__":
    main()
