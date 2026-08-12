"""
Body Sync Fitness - Database Models
Comprehensive models for user progression, exercises, and social features
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import sqlite3
import json
import hashlib
import secrets


import os

class Database:
    """Main database handler for the Body Sync Fitness System"""
    
    def __init__(self, db_path: str = None):
        if not db_path:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fitness_hunter.db")
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Create a new database connection with high-performance PRAGMAs"""
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA temp_store=MEMORY;")
            conn.execute("PRAGMA cache_size=-64000;")
        except Exception:
            pass
        return conn
    
    def init_database(self):
        """Initialize all database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP,
                reset_code TEXT,
                reset_code_expires TIMESTAMP,
                is_admin INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute("PRAGMA table_info(users)")
        cols = [col[1] for col in cursor.fetchall()]
        if 'reset_code' not in cols:
            cursor.execute("ALTER TABLE users ADD COLUMN reset_code TEXT")
        if 'reset_code_expires' not in cols:
            cursor.execute("ALTER TABLE users ADD COLUMN reset_code_expires TIMESTAMP")
        if 'is_admin' not in cols:
            cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
        
        # Player stats table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS player_stats (
                user_id INTEGER PRIMARY KEY,
                age INTEGER,
                height_cm REAL,
                weight_kg REAL,
                initial_height REAL,
                initial_weight REAL,
                target_height REAL,
                target_weight REAL,
                level INTEGER DEFAULT 1,
                exp INTEGER DEFAULT 0,
                exp_to_next_level INTEGER DEFAULT 100,
                stat_points INTEGER DEFAULT 0,
                strength INTEGER DEFAULT 10,
                endurance INTEGER DEFAULT 10,
                agility INTEGER DEFAULT 10,
                vitality INTEGER DEFAULT 10,
                primary_focus_areas TEXT,
                experience_level TEXT DEFAULT 'beginner',
                days_per_week INTEGER DEFAULT 5,
                body_type TEXT DEFAULT 'mesomorph',
                injuries TEXT DEFAULT 'None',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        
        # Exercise records table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS exercise_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                exercise_name TEXT NOT NULL,
                category TEXT NOT NULL,
                max_reps INTEGER DEFAULT 0,
                max_weight_kg REAL DEFAULT 0,
                max_duration_seconds INTEGER DEFAULT 0,
                personal_record INTEGER DEFAULT 0,
                difficulty_level INTEGER DEFAULT 1,
                last_performed TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Daily quests table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                quest_date DATE NOT NULL,
                quest_data TEXT NOT NULL,
                completed BOOLEAN DEFAULT 0,
                exp_reward INTEGER DEFAULT 0,
                completed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Quest completions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quest_completions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                quest_id INTEGER,
                exercise_name TEXT,
                reps_completed INTEGER,
                sets_completed INTEGER,
                weight_used REAL,
                duration_seconds INTEGER,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (quest_id) REFERENCES daily_quests(id)
            )
        ''')
        
        # Workout history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workout_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                workout_date DATE NOT NULL,
                total_exercises INTEGER DEFAULT 0,
                total_reps INTEGER DEFAULT 0,
                total_duration_minutes INTEGER DEFAULT 0,
                exp_gained INTEGER DEFAULT 0,
                calories_burned INTEGER DEFAULT 0,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Goals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                goal_type TEXT NOT NULL,
                goal_name TEXT NOT NULL,
                target_value REAL,
                current_value REAL DEFAULT 0,
                deadline DATE,
                priority TEXT DEFAULT 'medium',
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Friends table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS friends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                friend_id INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                accepted_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (friend_id) REFERENCES users(id)
            )
        ''')
        
        # Achievements table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                achievement_name TEXT NOT NULL,
                achievement_type TEXT NOT NULL,
                description TEXT,
                exp_reward INTEGER DEFAULT 0,
                unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Rest days table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rest_schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                rest_day DATE NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Physique analysis / Quest Log table (target-based AI training plans)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS physique_quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                target_name TEXT,
                source_type TEXT DEFAULT 'text',
                image_path TEXT,
                physique_breakdown TEXT,
                quest_log_markdown TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Structured weekly training split, parsed out of a physique Quest Log's
        # "Main Story Quests" section so it can drive the actual daily quests
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weekly_training_plan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                physique_quest_id INTEGER,
                day_of_week INTEGER NOT NULL,
                day_label TEXT,
                focus TEXT,
                is_rest BOOLEAN DEFAULT 0,
                exercises_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (physique_quest_id) REFERENCES physique_quests(id)
            )
        ''')
        
        # Per-user AI API keys (encrypted at rest) so a deployed multi-user
        # site doesn't have to foot everyone's AI usage on one shared key
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                encrypted_gemini_key TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # Penalty Quests table for Penalty Zone survival mode
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS penalty_quests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                status TEXT DEFAULT 'active',
                title TEXT DEFAULT 'WARNING: PENALTY QUEST INITIATED',
                reason TEXT DEFAULT 'Missed Daily System Protocol',
                quest_data TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                cleared_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # Custom Workout Routines Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS custom_routines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                routine_name TEXT NOT NULL,
                split_type TEXT DEFAULT 'Custom',
                description TEXT,
                exercises_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

        # Strength 1RM Calculation Logs Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS strength_calc_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                exercise_name TEXT NOT NULL,
                weight_kg REAL NOT NULL,
                reps INTEGER NOT NULL,
                estimated_1rm REAL NOT NULL,
                benchmark_level TEXT,
                calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        # Performance Indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_quests_user_date ON daily_quests(user_id, quest_date);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_penalty_quests_user_status ON penalty_quests(user_id, status);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_custom_routines_user ON custom_routines(user_id);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_strength_calc_user ON strength_calc_history(user_id);')

        conn.commit()
        conn.close()
        
        # Lightweight migration for existing DBs created before these columns existed
        self._migrate_schema()
    
    def _migrate_schema(self):
        """Add new columns to existing databases without wiping data"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(users)")
        existing_user_cols = {row['name'] for row in cursor.fetchall()}
        if 'is_admin' not in existing_user_cols:
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass

        cursor.execute("PRAGMA table_info(player_stats)")
        existing_cols = {row['name'] for row in cursor.fetchall()}
        
        migrations = {
            'primary_focus_areas': "ALTER TABLE player_stats ADD COLUMN primary_focus_areas TEXT",
            'experience_level': "ALTER TABLE player_stats ADD COLUMN experience_level TEXT DEFAULT 'beginner'",
            'days_per_week': "ALTER TABLE player_stats ADD COLUMN days_per_week INTEGER DEFAULT 5",
            'body_type': "ALTER TABLE player_stats ADD COLUMN body_type TEXT DEFAULT 'mesomorph'",
            'injuries': "ALTER TABLE player_stats ADD COLUMN injuries TEXT DEFAULT 'None'"
        }
        
        for col, sql in migrations.items():
            if col not in existing_cols:
                try:
                    cursor.execute(sql)
                except sqlite3.OperationalError:
                    pass
        
        # Clean up duplicate friends rows before creating unique index
        try:
            cursor.execute('''
                DELETE FROM friends WHERE id NOT IN (
                    SELECT MIN(id) FROM friends GROUP BY user_id, friend_id
                )
            ''')
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_friends_user_friend 
                ON friends(user_id, friend_id)
            ''')
        except sqlite3.OperationalError:
            pass
            
        conn.commit()
        conn.close()


class User:
    """User authentication and management"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def hash_password(self, password: str, salt: Optional[str] = None) -> str:
        """Hash password using PBKDF2 HMAC SHA-256 with a random salt"""
        if not salt:
            salt = secrets.token_hex(16)
        key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
        return f"pbkdf2:sha256:100000${salt}${key.hex()}"

    def verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify password against stored hash (supports PBKDF2 and legacy plain SHA-256)"""
        if stored_hash.startswith("pbkdf2:sha256:"):
            try:
                parts = stored_hash.split('$')
                if len(parts) == 3:
                    _, salt, key_hex = parts
                    recomputed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
                    return secrets.compare_digest(recomputed, key_hex)
            except Exception:
                return False
        # Legacy plain SHA-256 check
        legacy_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
        return secrets.compare_digest(legacy_hash, stored_hash)

    def create_user(self, username: str, email: str, password: str) -> Optional[int]:
        """Create a new user account"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            password_hash = self.hash_password(password)
            cursor.execute(
                'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                (username, email, password_hash)
            )
            conn.commit()
            user_id = cursor.lastrowid
            conn.close()
            return user_id
        except sqlite3.IntegrityError:
            conn.close()
            return None
    
    def authenticate(self, username_or_email: str, password: str) -> Optional[Dict]:
        """Authenticate user by username or email (case-insensitive)"""
        if not username_or_email or not password:
            return None
            
        clean_input = username_or_email.strip()
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM users 
            WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)
        ''', (clean_input, clean_input))
        user = cursor.fetchone()
        
        if user and self.verify_password(password, user['password_hash']):
            # Auto-upgrade legacy hash if needed
            if not user['password_hash'].startswith("pbkdf2:sha256:"):
                new_hash = self.hash_password(password)
                cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, user['id']))
            cursor.execute(
                'UPDATE users SET last_login = ? WHERE id = ?',
                (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user['id'])
            )
            conn.commit()
            conn.close()
            return dict(user)
        
        conn.close()
        return None
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username (case-insensitive)"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE LOWER(username) = LOWER(?)', (username.strip(),))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None

    def get_user_by_username_or_email(self, username_or_email: str) -> Optional[Dict]:
        """Get user by username or email (case-insensitive)"""
        if not username_or_email:
            return None
        clean_input = username_or_email.strip()
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM users 
            WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)
        ''', (clean_input, clean_input))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email (case-insensitive)"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(?)', (email.strip(),))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user by ID"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None

    def ensure_admin_user(self) -> int:
        """Ensure default admin user exists with full privileges & max stats"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM users WHERE is_admin = 1 OR LOWER(username) = 'admin'")
        admin = cursor.fetchone()
        
        stats_mgr = PlayerStats(self.db)
        if admin:
            user_id = admin['id']
            if not admin['is_admin']:
                cursor.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (user_id,))
                conn.commit()
            conn.close()
            
            if not stats_mgr.get_player_stats(user_id):
                stats_mgr.create_player_stats(user_id, age=25, height_cm=185.0, weight_kg=80.0)
            stats_mgr.grant_god_mode(user_id)
            return user_id
        
        # Create default admin user
        password_hash = self.hash_password("adminpassword123")
        cursor.execute(
            'INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, 1)',
            ("admin", "admin@bodysync.com", password_hash)
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        
        stats_mgr.create_player_stats(user_id, age=25, height_cm=185.0, weight_kg=80.0)
        stats_mgr.grant_god_mode(user_id)
        try:
            print(f"👑 Admin user created and granted God Mode stats (ID: {user_id}, Username: admin)")
        except UnicodeEncodeError:
            print(f"Admin user created and granted God Mode stats (ID: {user_id}, Username: admin)")
        return user_id

    def get_all_users(self, search_query: Optional[str] = None) -> List[Dict]:
        """Get all users with stats, rank, and admin status"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        if search_query:
            q = f"%{search_query.strip().lower()}%"
            cursor.execute('''
                SELECT u.id, u.username, u.email, u.created_at, u.last_login, COALESCE(u.is_admin, 0) as is_admin,
                       ps.level, ps.exp, ps.exp_to_next_level, ps.stat_points,
                       ps.strength, ps.endurance, ps.agility, ps.vitality
                FROM users u
                LEFT JOIN player_stats ps ON u.id = ps.user_id
                WHERE LOWER(u.username) LIKE ? OR LOWER(u.email) LIKE ?
                ORDER BY u.id ASC
            ''', (q, q))
        else:
            cursor.execute('''
                SELECT u.id, u.username, u.email, u.created_at, u.last_login, COALESCE(u.is_admin, 0) as is_admin,
                       ps.level, ps.exp, ps.exp_to_next_level, ps.stat_points,
                       ps.strength, ps.endurance, ps.agility, ps.vitality
                FROM users u
                LEFT JOIN player_stats ps ON u.id = ps.user_id
                ORDER BY u.id ASC
            ''')
            
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def update_user_admin(self, user_id: int, username: str, email: str, is_admin: int) -> bool:
        """Update basic user profile details & admin role"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                UPDATE users
                SET username = ?, email = ?, is_admin = ?
                WHERE id = ?
            ''', (username.strip(), email.strip().lower(), 1 if is_admin else 0, user_id))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False

    def reset_password_admin(self, user_id: int, new_password: str) -> bool:
        """Admin force password reset for any user"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        new_hash = self.hash_password(new_password)
        cursor.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, user_id))
        conn.commit()
        conn.close()
        return True

    def delete_user_cascade(self, user_id: int) -> bool:
        """Completely delete user and clean up all related database tables"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        tables = [
            'player_stats', 'exercise_records', 'daily_quests', 'quest_completions',
            'workout_history', 'goals', 'friends', 'achievements', 'rest_schedule',
            'physique_quests', 'weekly_training_plan', 'user_settings'
        ]
        for tbl in tables:
            try:
                cursor.execute(f'DELETE FROM {tbl} WHERE user_id = ?', (user_id,))
            except sqlite3.OperationalError:
                pass
        
        try:
            cursor.execute('DELETE FROM friends WHERE friend_id = ?', (user_id,))
        except sqlite3.OperationalError:
            pass

        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True


class PlayerStats:
    """Player statistics and progression management"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create_player_stats(self, user_id: int, age: int, height_cm: float, 
                           weight_kg: float, target_height: float = None,
                           target_weight: float = None,
                           primary_focus_areas: List[str] = None,
                           experience_level: str = 'beginner',
                           days_per_week: int = 5,
                           body_type: str = 'mesomorph',
                           injuries: str = 'None') -> bool:
        """Create initial player stats"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO player_stats 
                (user_id, age, height_cm, weight_kg, initial_height, initial_weight,
                 target_height, target_weight, primary_focus_areas, experience_level,
                 days_per_week, body_type, injuries)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, age, height_cm, weight_kg, height_cm, weight_kg,
                  target_height or height_cm, target_weight or weight_kg,
                  json.dumps(primary_focus_areas or []), experience_level,
                  days_per_week, body_type, injuries or 'None'))
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False
    
    def get_primary_focus_areas(self, user_id: int) -> List[str]:
        """Get the user's selected primary objective paths (multi-select goals)"""
        stats = self.get_player_stats(user_id)
        if not stats or not stats.get('primary_focus_areas'):
            return []
        try:
            return json.loads(stats['primary_focus_areas'])
        except (json.JSONDecodeError, TypeError):
            return []
    
    def update_primary_focus_areas(self, user_id: int, focus_areas: List[str]) -> bool:
        """Update the user's selected primary objective paths"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE player_stats 
            SET primary_focus_areas = ?, updated_at = ?
            WHERE user_id = ?
        ''', (json.dumps(focus_areas), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id))
        
        return True
    
    def get_player_stats(self, user_id: int) -> Optional[Dict]:
        """Get player stats by user_id"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM player_stats WHERE user_id = ?', (user_id,))
        stats = cursor.fetchone()
        conn.close()
        return dict(stats) if stats else None

    def update_player_stats_admin(self, user_id: int, level: Optional[int] = None, exp: Optional[int] = None,
                                  exp_to_next_level: Optional[int] = None, stat_points: Optional[int] = None,
                                  strength: Optional[int] = None, endurance: Optional[int] = None,
                                  agility: Optional[int] = None, vitality: Optional[int] = None) -> bool:
        """Directly update player stats values (Admin control)"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM player_stats WHERE user_id = ?', (user_id,))
        stats = cursor.fetchone()
        
        if not stats:
            conn.close()
            self.create_player_stats(user_id, age=25, height_cm=180.0, weight_kg=75.0)
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM player_stats WHERE user_id = ?', (user_id,))
            stats = cursor.fetchone()
            
        new_level = level if level is not None else stats['level']
        new_exp = exp if exp is not None else stats['exp']
        new_exp_next = exp_to_next_level if exp_to_next_level is not None else (new_level * 100)
        new_pts = stat_points if stat_points is not None else stats['stat_points']
        new_str = strength if strength is not None else stats['strength']
        new_end = endurance if endurance is not None else stats['endurance']
        new_agi = agility if agility is not None else stats['agility']
        new_vit = vitality if vitality is not None else stats['vitality']
        
        cursor.execute('''
            UPDATE player_stats
            SET level = ?, exp = ?, exp_to_next_level = ?, stat_points = ?,
                strength = ?, endurance = ?, agility = ?, vitality = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (new_level, new_exp, new_exp_next, new_pts, new_str, new_end, new_agi, new_vit, user_id))
        
        conn.commit()
        conn.close()
        return True

    def grant_god_mode(self, user_id: int) -> bool:
        """Grant God Mode / Max stats to user: Level 100, 500 stat points, 100 all stats"""
        return self.update_player_stats_admin(
            user_id=user_id,
            level=100,
            exp=99999,
            exp_to_next_level=10000,
            stat_points=500,
            strength=100,
            endurance=100,
            agility=100,
            vitality=100
        )
    
    def add_exp(self, user_id: int, exp_amount: int) -> Dict:
        """Add experience and handle leveling up"""
        stats = self.get_player_stats(user_id)
        if not stats:
            return {'leveled_up': False}
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        new_exp = stats['exp'] + exp_amount
        level = stats['level']
        exp_to_next = stats['exp_to_next_level']
        leveled_up = False
        levels_gained = 0
        stat_points = stats['stat_points']
        
        # Check for level ups
        while new_exp >= exp_to_next:
            new_exp -= exp_to_next
            level += 1
            levels_gained += 1
            stat_points += 5  # 5 stat points per level
            exp_to_next = int(exp_to_next * 1.15)  # 15% increase per level
            leveled_up = True
        
        cursor.execute('''
            UPDATE player_stats 
            SET exp = ?, level = ?, exp_to_next_level = ?, stat_points = ?, updated_at = ?
            WHERE user_id = ?
        ''', (new_exp, level, exp_to_next, stat_points, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id))
        
        conn.commit()
        conn.close()
        
        return {
            'leveled_up': leveled_up,
            'levels_gained': levels_gained,
            'new_level': level,
            'current_exp': new_exp,
            'exp_to_next': exp_to_next,
            'stat_points': stat_points
        }

    def deduct_exp(self, user_id: int, exp_amount: int) -> Dict:
        """Deduct experience if a user unchecks a set or exercise"""
        stats = self.get_player_stats(user_id)
        if not stats:
            return {'leveled_up': False}
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        new_exp = max(0, stats['exp'] - exp_amount)
        
        cursor.execute('''
            UPDATE player_stats 
            SET exp = ?, updated_at = ?
            WHERE user_id = ?
        ''', (new_exp, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id))
        
        conn.commit()
        conn.close()
        
        return {
            'leveled_up': False,
            'levels_gained': 0,
            'new_level': stats['level'],
            'current_exp': new_exp,
            'exp_to_next': stats['exp_to_next_level'],
            'stat_points': stats['stat_points']
        }
    
    def allocate_stat_points(self, user_id: int, strength: int = 0, 
                            endurance: int = 0, agility: int = 0, 
                            vitality: int = 0) -> bool:
        """Allocate stat points"""
        stats = self.get_player_stats(user_id)
        if not stats:
            return False
        
        total_points = strength + endurance + agility + vitality
        if total_points > stats['stat_points']:
            return False
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE player_stats 
            SET strength = strength + ?, 
                endurance = endurance + ?,
                agility = agility + ?,
                vitality = vitality + ?,
                stat_points = stat_points - ?,
                updated_at = ?
            WHERE user_id = ?
        ''', (strength, endurance, agility, vitality, total_points, 
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id))
        
        conn.commit()
        conn.close()
        return True
    
    def update_body_measurements(self, user_id: int, height_cm: float = None,
                                 weight_kg: float = None) -> bool:
        """Update body measurements"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if height_cm is not None:
            updates.append('height_cm = ?')
            params.append(height_cm)
        
        if weight_kg is not None:
            updates.append('weight_kg = ?')
            params.append(weight_kg)
        
        if not updates:
            return False
        
        updates.append('updated_at = ?')
        params.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        params.append(user_id)
        
        query = f"UPDATE player_stats SET {', '.join(updates)} WHERE user_id = ?"
        cursor.execute(query, params)
        
        conn.commit()
        conn.close()
        return True


class ExerciseManager:
    """Exercise tracking and progression"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def add_or_update_exercise(self, user_id: int, exercise_name: str,
                               category: str, max_reps: int = 0,
                               max_weight_kg: float = 0,
                               max_duration_seconds: int = 0) -> bool:
        """Add or update exercise record"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Check if exercise exists
        cursor.execute('''
            SELECT id, personal_record FROM exercise_records 
            WHERE user_id = ? AND exercise_name = ?
        ''', (user_id, exercise_name))
        existing = cursor.fetchone()
        
        if existing:
            # Query current metrics safely without nested cursor call
            cursor.execute('''
                SELECT max_reps, max_weight_kg, max_duration_seconds FROM exercise_records WHERE id = ?
            ''', (existing['id'],))
            current = cursor.fetchone()
            curr_max_reps = (current['max_reps'] or 0) if current else 0
            curr_max_weight = (current['max_weight_kg'] or 0.0) if current else 0.0
            curr_max_duration = (current['max_duration_seconds'] or 0) if current else 0
            
            updated_reps = max(max_reps, curr_max_reps)
            updated_weight = max(max_weight_kg, curr_max_weight)
            updated_duration = max(max_duration_seconds, curr_max_duration)
            new_pr = max(updated_reps, updated_duration)
            old_pr = existing['personal_record'] or 0
            
            cursor.execute('''
                UPDATE exercise_records 
                SET max_reps = ?, max_weight_kg = ?, max_duration_seconds = ?,
                    personal_record = ?, last_performed = ?
                WHERE id = ?
            ''', (updated_reps, updated_weight, updated_duration, max(new_pr, old_pr),
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S'), existing['id']))
        else:
            # Insert new exercise
            cursor.execute('''
                INSERT INTO exercise_records 
                (user_id, exercise_name, category, max_reps, max_weight_kg,
                 max_duration_seconds, personal_record, last_performed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, exercise_name, category, max_reps, max_weight_kg,
                  max_duration_seconds, max(max_reps, max_duration_seconds),
                  datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        
        conn.commit()
        conn.close()
        return True
    
    def get_user_exercises(self, user_id: int) -> List[Dict]:
        """Get all exercises for a user"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM exercise_records WHERE user_id = ?
            ORDER BY category, exercise_name
        ''', (user_id,))
        exercises = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return exercises
    
    def get_exercise_by_name(self, user_id: int, exercise_name: str) -> Optional[Dict]:
        """Get specific exercise record"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM exercise_records 
            WHERE user_id = ? AND exercise_name = ?
        ''', (user_id, exercise_name))
        exercise = cursor.fetchone()
        conn.close()
        return dict(exercise) if exercise else None


class WeeklyPlanManager:
    """
    Stores and serves the structured weekly training split generated from
    an active "Become Like..." physique Quest Log, so the daily quest
    generator can build each day's quest directly from that plan instead
    of the generic algorithmic exercise picker.
    """

    def __init__(self, db: Database):
        self.db = db

    def save_weekly_plan(self, user_id: int, physique_quest_id: int,
                          days: List[Dict]) -> bool:
        """
        Replace the user's active weekly plan. `days` is a list of dicts:
        {day_of_week: 0-6 (Mon-Sun), day_label, focus, is_rest, exercises: [...]}
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Clear any previous plan (only one active build-goal plan at a time)
        cursor.execute('DELETE FROM weekly_training_plan WHERE user_id = ?', (user_id,))

        for day in days:
            cursor.execute('''
                INSERT INTO weekly_training_plan
                (user_id, physique_quest_id, day_of_week, day_label, focus,
                 is_rest, exercises_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, physique_quest_id, day.get('day_of_week'),
                  day.get('day_label'), day.get('focus'),
                  1 if day.get('is_rest') else 0,
                  json.dumps(day.get('exercises', []))))

        conn.commit()
        conn.close()
        return True

    def get_plan_for_today(self, user_id: int) -> Optional[Dict]:
        """Get today's entry from the user's active weekly plan, if one exists"""
        today_weekday = datetime.now().weekday()  # Monday=0 ... Sunday=6

        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT w.* FROM weekly_training_plan w
            JOIN physique_quests p ON w.physique_quest_id = p.id
            WHERE w.user_id = ? AND w.day_of_week = ? AND p.is_active = 1
            ORDER BY w.created_at DESC LIMIT 1
        ''', (user_id, today_weekday))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        result = dict(row)
        try:
            result['exercises'] = json.loads(result['exercises_json'])
        except (json.JSONDecodeError, TypeError):
            result['exercises'] = []
        return result

    def get_all_days(self, user_id: int) -> List[Dict]:
        """Get all 7 days of the active weekly plan ordered Monday to Sunday"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT w.* FROM weekly_training_plan w
            JOIN physique_quests p ON w.physique_quest_id = p.id
            WHERE w.user_id = ? AND p.is_active = 1
            ORDER BY w.day_of_week ASC
        ''', (user_id,))
        rows = cursor.fetchall()
        conn.close()

        days = []
        for row in rows:
            day_dict = dict(row)
            try:
                day_dict['exercises'] = json.loads(day_dict['exercises_json'])
            except (json.JSONDecodeError, TypeError):
                day_dict['exercises'] = []
            days.append(day_dict)
        return days

    def has_active_plan(self, user_id: int) -> bool:
        """Check whether the user currently has any structured weekly plan saved"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as cnt FROM weekly_training_plan WHERE user_id = ?',
                       (user_id,))
        count = cursor.fetchone()['cnt']
        conn.close()
        return count > 0

    def clear_plan(self, user_id: int) -> bool:
        """Remove the user's weekly plan (e.g. when they deactivate a build goal)"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM weekly_training_plan WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True


class UserSettings:
    """
    Per-user settings, primarily their personal AI API key so a deployed,
    multi-user site doesn't require the site owner to pay for everyone's
    AI usage on one shared key. Keys are encrypted at rest.
    """

    def __init__(self, db: Database):
        self.db = db

    def save_gemini_key(self, user_id: int, plaintext_key: str) -> bool:
        """Encrypt and store the user's personal Gemini API key"""
        from crypto_utils import encrypt_value

        encrypted = encrypt_value(plaintext_key)

        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_settings (user_id, encrypted_gemini_key, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                encrypted_gemini_key = excluded.encrypted_gemini_key,
                updated_at = excluded.updated_at
        ''', (user_id, encrypted, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()
        return True

    def get_gemini_key(self, user_id: int) -> Optional[str]:
        """Retrieve and decrypt the user's personal Gemini API key, if set"""
        from crypto_utils import decrypt_value

        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT encrypted_gemini_key FROM user_settings WHERE user_id = ?',
                       (user_id,))
        row = cursor.fetchone()
        conn.close()

        if not row or not row['encrypted_gemini_key']:
            return None

        try:
            return decrypt_value(row['encrypted_gemini_key'])
        except Exception:
            return None

    def has_gemini_key(self, user_id: int) -> bool:
        return self.get_gemini_key(user_id) is not None

    def delete_gemini_key(self, user_id: int) -> bool:
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM user_settings WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        return True


def get_hunter_rank(level: int) -> Dict[str, str]:
    """Calculate Solo Leveling Hunter Rank details based on user level"""
    if level >= 100:
        return {
            'rank': 'S-Rank',
            'title': 'National Level Hunter (Shadow Monarch)',
            'badge_color': '#a855f7',
            'glow': '0 0 20px rgba(168, 85, 247, 0.8)',
            'border_color': '#c084fc'
        }
    elif level >= 90:
        return {
            'rank': 'S-Rank',
            'title': 'S-Rank High Hunter',
            'badge_color': '#eab308',
            'glow': '0 0 15px rgba(234, 179, 8, 0.8)',
            'border_color': '#fde047'
        }
    elif level >= 70:
        return {
            'rank': 'A-Rank',
            'title': 'A-Rank Elite Hunter',
            'badge_color': '#3b82f6',
            'glow': '0 0 15px rgba(59, 130, 246, 0.7)',
            'border_color': '#60a5fa'
        }
    elif level >= 45:
        return {
            'rank': 'B-Rank',
            'title': 'B-Rank Veteran Hunter',
            'badge_color': '#10b981',
            'glow': '0 0 12px rgba(16, 185, 129, 0.6)',
            'border_color': '#34d399'
        }
    elif level >= 25:
        return {
            'rank': 'C-Rank',
            'title': 'C-Rank Skilled Hunter',
            'badge_color': '#06b6d4',
            'glow': '0 0 10px rgba(6, 182, 212, 0.5)',
            'border_color': '#22d3ee'
        }
    elif level >= 10:
        return {
            'rank': 'D-Rank',
            'title': 'D-Rank Novice Hunter',
            'badge_color': '#f97316',
            'glow': '0 0 8px rgba(249, 115, 22, 0.5)',
            'border_color': '#fb923c'
        }
    else:
        return {
            'rank': 'E-Rank',
            'title': 'E-Rank Weakest Hunter',
            'badge_color': '#94a3b8',
            'glow': '0 0 5px rgba(148, 163, 184, 0.4)',
            'border_color': '#cbd5e1'
        }


class PenaltyManager:
    """Manages Solo Leveling Penalty Zone quests triggered by missed daily protocols"""

    def __init__(self, db: Database):
        self.db = db

    def get_active_penalty(self, user_id: int) -> Optional[Dict]:
        """Check if user currently has an active Penalty Zone quest"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM penalty_quests
            WHERE user_id = ? AND status = 'active'
            ORDER BY id DESC LIMIT 1
        ''', (user_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        penalty = dict(row)
        try:
            expires_at = datetime.strptime(penalty['expires_at'], '%Y-%m-%d %H:%M:%S')
            if datetime.now() > expires_at:
                cursor.execute("UPDATE penalty_quests SET status = 'failed' WHERE id = ?", (penalty['id'],))
                conn.commit()
                conn.close()
                penalty['status'] = 'failed'
                return penalty
        except Exception:
            pass

        conn.close()
        if isinstance(penalty.get('quest_data'), str):
            try:
                penalty['quest_data'] = json.loads(penalty['quest_data'])
            except Exception:
                pass
        return penalty

    def create_penalty(self, user_id: int, quest_data: Dict, duration_hours: int = 4, reason: str = "Missed Daily Workout Protocol") -> Dict:
        """Create a new Penalty Zone quest for the user"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute("UPDATE penalty_quests SET status = 'failed' WHERE user_id = ? AND status = 'active'", (user_id,))

        expires_at = (datetime.now() + timedelta(hours=duration_hours)).strftime('%Y-%m-%d %H:%M:%S')
        quest_data_json = json.dumps(quest_data)

        cursor.execute('''
            INSERT INTO penalty_quests (user_id, status, title, reason, quest_data, expires_at)
            VALUES (?, 'active', 'WARNING: PENALTY QUEST INITIATED', ?, ?, ?)
        ''', (user_id, reason, quest_data_json, expires_at))

        penalty_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return {
            'id': penalty_id,
            'user_id': user_id,
            'status': 'active',
            'title': 'WARNING: PENALTY QUEST INITIATED',
            'reason': reason,
            'quest_data': quest_data,
            'expires_at': expires_at
        }

    def clear_penalty(self, penalty_id: int, user_id: int) -> bool:
        """Mark penalty as successfully completed and cleared"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE penalty_quests
            SET status = 'cleared', cleared_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
        ''', (penalty_id, user_id))
        conn.commit()
        conn.close()
        return True


class StrengthCalculator:
    """Calculator for 1-Rep Max (1RM), working weight percentages, and strength benchmarks"""

    @staticmethod
    def calculate_1rm(weight: float, reps: int) -> Dict[str, float]:
        """Calculate estimated 1-Rep Max using standard exercise science formulas"""
        if reps <= 0 or weight <= 0:
            return {'epley': 0.0, 'brzycki': 0.0, 'lander': 0.0, 'mayhew': 0.0, 'average': 0.0}

        if reps == 1:
            return {'epley': weight, 'brzycki': weight, 'lander': weight, 'mayhew': weight, 'average': weight}

        epley = weight * (1 + reps / 30.0)
        brzycki = weight * (36.0 / (37.0 - reps)) if reps < 37 else weight * 1.5
        lander = (100.0 * weight) / (101.3 - 2.67123 * reps) if (101.3 - 2.67123 * reps) > 0 else epley

        import math
        mayhew = (100.0 * weight) / (52.2 + (41.9 * math.exp(-0.055 * reps)))

        avg = (epley + brzycki + lander + mayhew) / 4.0

        return {
            'epley': round(epley, 1),
            'brzycki': round(brzycki, 1),
            'lander': round(lander, 1),
            'mayhew': round(mayhew, 1),
            'average': round(avg, 1)
        }

    @staticmethod
    def get_working_percentages(one_rep_max: float) -> List[Dict]:
        """Get working weight percentages for training programs"""
        return [
            {'percentage': 100, 'reps': '1 Rep (Max)', 'weight': round(one_rep_max, 1), 'intensity': 'Maximal'},
            {'percentage': 95, 'reps': '2 Reps', 'weight': round(one_rep_max * 0.95, 1), 'intensity': 'Heavy Power'},
            {'percentage': 90, 'reps': '3-4 Reps', 'weight': round(one_rep_max * 0.90, 1), 'intensity': 'Heavy Strength'},
            {'percentage': 85, 'reps': '5-6 Reps', 'weight': round(one_rep_max * 0.85, 1), 'intensity': 'Strength / Hypertrophy'},
            {'percentage': 80, 'reps': '7-8 Reps', 'weight': round(one_rep_max * 0.80, 1), 'intensity': 'Hypertrophy Focus'},
            {'percentage': 75, 'reps': '9-10 Reps', 'weight': round(one_rep_max * 0.75, 1), 'intensity': 'Moderate / Hypertrophy'},
            {'percentage': 70, 'reps': '12-15 Reps', 'weight': round(one_rep_max * 0.70, 1), 'intensity': 'Endurance / Volume'},
            {'percentage': 60, 'reps': '15-20 Reps', 'weight': round(one_rep_max * 0.60, 1), 'intensity': 'Light / Speed Work'}
        ]

    @staticmethod
    def get_strength_benchmark(exercise_name: str, bodyweight_kg: float, estimated_1rm: float) -> Dict[str, str]:
        """Determine strength tier (Untrained, Novice, Intermediate, Advanced, Elite) relative to bodyweight"""
        if bodyweight_kg <= 0 or estimated_1rm <= 0:
            return {'tier': 'Untrained', 'ratio': 0.0, 'color': '#94a3b8'}

        ratio = estimated_1rm / bodyweight_kg
        ex = (exercise_name or '').lower()

        if 'squat' in ex:
            benchmarks = [(0.75, 'Untrained', '#94a3b8'), (1.2, 'Novice', '#3b82f6'), (1.5, 'Intermediate', '#10b981'), (2.0, 'Advanced', '#f59e0b'), (2.5, 'Elite', '#a855f7')]
        elif 'deadlift' in ex:
            benchmarks = [(1.0, 'Untrained', '#94a3b8'), (1.5, 'Novice', '#3b82f6'), (1.8, 'Intermediate', '#10b981'), (2.4, 'Advanced', '#f59e0b'), (3.0, 'Elite', '#a855f7')]
        elif ('press' in ex and 'overhead' in ex) or 'shoulder' in ex:
            benchmarks = [(0.35, 'Untrained', '#94a3b8'), (0.55, 'Novice', '#3b82f6'), (0.75, 'Intermediate', '#10b981'), (1.0, 'Advanced', '#f59e0b'), (1.25, 'Elite', '#a855f7')]
        else:
            benchmarks = [(0.5, 'Untrained', '#94a3b8'), (0.8, 'Novice', '#3b82f6'), (1.1, 'Intermediate', '#10b981'), (1.5, 'Advanced', '#f59e0b'), (1.9, 'Elite', '#a855f7')]

        tier = 'Untrained'
        color = '#94a3b8'
        for min_ratio, tier_label, tier_color in benchmarks:
            if ratio >= min_ratio:
                tier = tier_label
                color = tier_color

        return {
            'tier': tier,
            'ratio': round(ratio, 2),
            'color': color
        }


class RoutineManager:
    """Manages custom workout split routines created by users"""

    def __init__(self, db: Database):
        self.db = db

    def create_routine(self, user_id: int, routine_name: str, split_type: str, exercises: List[Dict], description: str = "") -> Dict:
        conn = self.db.get_connection()
        cursor = conn.cursor()
        exercises_json = json.dumps(exercises)
        cursor.execute('''
            INSERT INTO custom_routines (user_id, routine_name, split_type, description, exercises_json)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, routine_name, split_type, description, exercises_json))
        routine_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return {
            'id': routine_id,
            'user_id': user_id,
            'routine_name': routine_name,
            'split_type': split_type,
            'description': description,
            'exercises': exercises
        }

    def get_user_routines(self, user_id: int) -> List[Dict]:
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM custom_routines
            WHERE user_id = ?
            ORDER BY id DESC
        ''', (user_id,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        for r in rows:
            if isinstance(r.get('exercises_json'), str):
                try:
                    r['exercises'] = json.loads(r['exercises_json'])
                except Exception:
                    r['exercises'] = []
        return rows

    def get_routine_by_id(self, routine_id: int, user_id: int) -> Optional[Dict]:
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM custom_routines
            WHERE id = ? AND user_id = ?
        ''', (routine_id, user_id))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        r = dict(row)
        if isinstance(r.get('exercises_json'), str):
            try:
                r['exercises'] = json.loads(r['exercises_json'])
            except Exception:
                r['exercises'] = []
        return r

    def delete_routine(self, routine_id: int, user_id: int) -> bool:
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM custom_routines
            WHERE id = ? AND user_id = ?
        ''', (routine_id, user_id))
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected > 0

    def log_1rm_test(self, user_id: int, exercise_name: str, weight_kg: float, reps: int, estimated_1rm: float, benchmark_level: str) -> bool:
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO strength_calc_history (user_id, exercise_name, weight_kg, reps, estimated_1rm, benchmark_level)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, exercise_name, weight_kg, reps, estimated_1rm, benchmark_level))
        conn.commit()
        conn.close()
        return True

    def get_1rm_history(self, user_id: int) -> List[Dict]:
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM strength_calc_history
            WHERE user_id = ?
            ORDER BY calculated_at DESC
            LIMIT 20
        ''', (user_id,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows


