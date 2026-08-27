"""
Body Sync Fitness - Flask Backend API (IMPROVED)
Fixed quest generation with better error handling
"""

from flask import Flask, request, jsonify, session, render_template
from flask_cors import CORS
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.utils import secure_filename
import json
import os
import sys
import uuid
import traceback
import sqlite3

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Database, User, PlayerStats, ExerciseManager, WeeklyPlanManager, UserSettings, PenaltyManager, get_hunter_rank, StrengthCalculator, RoutineManager
from quest_generator import AIQuestGenerator
from physique_analyzer import PhysiqueAnalyzer

app = Flask(__name__, 
            template_folder='../templates',
            static_folder='../static')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-only-insecure-default-change-before-deploying')
if app.secret_key == 'dev-only-insecure-default-change-before-deploying':
    print("⚠️  WARNING: Using the default FLASK_SECRET_KEY. This is fine for local")
    print("   testing, but set a real one via the FLASK_SECRET_KEY environment")
    print("   variable before deploying this publicly (see README).")
CORS(app, supports_credentials=True)

# Initialize database
db = Database()
user_manager = User(db)
stats_manager = PlayerStats(db)
exercise_manager = ExerciseManager(db)
quest_generator = AIQuestGenerator(db)
weekly_plan_manager = WeeklyPlanManager(db)
user_settings = UserSettings(db)
penalty_manager = PenaltyManager(db)
routine_manager = RoutineManager(db)

# Lazy DB initialization for gunicorn/Rust async compatibility
_db_initialized = False

@app.before_request
def initialize_db_once():
    global _db_initialized
    if not _db_initialized:
        db.init_database()
        try:
            user_manager.ensure_admin_user()
        except Exception as e:
            print(f"⚠️ Admin account initialization error: {e}")
        _db_initialized = True

# A server-wide fallback key is OPTIONAL. If the site owner sets
# GEMINI_API_KEY, users without their own key can still use the feature
# (owner absorbs the cost). If not set, each user MUST provide their own
# key via Settings before the "Become Like..." feature works for them.
_fallback_analyzer = PhysiqueAnalyzer()  # uses GEMINI_API_KEY env var if present


def get_analyzer_for_user(uid: int) -> PhysiqueAnalyzer:
    """
    Resolve which AI client to use for this user: their own personal key
    if they've set one in Settings, otherwise the server's shared key (if
    the site owner configured one), otherwise an unconfigured instance
    that will fail gracefully with a clear "add your key" message.
    """
    personal_key = user_settings.get_gemini_key(uid)
    if personal_key:
        return PhysiqueAnalyzer(api_key=personal_key)
    return _fallback_analyzer

# Upload folder for physique reference photos
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}


def allowed_image(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def get_rank_from_level(level) -> str:
    try:
        lvl = int(level) if level is not None else 1
    except (TypeError, ValueError):
        lvl = 1
        
    if lvl >= 100:
        return 'SS-Rank Hunter'
    elif lvl >= 80:
        return 'S-Rank Hunter'
    elif lvl >= 60:
        return 'A-Rank Hunter'
    elif lvl >= 40:
        return 'B-Rank Hunter'
    elif lvl >= 25:
        return 'C-Rank Hunter'
    elif lvl >= 10:
        return 'D-Rank Hunter'
    return 'E-Rank Hunter'


# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/')
def index():
    """Serve main application page"""
    return render_template('index.html')


@app.route('/api/register', methods=['POST'])
def register():
    """Register a new user and automatically log them in"""
    data = request.json or {}
    
    username = (data.get('username') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password')
    
    if not username or not email or not password:
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Specific check for existing username or email
    if user_manager.get_user_by_username(username):
        return jsonify({'error': f"Username '{username}' is already taken. Try logging in."}), 409

    if user_manager.get_user_by_email(email):
        return jsonify({'error': f"Email '{email}' is already registered. Try logging in."}), 409
    
    user_id = user_manager.create_user(username, email, password)
    
    if user_id:
        # Establish session automatically for seamless onboarding
        session['user_id'] = user_id
        session['username'] = username
        session['is_admin'] = False
        print(f"✅ New user registered and logged in: {username} (ID: {user_id})")
        return jsonify({
            'success': True,
            'message': 'Account created successfully!',
            'user_id': user_id,
            'user': {
                'id': user_id,
                'username': username,
                'is_admin': False,
                'has_stats': False
            }
        }), 201
    else:
        return jsonify({'error': 'Username or email already exists'}), 409



@app.route('/api/login', methods=['POST'])
def login():
    """Authenticate user"""
    data = request.json or {}
    
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    
    if not username or not password:
        return jsonify({'error': 'Please enter your username/email and password.'}), 400
    
    # Specific check: if user doesn't exist vs wrong password
    user_record = user_manager.get_user_by_username_or_email(username)
    if not user_record:
        return jsonify({'error': 'Incorrect username or email'}), 401
    
    user = user_manager.authenticate(username, password)
    if not user:
        return jsonify({'error': 'Incorrect password'}), 401
        
    is_admin = bool(user.get('is_admin'))
    session['user_id'] = user['id']
    session['username'] = user['username']
    session['is_admin'] = is_admin
    
    # Get player stats
    stats = stats_manager.get_player_stats(user['id'])
    
    print(f"✅ User logged in: {username} (Admin: {is_admin}, Has stats: {stats is not None})")
    
    return jsonify({
        'success': True,
        'message': 'Welcome back, Hunter!',
        'user': {
            'id': user['id'],
            'username': user['username'],
            'email': user.get('email', ''),
            'is_admin': is_admin,
            'has_stats': stats is not None
        }
    })





@app.route('/api/weekly-activity', methods=['GET'])
def get_weekly_activity():
    """Get 7-day weekly workout activity calendar data with active streak, EXP, and completion metrics"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    user_id = session['user_id']
    conn = db.get_connection()
    cursor = conn.cursor()
    
    today = datetime.now().date()
    days_since_sunday = (today.weekday() + 1) % 7
    sunday = today - timedelta(days=days_since_sunday)
    
    day_codes = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']
    day_names_full = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
    week_days = []
    weekly_active_days = 0
    weekly_exp_earned = 0
    
    for i in range(7):
        current_date = sunday + timedelta(days=i)
        date_str = current_date.strftime('%Y-%m-%d')
        count = 0
        day_exp = 0
        
        # 1. Check daily_quests for completed quests or logged sets
        cursor.execute('''
            SELECT id, completed, quest_data, exp_reward FROM daily_quests 
            WHERE user_id = ? AND (quest_date = ? OR DATE(completed_at) = ?)
        ''', (user_id, date_str, date_str))
        q_rows = cursor.fetchall()
        for qr in q_rows:
            if qr['completed']:
                count += 1
                day_exp += (qr['exp_reward'] or 50)
            else:
                try:
                    q_data = json.loads(qr['quest_data']) if qr['quest_data'] else {}
                    c_sets = len(q_data.get('completed_sets', []))
                    if c_sets > 0:
                        count += 1
                        day_exp += (c_sets * 10)
                except Exception:
                    pass
                    
        # 2. Check quest_completions
        if count == 0:
            cursor.execute('''
                SELECT COUNT(*) FROM quest_completions 
                WHERE user_id = ? AND DATE(completed_at) = ?
            ''', (user_id, date_str))
            c_comp = (cursor.fetchone()[0] or 0)
            if c_comp > 0:
                count += c_comp
                day_exp += (c_comp * 10)
            
        # 3. Check workout_history
        if count == 0:
            cursor.execute('''
                SELECT total_exercises, exp_gained FROM workout_history 
                WHERE user_id = ? AND (workout_date = ? OR DATE(created_at) = ?)
            ''', (user_id, date_str, date_str))
            row = cursor.fetchone()
            if row and row[0]:
                count += row[0]
                day_exp += (row[1] or 50)
                
        is_completed = count > 0
        if is_completed:
            weekly_active_days += 1
        weekly_exp_earned += day_exp
                
        week_days.append({
            'day_code': day_codes[i],
            'day_name': day_names_full[i],
            'day_number': current_date.day,
            'date': date_str,
            'count': count,
            'completed': is_completed,
            'is_today': current_date == today,
            'is_past': current_date < today,
            'is_future': current_date > today,
            'exp_earned': day_exp
        })
        
    stats = stats_manager.get_player_stats(user_id)
    current_level = stats['level'] if stats else 1
    
    # Calculate streak from workout_history and daily_quests
    cursor.execute('''
        SELECT DISTINCT workout_date FROM (
            SELECT workout_date FROM workout_history WHERE user_id = ?
            UNION
            SELECT DATE(completed_at) as workout_date FROM daily_quests WHERE user_id = ? AND completed = 1 AND completed_at IS NOT NULL
        ) ORDER BY workout_date DESC
    ''', (user_id, user_id))
    workout_dates = [r[0] for r in cursor.fetchall() if r[0]]
    
    streak = 0
    curr_check = today
    if workout_dates and workout_dates[0] != today.strftime('%Y-%m-%d'):
        curr_check = today - timedelta(days=1)
        
    for w_date_str in workout_dates:
        if w_date_str == curr_check.strftime('%Y-%m-%d'):
            streak += 1
            curr_check = curr_check - timedelta(days=1)
        else:
            break
            
    cursor.execute('''
        SELECT COUNT(DISTINCT workout_date) FROM workout_history WHERE user_id = ?
    ''', (user_id,))
    hist_days = cursor.fetchone()[0] or 0
    
    cursor.execute('''
        SELECT COUNT(DISTINCT DATE(completed_at)) FROM daily_quests WHERE user_id = ? AND completed = 1
    ''', (user_id,))
    quest_days = cursor.fetchone()[0] or 0
    
    total_completed_days = max(hist_days, quest_days)
    rank_ups = max(0, current_level - 1)
    conn.close()
    
    return jsonify({
        'success': True,
        'rank_ups': rank_ups,
        'current_level': current_level,
        'active_streak': streak,
        'weekly_active_days': weekly_active_days,
        'weekly_total_days': 7,
        'weekly_exp_earned': weekly_exp_earned,
        'week_days': week_days
    })


@app.route('/api/logout', methods=['POST'])
def logout():
    """Logout user"""
    username = session.get('username', 'Unknown')
    session.clear()
    print(f"👋 User logged out: {username}")
    return jsonify({'success': True, 'message': 'Logged out successfully'})


@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    """Check if user is authenticated"""
    if 'user_id' in session:
        user = user_manager.get_user_by_id(session['user_id'])
        if not user:
            session.clear()
            return jsonify({'authenticated': False})
            
        stats = stats_manager.get_player_stats(session['user_id'])
        is_admin = bool(user.get('is_admin'))
        session['is_admin'] = is_admin
        
        return jsonify({
            'authenticated': True,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'email': user.get('email', ''),
                'is_admin': is_admin,
                'has_stats': stats is not None
            }
        })
    else:
        return jsonify({'authenticated': False})


# ============================================================================
# PLAYER STATS ENDPOINTS
# ============================================================================

@app.route('/api/setup-profile', methods=['POST'])
@login_required
def setup_profile():
    """Setup initial player profile"""
    data = request.json
    user_id = session['user_id']
    
    # Get body information
    age = data.get('age')
    height_cm = data.get('height_cm')
    weight_kg = data.get('weight_kg')
    target_height = data.get('target_height')
    target_weight = data.get('target_weight')
    
    # Multi-select "Primary Objective Path" goals + related preferences
    primary_focus_areas = data.get('primary_focus_areas', [])
    experience_level = data.get('experience_level', 'beginner')
    days_per_week = data.get('days_per_week', 5)
    body_type = data.get('body_type', 'mesomorph')
    injuries = data.get('injuries', 'None')
    equipment = data.get('equipment', 'Full Commercial Gym')
    
    if not all([age, height_cm, weight_kg]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    if not primary_focus_areas:
        return jsonify({'error': 'Please select at least one objective from your Primary Objective Path'}), 400
    
    # Create player stats
    success = stats_manager.create_player_stats(
        user_id, age, height_cm, weight_kg,
        target_height, target_weight,
        primary_focus_areas, experience_level, days_per_week,
        body_type, injuries, equipment
    )
    
    if not success:
        return jsonify({'error': 'Profile already exists'}), 409
    
    # Add initial exercises if provided
    initial_exercises = data.get('initial_exercises', [])
    for exercise in initial_exercises:
        exercise_manager.add_or_update_exercise(
            user_id,
            exercise['name'],
            exercise['category'],
            exercise.get('max_reps', 0),
            exercise.get('max_weight', 0),
            exercise.get('max_duration', 0)
        )
    
    # Also persist each selected objective as a tracked goal so it shows
    # up in the Goals tab and factors into long-term progress tracking
    conn = db.get_connection()
    cursor = conn.cursor()
    goal_labels = {
        'strength': 'Build Strength',
        'muscle_gain': 'Gain Muscle',
        'weight_loss': 'Lose Weight',
        'endurance': 'Improve Endurance & Stamina',
        'flexibility': 'Improve Flexibility & Mobility',
        'height_growth': 'Support Height Growth',
        'general_fitness': 'General Fitness & Health',
        'athletic_performance': 'Sport-Specific Athletic Performance'
    }
    for path in primary_focus_areas:
        cursor.execute('''
            INSERT INTO goals (user_id, goal_type, goal_name, target_value, priority)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, path, goal_labels.get(path, path.replace('_', ' ').title()),
              100, 'high'))
    conn.commit()
    conn.close()
    
    # Immediately generate today's quest using the selected objectives so the
    # user has a workout plan waiting the moment setup finishes
    try:
        quest = quest_generator.generate_daily_quest(user_id, [], primary_focus_areas)
        quest_generator.save_daily_quest(user_id, quest)
    except Exception as e:
        print(f"⚠️  Could not pre-generate first quest: {e}")
    
    print(f"✅ Profile created for user {user_id}")
    print(f"   Age: {age}, Height: {height_cm}cm, Weight: {weight_kg}kg")
    print(f"   Objective path: {primary_focus_areas}")
    print(f"   Initial exercises: {len(initial_exercises)}")
    
    return jsonify({
        'success': True,
        'message': 'Profile created! Your journey begins now, Hunter!'
    })


@app.route('/api/player/update-settings', methods=['POST'])
@login_required
def update_player_settings():
    """Update user stats settings and adapt workouts on the spot if equipment changes"""
    data = request.json or {}
    user_id = session['user_id']
    
    # Extract fields
    age = data.get('age')
    height_cm = data.get('height_cm')
    weight_kg = data.get('weight_kg')
    target_weight = data.get('target_weight')
    days_per_week = data.get('days_per_week')
    experience_level = data.get('experience_level')
    injuries = data.get('injuries')
    equipment = data.get('equipment')
    
    # Get previous stats to detect equipment change
    prev_stats = stats_manager.get_player_stats(user_id) or {}
    old_equipment = prev_stats.get('equipment', 'Full Commercial Gym')
    
    # Safe casting
    if age is not None:
        try: age = int(age)
        except ValueError: age = None
    if height_cm is not None:
        try: height_cm = float(height_cm)
        except ValueError: height_cm = None
    if weight_kg is not None:
        try: weight_kg = float(weight_kg)
        except ValueError: weight_kg = None
    if target_weight is not None:
        try: target_weight = float(target_weight)
        except ValueError: target_weight = None
    if days_per_week is not None:
        try: days_per_week = int(days_per_week)
        except ValueError: days_per_week = None
        
    success = stats_manager.update_player_stats_settings(
        user_id=user_id,
        age=age,
        height_cm=height_cm,
        weight_kg=weight_kg,
        target_weight=target_weight,
        days_per_week=days_per_week,
        experience_level=experience_level,
        injuries=injuries,
        equipment=equipment
    )
    
    if not success:
        return jsonify({'error': 'No settings updated or user not found'}), 400
    
    updated_stats = stats_manager.get_player_stats(user_id) or {}
    equipment_changed = equipment and (equipment != old_equipment)
    weekly_plan_adapted = False
    new_quest = None
    
    # If equipment was updated, adapt active workout routines and daily quest on the spot
    if equipment_changed or data.get('force_adapt'):
        active_physique = quest_generator.get_active_physique_quest(user_id)
        if active_physique:
            user_analyzer = get_analyzer_for_user(user_id)
            adapt_res = user_analyzer.adapt_physique_quest_to_equipment(
                user_id=user_id,
                active_quest=active_physique,
                new_equipment=equipment,
                user_stats=updated_stats,
                db=db
            )
            weekly_plan_adapted = adapt_res.get('success', False)
        
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM goals WHERE user_id = ? AND status = 'active'", (user_id,))
        goals = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        primary_focus_areas = stats_manager.get_primary_focus_areas(user_id)
        try:
            new_quest = quest_generator.regenerate_daily_quest(user_id, goals, primary_focus_areas)
        except Exception as ex_quest:
            print(f"⚠️ Error regenerating daily quest on settings update: {ex_quest}")
        
    return jsonify({
        'success': True,
        'equipment': equipment or old_equipment,
        'equipment_changed': equipment_changed,
        'weekly_plan_adapted': weekly_plan_adapted,
        'quest': new_quest,
        'message': f"Hunter configuration updated! Training protocol adapted to '{equipment or old_equipment}'."
    })


@app.route('/api/player/change-equipment', methods=['POST'])
@login_required
def change_player_equipment():
    """1-Click quick endpoint to change location/equipment and adapt workout routine on the spot"""
    user_id = session['user_id']
    data = request.json or {}
    new_equipment = data.get('equipment')
    force_override = data.get('force_override', False)
    
    if not new_equipment:
        return jsonify({'error': 'Equipment location specification required'}), 400
        
    prev_stats = stats_manager.get_player_stats(user_id) or {}
    old_equipment = prev_stats.get('equipment', 'Full Commercial Gym')
    
    # Check for fatal injuries in Calisthenics (shoulder, wrist, elbow, rotator cuff, severe joint)
    if 'calisthenic' in new_equipment.lower():
        user_injuries = (prev_stats.get('injuries') or 'None').lower()
        fatal_keywords = ['shoulder', 'wrist', 'elbow', 'rotator', 'tendonitis', 'dislocation', 'fracture', 'tear', 'impingement', 'joint']
        has_fatal_calisthenics_injury = any(kw in user_injuries for kw in fatal_keywords) and user_injuries != 'none'
        
        if has_fatal_calisthenics_injury and not force_override:
            return jsonify({
                'success': False,
                'blocked_by_injury': True,
                'injury_detected': prev_stats.get('injuries'),
                'message': f"⚠️ SYSTEM REJECTION: Calisthenics access locked! You have registered '{prev_stats.get('injuries')}'. High-torque bar & inversion movements are unsafe for your recovery. Recommended: Home / Low-Impact."
            }), 403
    
    # Update stats
    stats_manager.update_player_stats_settings(
        user_id=user_id,
        equipment=new_equipment
    )
    
    updated_stats = stats_manager.get_player_stats(user_id) or {}
    weekly_plan_adapted = False
    
    # Check for active character build goal
    active_physique = quest_generator.get_active_physique_quest(user_id)
    if active_physique:
        user_analyzer = get_analyzer_for_user(user_id)
        adapt_res = user_analyzer.adapt_physique_quest_to_equipment(
            user_id=user_id,
            active_quest=active_physique,
            new_equipment=new_equipment,
            user_stats=updated_stats,
            db=db
        )
        weekly_plan_adapted = adapt_res.get('success', False)
        
    # Regenerate today's active quest
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM goals WHERE user_id = ? AND status = 'active'", (user_id,))
    goals = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    primary_focus_areas = stats_manager.get_primary_focus_areas(user_id)
    new_quest = quest_generator.regenerate_daily_quest(user_id, goals, primary_focus_areas)
    
    return jsonify({
        'success': True,
        'equipment': new_equipment,
        'old_equipment': old_equipment,
        'weekly_plan_adapted': weekly_plan_adapted,
        'quest': new_quest,
        'message': f"⚡ SYSTEM NOTICE: Training environment switched to '{new_equipment}'. Workout routines adapted on the spot!"
    })


@app.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    """Get player stats"""
    user_id = session['user_id']
    stats = stats_manager.get_player_stats(user_id)
    
    if not stats:
        return jsonify({'error': 'Stats not found'}), 404
    
    return jsonify({'stats': stats})


@app.route('/api/stats/allocate', methods=['POST'])
@login_required
def allocate_stats():
    """Allocate stat points"""
    data = request.json
    user_id = session['user_id']
    
    success = stats_manager.allocate_stat_points(
        user_id,
        data.get('strength', 0),
        data.get('endurance', 0),
        data.get('agility', 0),
        data.get('vitality', 0)
    )
    
    if success:
        stats = stats_manager.get_player_stats(user_id)
        return jsonify({
            'success': True,
            'message': 'Stats allocated successfully!',
            'stats': stats
        })
    else:
        return jsonify({'error': 'Invalid stat allocation'}), 400


@app.route('/api/stats/update-measurements', methods=['POST'])
@login_required
def update_measurements():
    """Update body measurements"""
    data = request.json
    user_id = session['user_id']
    
    success = stats_manager.update_body_measurements(
        user_id,
        data.get('height_cm'),
        data.get('weight_kg')
    )
    
    if success:
        stats = stats_manager.get_player_stats(user_id)
        return jsonify({
            'success': True,
            'message': 'Measurements updated!',
            'stats': stats
        })
    else:
        return jsonify({'error': 'Update failed'}), 400


# ============================================================================
# QUEST ENDPOINTS (IMPROVED)
# ============================================================================

@app.route('/api/quest/today', methods=['GET'])
@login_required
def get_todays_quest():
    """Get or generate today's quest"""
    user_id = session['user_id']
    username = session.get('username', 'Unknown')
    
    try:
        print(f"\n{'='*60}")
        print(f"📋 Quest request from: {username} (ID: {user_id})")
        
        # Check if user has stats
        stats = stats_manager.get_player_stats(user_id)
        if not stats:
            print(f"❌ User {user_id} has no stats - needs profile setup")
            return jsonify({
                'error': 'Please complete profile setup first',
                'needs_setup': True
            }), 400
        
        print(f"✅ User stats found - Level {stats['level']}")
        
        active_physique = quest_generator.get_active_physique_quest(user_id)
        quest = quest_generator.get_todays_quest(user_id)
        
        # If user has an active build goal target character, ensure today's quest is built from that active target
        if active_physique and quest:
            target_name = active_physique.get('target_name')
            if quest.get('target_name') != target_name or not quest.get('from_weekly_plan'):
                print(f"🔄 Active build goal ({target_name}) differs from current quest ({quest.get('target_name')}) - regenerating today's quest for target!")
                try:
                    quest = quest_generator.regenerate_daily_quest(user_id, [], [])
                except Exception as ex_reg:
                    print(f"⚠️ Failed to regenerate quest for target: {ex_reg}")
        
        if quest:
            print(f"✅ Active quest found for today")
            print(f"   Title: {quest['title']}")
            print(f"   Exercises: {len(quest['exercises'])}")
            print(f"   Completed: {quest.get('completed', False)}")
        else:
            print(f"🔄 No quest for today - generating new quest...")
            
            # Get user goals
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM goals 
                WHERE user_id = ? AND status = 'active'
            ''', (user_id,))
            goals = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            print(f"   Active goals: {len(goals)}")
            for goal in goals:
                print(f"     - {goal['goal_type']}: {goal['goal_name']}")
            
            primary_focus_areas = stats_manager.get_primary_focus_areas(user_id)
            print(f"   Primary objective path: {primary_focus_areas}")
            
            # Generate new quest
            try:
                quest = quest_generator.generate_daily_quest(user_id, goals, primary_focus_areas)
                print(f"✅ Quest generated successfully!")
                print(f"   Title: {quest['title']}")
                print(f"   Exercises: {len(quest['exercises'])}")
                print(f"   Difficulty: {quest['difficulty']}")
                print(f"   EXP Reward: {quest['exp_reward']}")
                
                # Save quest
                quest_id = quest_generator.save_daily_quest(user_id, quest)
                quest['id'] = quest_id
                print(f"   Quest ID: {quest_id}")
                
                # Print exercise details
                for i, ex in enumerate(quest['exercises'], 1):
                    print(f"   {i}. {ex['name']}: {ex.get('sets', 1)} sets")
                
            except Exception as e:
                print(f"❌ ERROR generating quest: {e}")
                traceback.print_exc()
                return jsonify({
                    'error': f'Failed to generate quest: {str(e)}'
                }), 500
        
        print(f"{'='*60}\n")
        return jsonify({'quest': quest})
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR in get_todays_quest: {e}")
        traceback.print_exc()
        return jsonify({
            'error': 'Server error while fetching quest',
            'details': str(e)
        }), 500


@app.route('/api/quest/regenerate', methods=['POST'])
@login_required
def regenerate_quest():
    """Regenerate today's quest for user"""
    user_id = session['user_id']
    stats = stats_manager.get_player_stats(user_id)
    if not stats:
        return jsonify({'error': 'Please complete profile setup first'}), 400
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM goals 
        WHERE user_id = ? AND status = 'active'
    ''', (user_id,))
    goals = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    primary_focus_areas = stats_manager.get_primary_focus_areas(user_id)
    quest = quest_generator.regenerate_daily_quest(user_id, goals, primary_focus_areas)
    return jsonify({'success': True, 'quest': quest, 'message': 'New quest generated!'})


@app.route('/api/quest/weekly-schedule', methods=['GET'])
@login_required
def get_weekly_schedule():
    """Get the user's 7-day planned quest schedule"""
    user_id = session['user_id']
    schedule_data = quest_generator.get_weekly_schedule(user_id)
    return jsonify(schedule_data)


@app.route('/api/quest/log-set-completion', methods=['POST'])
@login_required
def log_set_completion():
    """Real-time EXP allocation as soon as 1 set or 1 exercise task is completed or uncompleted"""
    user_id = session['user_id']
    data = request.json or {}
    
    quest_id = data.get('quest_id')
    set_key = data.get('set_key')  # e.g. "ex0_set1" or "ex0_master"
    action = data.get('action', 'completed')  # 'completed' or 'uncompleted'
    exercise_name = data.get('exercise_name', 'Exercise')
    
    if not quest_id or set_key is None:
        return jsonify({'error': 'Missing required fields'}), 400
        
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM daily_quests WHERE id = ? AND user_id = ?', (quest_id, user_id))
    quest_row = cursor.fetchone()
    if not quest_row:
        conn.close()
        return jsonify({'error': 'Quest not found'}), 404
        
    quest_data = json.loads(quest_row['quest_data'])
    completed_sets = set(quest_data.get('completed_sets', []))
    
    # Calculate EXP per set/task
    total_sets = 0
    for ex in quest_data.get('exercises', []):
        total_sets += ex.get('sets', 3)
    total_sets = max(1, total_sets)
    
    exp_reward = quest_data.get('exp_reward', 100)
    set_exp = max(5, int(exp_reward / total_sets))
    
    level_result = {'leveled_up': False}
    exp_gained = 0
    
    # Handle bulk master checkbox toggle
    if data.get('toggle_all') or set_key == 'all':
        all_keys = set()
        exercises = quest_data.get('exercises', [])
        for i, ex in enumerate(exercises):
            all_keys.add(f"ex{i}_master")
            for s in range(ex.get('sets', 3)):
                all_keys.add(f"ex{i}_set{s}")
                
        if action == 'completed':
            added_count = len(all_keys - completed_sets)
            completed_sets = all_keys
            exp_gained = added_count * set_exp
            if exp_gained > 0:
                level_result = stats_manager.add_exp(user_id, exp_gained)
        else:  # uncompleted
            removed_count = len(completed_sets)
            completed_sets = set()
            exp_gained = -(removed_count * set_exp)
            if exp_gained < 0:
                level_result = stats_manager.deduct_exp(user_id, abs(exp_gained))
                
        quest_data['completed_sets'] = list(completed_sets)
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        is_completed_flag = 1 if (action == 'completed' and len(exercises) > 0) else 0
        
        cursor.execute('''
            UPDATE daily_quests
            SET quest_data = ?, completed = ?, completed_at = ?
            WHERE id = ?
        ''', (json.dumps(quest_data), is_completed_flag, now_str if is_completed_flag else None, quest_id))
        
        conn.commit()
        conn.close()
        
        updated_stats = stats_manager.get_player_stats(user_id)
        return jsonify({
            'success': True,
            'action': action,
            'toggle_all': True,
            'exp_gained': exp_gained,
            'exercise_name': "Today's Quest",
            'stats': updated_stats,
            'level_result': level_result,
            'completed_sets': list(completed_sets)
        })

    if action == 'completed':
        if set_key not in completed_sets:
            completed_sets.add(set_key)
            exp_gained = set_exp
            level_result = stats_manager.add_exp(user_id, set_exp)
    else:  # uncompleted
        if set_key in completed_sets:
            completed_sets.remove(set_key)
            exp_gained = -set_exp
            level_result = stats_manager.deduct_exp(user_id, set_exp)
            
    quest_data['completed_sets'] = list(completed_sets)
    is_fully_completed = len(completed_sets) >= total_sets and total_sets > 0
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if is_fully_completed:
        cursor.execute('''
            UPDATE daily_quests
            SET quest_data = ?, completed = 1, completed_at = COALESCE(completed_at, ?)
            WHERE id = ?
        ''', (json.dumps(quest_data), now_str, quest_id))
    else:
        cursor.execute('''
            UPDATE daily_quests
            SET quest_data = ?, completed = 0, completed_at = NULL
            WHERE id = ?
        ''', (json.dumps(quest_data), quest_id))
        
    # Ensure workout_history record is present for this workout date
    if len(completed_sets) > 0:
        q_date = quest_row['quest_date'] or datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT id FROM workout_history WHERE user_id = ? AND workout_date = ?
        ''', (user_id, q_date))
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO workout_history (user_id, workout_date, total_exercises, total_reps, total_duration_minutes, exp_gained, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, q_date, len(quest_data.get('exercises', [])), len(completed_sets) * 10, 30, exp_reward, 'Daily Quest Completed'))
            
    conn.commit()
    conn.close()
    
    updated_stats = stats_manager.get_player_stats(user_id)
    
    return jsonify({
        'success': True,
        'action': action,
        'set_key': set_key,
        'exp_gained': exp_gained,
        'exercise_name': exercise_name,
        'stats': updated_stats,
        'level_result': level_result,
        'completed_sets': list(completed_sets)
    })


@app.route('/api/quest/complete', methods=['POST'])
@login_required
def complete_quest():
    """Complete a quest"""
    data = request.json
    user_id = session['user_id']
    username = session.get('username', 'Unknown')
    
    quest_id = data.get('quest_id')
    completions = data.get('completions', [])
    
    print(f"\n🎯 Quest completion from {username}")
    print(f"   Quest ID: {quest_id}")
    print(f"   Exercises completed: {len(completions)}")
    
    try:
        result = quest_generator.complete_quest(user_id, quest_id, completions)
        
        if result.get('success'):
            print(f"✅ Quest completed!")
            print(f"   EXP gained: {result.get('exp_gained', 0)}")
            if result.get('level_result') and result['level_result'].get('leveled_up'):
                print(f"   🎉 LEVEL UP! New level: {result['level_result']['new_level']}")
            return jsonify(result)
        else:
            return jsonify(result), 400
        
    except Exception as e:
        print(f"❌ Error completing quest: {e}")
        traceback.print_exc()
        return jsonify({
            'error': 'Failed to complete quest',
            'details': str(e)
        }), 500


@app.route('/api/quest/history', methods=['GET'])
@login_required
def get_quest_history():
    """Get quest completion history"""
    user_id = session['user_id']
    days = request.args.get('days', 30, type=int)
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM daily_quests
        WHERE user_id = ? 
        AND quest_date >= date('now', ? || ' days')
        ORDER BY quest_date DESC
    ''', (user_id, -days))
    
    quests = []
    for row in cursor.fetchall():
        quest_data = json.loads(row['quest_data'])
        quest_data['id'] = row['id']
        quest_data['completed'] = bool(row['completed'])
        quest_data['completed_at'] = row['completed_at']
        quests.append(quest_data)
    
    conn.close()
    
    return jsonify({'quests': quests})


# ============================================================================
# EXERCISE ENDPOINTS
# ============================================================================

@app.route('/api/exercises', methods=['GET'])
@login_required
def get_exercises():
    """Get all user exercises"""
    user_id = session['user_id']
    exercises = exercise_manager.get_user_exercises(user_id)
    
    return jsonify({'exercises': exercises})


@app.route('/api/exercises/add', methods=['POST'])
@login_required
def add_exercise():
    """Add or update exercise record"""
    data = request.json
    user_id = session['user_id']
    
    success = exercise_manager.add_or_update_exercise(
        user_id,
        data.get('name'),
        data.get('category'),
        data.get('max_reps', 0),
        data.get('max_weight', 0),
        data.get('max_duration', 0)
    )
    
    if success:
        return jsonify({
            'success': True,
            'message': 'Exercise record updated!'
        })
    else:
        return jsonify({'error': 'Failed to update exercise'}), 400


# ============================================================================
# GOALS ENDPOINTS
# ============================================================================

@app.route('/api/goals', methods=['GET'])
@login_required
def get_goals():
    """Get all user goals"""
    user_id = session['user_id']
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM goals 
        WHERE user_id = ?
        ORDER BY 
            CASE status 
                WHEN 'active' THEN 1 
                WHEN 'completed' THEN 2 
                ELSE 3 
            END,
            priority DESC
    ''', (user_id,))
    
    goals = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'goals': goals})


@app.route('/api/goals/add', methods=['POST'])
@login_required
def add_goal():
    """Add a new goal"""
    data = request.json
    user_id = session['user_id']
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO goals 
        (user_id, goal_type, goal_name, target_value, current_value, 
         deadline, priority)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, data.get('goal_type'), data.get('goal_name'),
          data.get('target_value'), data.get('current_value', 0),
          data.get('deadline'), data.get('priority', 'medium')))
    
    conn.commit()
    goal_id = cursor.lastrowid
    conn.close()
    
    print(f"✅ Goal added for user {user_id}: {data.get('goal_name')}")
    
    return jsonify({
        'success': True,
        'message': 'Goal added!',
        'goal_id': goal_id
    })


@app.route('/api/goals/<int:goal_id>/update', methods=['POST'])
@login_required
def update_goal(goal_id):
    """Update goal progress safely with strict validation and static queries"""
    data = request.json or {}
    user_id = session['user_id']
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    has_val = 'current_value' in data
    has_status = 'status' in data
    
    val = None
    if has_val:
        try:
            val = float(data['current_value'])
        except (ValueError, TypeError):
            conn.close()
            return jsonify({'error': 'current_value must be a valid number'}), 400

    status_val = None
    if has_status:
        status_val = str(data['status']).strip().lower()
        if status_val not in ('active', 'completed', 'abandoned'):
            conn.close()
            return jsonify({'error': 'Invalid status'}), 400

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if has_val and has_status:
        if status_val == 'completed':
            cursor.execute('''
                UPDATE goals 
                SET current_value = ?, status = ?, completed_at = ?
                WHERE user_id = ? AND id = ?
            ''', (val, status_val, now_str, user_id, goal_id))
        else:
            cursor.execute('''
                UPDATE goals 
                SET current_value = ?, status = ?
                WHERE user_id = ? AND id = ?
            ''', (val, status_val, user_id, goal_id))
    elif has_val:
        cursor.execute('''
            UPDATE goals 
            SET current_value = ?
            WHERE user_id = ? AND id = ?
        ''', (val, user_id, goal_id))
    elif has_status:
        if status_val == 'completed':
            cursor.execute('''
                UPDATE goals 
                SET status = ?, completed_at = ?
                WHERE user_id = ? AND id = ?
            ''', (status_val, now_str, user_id, goal_id))
        else:
            cursor.execute('''
                UPDATE goals 
                SET status = ?
                WHERE user_id = ? AND id = ?
            ''', (status_val, user_id, goal_id))
    else:
        conn.close()
        return jsonify({'error': 'No valid update fields provided'}), 400
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Goal updated!'})


@app.route('/api/goals/objective-path', methods=['POST'])
@login_required
def update_objective_path():
    """Update the multi-select Primary Objective Path after initial setup"""
    data = request.json
    user_id = session['user_id']
    focus_areas = data.get('primary_focus_areas', [])
    
    if not focus_areas:
        return jsonify({'error': 'Select at least one objective'}), 400
    
    stats_manager.update_primary_focus_areas(user_id, focus_areas)
    
    return jsonify({
        'success': True,
        'message': 'Objective path updated! Tomorrow\'s quest will reflect your new focus.'
    })


# ============================================================================
# PHYSIQUE ANALYZER ENDPOINTS
# ("Become Like X" - AI Quest Log Generator)
# ============================================================================

@app.route('/api/physique/status', methods=['GET'])
@login_required
def physique_status():
    """Check whether AI physique analysis is configured for THIS user"""
    user_id = session['user_id']
    analyzer = get_analyzer_for_user(user_id)
    return jsonify({
        'configured': analyzer.is_configured(),
        'using_personal_key': user_settings.has_gemini_key(user_id),
        'shared_key_available': _fallback_analyzer.is_configured()
    })


@app.route('/api/physique/analyze', methods=['POST'])
@login_required
def analyze_physique():
    """
    Generate a Quest Log by analyzing either:
    - A named character/person (form field 'target_name'), OR
    - An uploaded reference photo (multipart file field 'image')
    
    Uses the requesting user's personal API key if they've set one in
    Settings, otherwise falls back to the server's shared key if the site
    owner configured one.
    """
    user_id = session['user_id']
    username = session.get('username', 'Unknown')
    analyzer = get_analyzer_for_user(user_id)
    
    target_name = request.form.get('target_name', '').strip() or None
    image_file = request.files.get('image')
    image_path = None
    saved_filename = None
    
    print(f"\n🎭 Physique analysis request from {username}")
    print(f"   Target name: {target_name}")
    print(f"   Image uploaded: {image_file is not None and image_file.filename}")
    print(f"   Using personal key: {user_settings.has_gemini_key(user_id)}")
    
    if image_file and image_file.filename:
        if not allowed_image(image_file.filename):
            return jsonify({'error': 'Unsupported image type. Use JPG, PNG, or WEBP.'}), 400
        
        ext = image_file.filename.rsplit('.', 1)[1].lower()
        saved_filename = f"{user_id}_{uuid.uuid4().hex}.{ext}"
        image_path = os.path.join(UPLOAD_FOLDER, saved_filename)
        image_file.save(image_path)
    
    if not target_name and not image_path:
        return jsonify({'error': 'Provide a character/person name or upload a photo.'}), 400
    
    user_stats = stats_manager.get_player_stats(user_id) or {}
    user_body_type = user_stats.get('body_type', 'mesomorph')
    user_injuries = user_stats.get('injuries', 'None')
    user_equipment = user_stats.get('equipment', 'Full Commercial Gym')

    try:
        result = analyzer.generate_quest_log(
            target_name=target_name,
            image_path=image_path,
            current_body_type=user_body_type,
            injuries=user_injuries,
            equipment=user_equipment
        )
        
        if not result.get('success'):
            print(f"❌ Physique analysis failed: {result.get('error')}")
            return jsonify(result), 400 if result.get('setup_required') else 500
        
        # Save to database
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Deactivate previous active quest logs (only one "current build goal" at a time)
        cursor.execute('UPDATE physique_quests SET is_active = 0 WHERE user_id = ?', (user_id,))
        
        cursor.execute('''
            INSERT INTO physique_quests 
            (user_id, target_name, source_type, image_path, quest_log_markdown, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        ''', (user_id, result['target_name'], result['source_type'],
              saved_filename, result['quest_log_markdown']))
        
        physique_quest_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        result['id'] = physique_quest_id
        print(f"✅ Quest Log generated and saved (ID: {physique_quest_id})")
        
        # Convert the weekly split into structured data so it drives the
        # actual daily quests, not just a wall of text the user reads once.
        weekly_result = analyzer.extract_structured_weekly_plan(
            result['quest_log_markdown'],
            target_name=result.get('target_name'),
            equipment=user_equipment
        )
        if weekly_result.get('success'):
            weekly_plan_manager.save_weekly_plan(user_id, physique_quest_id, weekly_result['days'])
            try:
                # Update today's active quest immediately so the build goal is active starting today
                quest_generator.regenerate_daily_quest(user_id, [], [])
            except Exception as ex_reg:
                print(f"⚠️  Could not auto-update today's quest: {ex_reg}")
            result['weekly_plan_linked'] = True
            print(f"✅ Weekly plan structured and linked to daily quests")
        else:
            result['weekly_plan_linked'] = False
            result['weekly_plan_error'] = weekly_result.get('error')
            print(f"⚠️  Weekly plan structuring failed: {weekly_result.get('error')}")
        
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ Error in physique analysis: {e}")
        traceback.print_exc()
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500


@app.route('/api/physique/history', methods=['GET'])
@login_required
def physique_history():
    """Get past physique analysis Quest Logs for this user"""
    user_id = session['user_id']
    
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, target_name, source_type, image_path, quest_log_markdown, 
               is_active, created_at
        FROM physique_quests
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (user_id,))
    
    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'history': history})


@app.route('/api/workout/generate-by-bodytype', methods=['POST'])
@login_required
def generate_workout_by_bodytype():
    """
    Backend Fitness Programming Engine Endpoint
    Generates a highly optimized, physiologically safe, and effective weekly workout plan.
    """
    from physique_analyzer import PhysiqueAnalyzer
    data = request.get_json() or {}
    user_id = session.get('user_id')
    user_stats = stats_manager.get_player_stats(user_id) or {}
    
    body_type = data.get('body_type') or user_stats.get('body_type', 'mesomorph')
    days_per_week = data.get('days_per_week') or user_stats.get('days_per_week', 5)
    equipment = data.get('equipment') or user_stats.get('equipment', 'Full Commercial Gym')
    injuries = data.get('injuries') or user_stats.get('injuries', 'None')
    
    analyzer = PhysiqueAnalyzer()
    result = analyzer.generate_weekly_workout_json(
        body_type=body_type,
        days_per_week=days_per_week,
        equipment=equipment,
        injuries=injuries
    )
    return jsonify(result)


@app.route('/api/physique/<int:quest_log_id>/activate', methods=['POST'])
@login_required
def activate_physique_quest(quest_log_id):
    """Mark a past Quest Log as the active build goal and re-link its weekly plan"""
    user_id = session['user_id']
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, target_name, quest_log_markdown FROM physique_quests WHERE id = ? AND user_id = ?',
                   (quest_log_id, user_id))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Quest Log not found'}), 404
    
    target_name = row['target_name']
    quest_log_markdown = row['quest_log_markdown']
    
    cursor.execute('UPDATE physique_quests SET is_active = 0 WHERE user_id = ?', (user_id,))
    cursor.execute('UPDATE physique_quests SET is_active = 1 WHERE id = ?', (quest_log_id,))
    conn.commit()
    conn.close()
    
    # Re-derive the structured weekly plan for the newly-activated goal so
    # daily quests immediately reflect it instead of the previous one.
    user_stats = stats_manager.get_player_stats(user_id) or {}
    user_eq = user_stats.get('equipment', 'Full Commercial Gym')
    analyzer = get_analyzer_for_user(user_id)
    weekly_result = analyzer.extract_structured_weekly_plan(quest_log_markdown, target_name=target_name, equipment=user_eq)
    if weekly_result.get('success'):
        weekly_plan_manager.save_weekly_plan(user_id, quest_log_id, weekly_result['days'])
        try:
            quest_generator.regenerate_daily_quest(user_id, [], [])
        except Exception as ex_reg:
            print(f"⚠️  Could not auto-update today's quest on activation: {ex_reg}")
    
    return jsonify({'success': True, 'message': 'Build goal activated!'})


@app.route('/api/physique/<int:quest_log_id>', methods=['DELETE'])
@login_required
def delete_physique_quest(quest_log_id):
    """Delete a saved physique Quest Log"""
    user_id = session['user_id']
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT image_path, is_active FROM physique_quests WHERE id = ? AND user_id = ?',
                   (quest_log_id, user_id))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return jsonify({'error': 'Quest Log not found'}), 404
    
    was_active = bool(row['is_active'])
    
    if row['image_path']:
        img_path = os.path.join(UPLOAD_FOLDER, row['image_path'])
        if os.path.exists(img_path):
            os.remove(img_path)
    
    cursor.execute('DELETE FROM physique_quests WHERE id = ? AND user_id = ?',
                   (quest_log_id, user_id))
    conn.commit()
    conn.close()
    
    # If the deleted goal was the active one, clear its weekly plan too --
    # daily quests fall back to the normal algorithmic generator.
    if was_active:
        weekly_plan_manager.clear_plan(user_id)
    
    return jsonify({'success': True, 'message': 'Quest Log deleted'})


# ============================================================================
# USER SETTINGS ENDPOINTS
# (personal AI API keys, for when this app is deployed for multiple people)
# ============================================================================

@app.route('/api/settings/api-key', methods=['GET'])
@login_required
def get_api_key_status():
    """Check whether the current user has a personal key saved (never returns the key itself)"""
    user_id = session['user_id']
    return jsonify({
        'has_personal_key': user_settings.has_gemini_key(user_id),
        'shared_key_available': _fallback_analyzer.is_configured()
    })


@app.route('/api/settings/api-key', methods=['POST'])
@login_required
def save_api_key():
    """Save (or replace) the current user's personal Gemini API key, encrypted at rest"""
    from crypto_utils import is_configured as encryption_is_configured
    
    if not encryption_is_configured():
        return jsonify({
            'error': (
                'Server-side encryption is not configured. An administrator needs to '
                'set the APP_ENCRYPTION_KEY environment variable before personal API '
                'keys can be safely stored. See README for setup instructions.'
            )
        }), 503
    
    data = request.json
    api_key = (data.get('api_key') or '').strip()
    
    if not api_key:
        return jsonify({'error': 'API key cannot be empty'}), 400
    
    if len(api_key) < 10:
        return jsonify({'error': 'That doesn\'t look like a valid API key'}), 400
    
    user_id = session['user_id']
    
    # Do a lightweight live check that the key actually works before saving it,
    # so users get immediate feedback instead of a silent failure later.
    test_analyzer = PhysiqueAnalyzer(api_key=api_key)
    if not test_analyzer.is_configured():
        return jsonify({'error': 'Could not initialize with that key. Double-check it\'s correct.'}), 400
    
    user_settings.save_gemini_key(user_id, api_key)
    
    print(f"✅ User {session.get('username')} saved a personal Gemini API key")
    
    return jsonify({
        'success': True,
        'message': 'Your API key has been saved securely. It will be used for your AI features going forward.'
    })


@app.route('/api/settings/api-key', methods=['DELETE'])
@login_required
def delete_api_key():
    """Remove the current user's personal API key (falls back to shared key if available)"""
    user_id = session['user_id']
    user_settings.delete_gemini_key(user_id)
    
    return jsonify({
        'success': True,
        'message': 'Personal API key removed.'
    })


# ============================================================================
# SOCIAL / FRIENDS ENDPOINTS
# ============================================================================

@app.route('/api/friends', methods=['GET'])
@login_required
def get_friends():
    """Get user's friends list"""
    user_id = session['user_id']
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT DISTINCT u.id, u.username, ps.level, ps.exp, f.status
        FROM friends f
        JOIN users u ON (f.friend_id = u.id)
        LEFT JOIN player_stats ps ON (u.id = ps.user_id)
        WHERE f.user_id = ? AND f.status = 'accepted'
        ORDER BY ps.level DESC
    ''', (user_id,))
    
    friends = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'friends': friends})


@app.route('/api/friends/search', methods=['GET'])
@login_required
def search_users():
    """Search for users to add as friends with current relationship status"""
    query = request.args.get('q', '').strip()
    user_id = session['user_id']
    
    if len(query) < 2:
        return jsonify({'users': []})
    
    # Escape LIKE wildcards to prevent pattern injection
    escaped_query = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    search_param = f"%{escaped_query}%"
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT u.id, u.username, ps.level,
               f.status as friendship_status,
               f.user_id as request_sender_id
        FROM users u
        LEFT JOIN player_stats ps ON (u.id = ps.user_id)
        LEFT JOIN friends f ON (
            (f.user_id = ? AND f.friend_id = u.id) OR 
            (f.user_id = u.id AND f.friend_id = ?)
        )
        WHERE u.username LIKE ? ESCAPE '\\' AND u.id != ? AND COALESCE(u.is_admin, 0) = 0
        LIMIT 20
    ''', (user_id, user_id, search_param, user_id))
    
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'users': users})


@app.route('/api/friends/add', methods=['POST'])
@login_required
def add_friend():
    """Send friend request"""
    data = request.json or {}
    user_id = session['user_id']
    friend_id = data.get('friend_id')
    
    if not friend_id or int(friend_id) == user_id:
        return jsonify({'error': 'Cannot add yourself as a friend'}), 400
        
    friend_id = int(friend_id)
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Check if target user exists
    cursor.execute('SELECT id FROM users WHERE id = ?', (friend_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'User not found'}), 404
        
    # Check existing friendship or pending request
    cursor.execute('''
        SELECT status, user_id FROM friends
        WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)
    ''', (user_id, friend_id, friend_id, user_id))
    existing = cursor.fetchone()
    
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if existing:
        if existing['status'] == 'accepted':
            conn.close()
            return jsonify({'error': 'You are already friends!'}), 400
        elif existing['user_id'] == user_id:
            conn.close()
            return jsonify({'error': 'Friend request already sent!'}), 400
        else:
            # The other user sent a request to us -> Auto Accept!
            cursor.execute('''
                UPDATE friends SET status = 'accepted', accepted_at = ?
                WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)
            ''', (now_str, friend_id, user_id, user_id, friend_id))
            cursor.execute('''
                INSERT OR IGNORE INTO friends (user_id, friend_id, status, accepted_at)
                VALUES (?, ?, 'accepted', ?)
            ''', (user_id, friend_id, now_str))
            conn.commit()
            conn.close()
            return jsonify({'success': True, 'message': 'Mutual request! You are now friends!'})
    
    cursor.execute('''
        INSERT INTO friends (user_id, friend_id, status)
        VALUES (?, ?, 'pending')
    ''', (user_id, friend_id))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Friend request sent!'})


@app.route('/api/friends/pending', methods=['GET'])
@login_required
def get_pending_friends():
    """Get incoming and outgoing pending friend requests"""
    user_id = session['user_id']
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Incoming requests sent TO this user
    cursor.execute('''
        SELECT u.id, u.username, ps.level
        FROM friends f
        JOIN users u ON (f.user_id = u.id)
        LEFT JOIN player_stats ps ON (u.id = ps.user_id)
        WHERE f.friend_id = ? AND f.status = 'pending'
    ''', (user_id,))
    incoming = [dict(row) for row in cursor.fetchall()]
    
    # Outgoing requests sent BY this user
    cursor.execute('''
        SELECT u.id, u.username, ps.level
        FROM friends f
        JOIN users u ON (f.friend_id = u.id)
        LEFT JOIN player_stats ps ON (u.id = ps.user_id)
        WHERE f.user_id = ? AND f.status = 'pending'
    ''', (user_id,))
    outgoing = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'incoming': incoming,
        'outgoing': outgoing,
        'pending': incoming
    })


@app.route('/api/friends/accept', methods=['POST'])
@login_required
def accept_friend():
    """Accept friend request"""
    data = request.json or {}
    user_id = session['user_id']
    friend_id = data.get('friend_id')
    
    if not friend_id:
        return jsonify({'error': 'Missing friend_id'}), 400
        
    friend_id = int(friend_id)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Update existing request status to accepted for both directions
    cursor.execute('''
        UPDATE friends
        SET status = 'accepted', accepted_at = ?
        WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)
    ''', (now_str, friend_id, user_id, user_id, friend_id))
    
    # Check if reciprocal entry for (user_id, friend_id) exists, insert if missing
    cursor.execute('SELECT id FROM friends WHERE user_id = ? AND friend_id = ?', (user_id, friend_id))
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO friends (user_id, friend_id, status, accepted_at)
            VALUES (?, ?, 'accepted', ?)
        ''', (user_id, friend_id, now_str))
        
    # Check if reciprocal entry for (friend_id, user_id) exists, insert if missing
    cursor.execute('SELECT id FROM friends WHERE user_id = ? AND friend_id = ?', (friend_id, user_id))
    if not cursor.fetchone():
        cursor.execute('''
            INSERT INTO friends (user_id, friend_id, status, accepted_at)
            VALUES (?, ?, 'accepted', ?)
        ''', (friend_id, user_id, now_str))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Friend request accepted!'})
    conn.close()
    
    return jsonify({'success': True, 'message': 'Friend request accepted!'})


@app.route('/api/friends/decline', methods=['POST'])
@login_required
def decline_friend():
    """Decline / cancel a friend request or remove an active friend"""
    data = request.json or {}
    user_id = session['user_id']
    friend_id = data.get('friend_id')
    
    if not friend_id:
        return jsonify({'error': 'Missing friend_id'}), 400
        
    friend_id = int(friend_id)
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        DELETE FROM friends 
        WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)
    ''', (user_id, friend_id, friend_id, user_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Friend relationship updated'})


@app.route('/api/leaderboard', methods=['GET'])
@login_required
def get_leaderboard():
    """Get global or friends leaderboard with friendship status (de-duplicated)"""
    user_id = session['user_id']
    scope = request.args.get('scope', 'global')
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    if scope == 'friends':
        cursor.execute('''
            SELECT u.id, u.username, ps.level, ps.exp, ps.strength, 
                   ps.endurance, ps.agility, ps.vitality,
                   (
                       SELECT f.status FROM friends f
                       WHERE (f.user_id = ? AND f.friend_id = u.id) OR (f.user_id = u.id AND f.friend_id = ?)
                       ORDER BY CASE WHEN f.status = 'accepted' THEN 1 WHEN f.status = 'pending' THEN 2 ELSE 3 END
                       LIMIT 1
                   ) as friendship_status,
                   (
                       SELECT f.user_id FROM friends f
                       WHERE (f.user_id = ? AND f.friend_id = u.id) OR (f.user_id = u.id AND f.friend_id = ?)
                       ORDER BY CASE WHEN f.status = 'accepted' THEN 1 WHEN f.status = 'pending' THEN 2 ELSE 3 END
                       LIMIT 1
                   ) as request_sender_id
            FROM player_stats ps
            JOIN users u ON (ps.user_id = u.id)
            WHERE u.id IN (
                SELECT friend_id FROM friends WHERE user_id = ? AND status = 'accepted'
                UNION
                SELECT user_id FROM friends WHERE friend_id = ? AND status = 'accepted'
            ) OR ps.user_id = ?
            ORDER BY ps.level DESC, ps.exp DESC
            LIMIT 10
        ''', (user_id, user_id, user_id, user_id, user_id, user_id, user_id))
    else:
        cursor.execute('''
            SELECT u.id, u.username, ps.level, ps.exp, ps.strength,
                   ps.endurance, ps.agility, ps.vitality,
                   (
                       SELECT f.status FROM friends f
                       WHERE (f.user_id = ? AND f.friend_id = u.id) OR (f.user_id = u.id AND f.friend_id = ?)
                       ORDER BY CASE WHEN f.status = 'accepted' THEN 1 WHEN f.status = 'pending' THEN 2 ELSE 3 END
                       LIMIT 1
                   ) as friendship_status,
                   (
                       SELECT f.user_id FROM friends f
                       WHERE (f.user_id = ? AND f.friend_id = u.id) OR (f.user_id = u.id AND f.friend_id = ?)
                       ORDER BY CASE WHEN f.status = 'accepted' THEN 1 WHEN f.status = 'pending' THEN 2 ELSE 3 END
                       LIMIT 1
                   ) as request_sender_id
            FROM player_stats ps
            JOIN users u ON (ps.user_id = u.id)
            WHERE COALESCE(u.is_admin, 0) = 0
            ORDER BY ps.level DESC, ps.exp DESC
            LIMIT 10
        ''', (user_id, user_id, user_id, user_id))
    
    seen_ids = set()
    leaderboard = []
    for row in cursor.fetchall():
        row_dict = dict(row)
        if row_dict['id'] not in seen_ids:
            seen_ids.add(row_dict['id'])
            leaderboard.append(row_dict)
            if len(leaderboard) >= 10:
                break
            
    conn.close()
    
    return jsonify({'leaderboard': leaderboard[:10]})


@app.route('/api/user/<int:user_id>/profile', methods=['GET'])
@login_required
def get_user_profile(user_id):
    """Get read-only profile data for a specific user (Friend/Hunter inspection)"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # 1. Fetch user basic info
        cursor.execute('SELECT id, username, created_at FROM users WHERE id = ?', (user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            conn.close()
            return jsonify({'error': 'Hunter not found'}), 404
            
        user_data = dict(user_row)
        
        # 2. Fetch player stats
        cursor.execute('''
            SELECT level, exp, exp_to_next_level, strength, endurance, agility, vitality,
                   primary_focus_areas, experience_level, days_per_week
            FROM player_stats WHERE user_id = ?
        ''', (user_id,))
        stats_row = cursor.fetchone()
        raw_stats = dict(stats_row) if stats_row else {}
        
        stats_data = {
            'level': raw_stats.get('level') if raw_stats.get('level') is not None else 1,
            'exp': raw_stats.get('exp') if raw_stats.get('exp') is not None else 0,
            'exp_to_next_level': raw_stats.get('exp_to_next_level') if raw_stats.get('exp_to_next_level') is not None else 100,
            'strength': raw_stats.get('strength') if raw_stats.get('strength') is not None else 10,
            'endurance': raw_stats.get('endurance') if raw_stats.get('endurance') is not None else 10,
            'agility': raw_stats.get('agility') if raw_stats.get('agility') is not None else 10,
            'vitality': raw_stats.get('vitality') if raw_stats.get('vitality') is not None else 10,
            'primary_focus_areas': raw_stats.get('primary_focus_areas') or 'General Fitness',
            'experience_level': raw_stats.get('experience_level') or 'beginner',
            'days_per_week': raw_stats.get('days_per_week') or 5
        }
        
        # 3. Active Physique Quest Goal
        cursor.execute('''
            SELECT target_name, source_type FROM physique_quests 
            WHERE user_id = ? AND is_active = 1 LIMIT 1
        ''', (user_id,))
        physique_row = cursor.fetchone()
        physique_goal = dict(physique_row) if physique_row else None
        
        conn.close()
        
        # 4. Fetch Weekly Training Plan
        weekly_days = []
        try:
            weekly_plan_mgr = WeeklyPlanManager(db)
            weekly_days = weekly_plan_mgr.get_all_days(user_id)
        except Exception as wp_err:
            print(f"Error fetching weekly plan for user {user_id}: {wp_err}")
        
        # 5. Determine Rank
        rank_title = get_rank_from_level(stats_data['level'])
        
        return jsonify({
            'user': user_data,
            'stats': stats_data,
            'physique_goal': physique_goal,
            'weekly_plan': weekly_days,
            'rank': rank_title
        })
    except Exception as e:
        print(f"Error loading profile for user {user_id}: {e}")
        return jsonify({'error': f'Failed to load profile: {str(e)}'}), 500


# ============================================================================
# STATISTICS ENDPOINTS
# ============================================================================

@app.route('/api/stats/progress', methods=['GET'])
@login_required
def get_progress_data():
    """Get continuous day-by-day progress data for charts (7 parts for 7 days, 30 parts for 30 days)"""
    user_id = session['user_id']
    days = request.args.get('days', 30, type=int)
    days_count = max(1, min(days, 365))
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    today = datetime.now().date()
    start_date = today - timedelta(days=days_count - 1)
    start_date_str = start_date.strftime('%Y-%m-%d')
    
    # 1. Gather all activity dates and EXP gains from daily_quests
    cursor.execute('''
        SELECT id, quest_date, completed, completed_at, exp_reward, quest_data
        FROM daily_quests
        WHERE user_id = ? 
        AND quest_date >= ?
        ORDER BY quest_date ASC
    ''', (user_id, start_date_str))
    quest_rows = cursor.fetchall()
    
    daily_exp_map = {}
    daily_workout_map = {}
    
    for row in quest_rows:
        q_date = row['quest_date']
        is_completed = bool(row['completed'])
        reward = row['exp_reward'] or 50
        
        q_data = {}
        try:
            q_data = json.loads(row['quest_data']) if row['quest_data'] else {}
        except Exception:
            pass
            
        completed_sets = q_data.get('completed_sets', [])
        
        if is_completed:
            daily_exp_map[q_date] = daily_exp_map.get(q_date, 0) + reward
            daily_workout_map[q_date] = daily_workout_map.get(q_date, 0) + 1
        elif len(completed_sets) > 0:
            total_sets = sum(ex.get('sets', 3) for ex in q_data.get('exercises', [])) or 1
            earned = max(5, int(reward / total_sets)) * len(completed_sets)
            daily_exp_map[q_date] = daily_exp_map.get(q_date, 0) + earned
            daily_workout_map[q_date] = daily_workout_map.get(q_date, 0) + 1

    # 2. Check workout_history
    cursor.execute('''
        SELECT workout_date, exp_gained, total_exercises
        FROM workout_history
        WHERE user_id = ?
        AND workout_date >= ?
        ORDER BY workout_date ASC
    ''', (user_id, start_date_str))
    for wh in cursor.fetchall():
        w_date = wh['workout_date']
        w_exp = wh['exp_gained'] or 50
        if w_date not in daily_exp_map:
            daily_exp_map[w_date] = w_exp
        if w_date not in daily_workout_map:
            daily_workout_map[w_date] = 1

    # 3. Check quest_completions
    cursor.execute('''
        SELECT DATE(completed_at) as c_date, COUNT(*) as cnt
        FROM quest_completions
        WHERE user_id = ?
        AND DATE(completed_at) >= ?
        GROUP BY DATE(completed_at)
    ''', (user_id, start_date_str))
    for qc in cursor.fetchall():
        c_date = qc['c_date']
        if c_date and c_date not in daily_exp_map:
            daily_exp_map[c_date] = qc['cnt'] * 15
        if c_date and c_date not in daily_workout_map:
            daily_workout_map[c_date] = 1

    # Generate continuous day-by-day sequence for exactly days_count parts
    exp_data = []
    workout_data = []
    running_total = 0
    
    for i in range(days_count):
        cur_date = start_date + timedelta(days=i)
        date_str = cur_date.strftime('%Y-%m-%d')
        
        # Format labels
        if days_count <= 7:
            label = cur_date.strftime('%a, %b %d')
            short_label = f"Day {i+1} ({cur_date.strftime('%b %d')})"
        elif days_count <= 30:
            label = cur_date.strftime('%b %d')
            short_label = f"Day {i+1}"
        else:
            label = cur_date.strftime('%b %d')
            short_label = cur_date.strftime('%m/%d')
            
        daily_gained = daily_exp_map.get(date_str, 0)
        running_total += daily_gained
        workouts_done = daily_workout_map.get(date_str, 0)
        
        exp_data.append({
            'date': date_str,
            'label': label,
            'short_label': short_label,
            'day_index': i + 1,
            'daily_gain': daily_gained,
            'exp': running_total
        })
        
        workout_data.append({
            'date': date_str,
            'label': label,
            'workouts': workouts_done
        })
        
    conn.close()
    
    return jsonify({
        'success': True,
        'timeframe_days': days_count,
        'exp_progress': exp_data,
        'workout_completions': workout_data
    })


# ============================================================================
# ADMINISTRATOR & OVERLORD ENDPOINTS
# ============================================================================

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        user = user_manager.get_user_by_id(session['user_id'])
        if not user or not user.get('is_admin'):
            return jsonify({'error': 'Administrator access required'}), 403
        return f(*args, **kwargs)
    return decorated_function


@app.route('/api/admin/stats', methods=['GET'])
@admin_required
def admin_get_stats():
    """Get system-wide overview statistics"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_admin = 1')
    total_admins = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM workout_history')
    total_workouts = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM quest_completions')
    total_quests_completed = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM physique_quests WHERE is_active = 1')
    active_physique_quests = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM exercise_records')
    total_exercise_records = cursor.fetchone()[0] or 0

    conn.close()
    
    return jsonify({
        'success': True,
        'stats': {
            'total_users': total_users,
            'total_admins': total_admins,
            'total_workouts': total_workouts,
            'total_quests_completed': total_quests_completed,
            'active_physique_quests': active_physique_quests,
            'total_exercise_records': total_exercise_records,
            'system_status': 'OPERATIONAL'
        }
    })


@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_get_users():
    """Get all users with stats & ranks"""
    query = request.args.get('search', '').strip()
    users = user_manager.get_all_users(search_query=query if query else None)
    
    for u in users:
        u['rank'] = get_rank_from_level(u.get('level') or 1)
        u['is_admin'] = bool(u.get('is_admin'))
        
    return jsonify({
        'success': True,
        'count': len(users),
        'users': users
    })


@app.route('/api/admin/users/<int:target_id>/update-stats', methods=['POST'])
@admin_required
def admin_update_user_stats(target_id: int):
    """Update stats, level, EXP, or role of any user"""
    data = request.json or {}
    
    user = user_manager.get_user_by_id(target_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    username = (data.get('username') or user['username']).strip()
    email = (data.get('email') or user['email']).strip().lower()
    is_admin = 1 if data.get('is_admin') else 0
    
    if not user_manager.update_user_admin(target_id, username, email, is_admin):
        return jsonify({'error': 'Username or email already taken'}), 409
        
    level = data.get('level')
    exp = data.get('exp')
    exp_next = data.get('exp_to_next_level')
    stat_pts = data.get('stat_points')
    str_val = data.get('strength')
    end_val = data.get('endurance')
    agi_val = data.get('agility')
    vit_val = data.get('vitality')
    
    try:
        level = int(level) if level is not None else None
        exp = int(exp) if exp is not None else None
        exp_next = int(exp_next) if exp_next is not None else None
        stat_pts = int(stat_pts) if stat_pts is not None else None
        str_val = int(str_val) if str_val is not None else None
        end_val = int(end_val) if end_val is not None else None
        agi_val = int(agi_val) if agi_val is not None else None
        vit_val = int(vit_val) if vit_val is not None else None
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid numerical value provided'}), 400
        
    stats_manager.update_player_stats_admin(
        user_id=target_id,
        level=level,
        exp=exp,
        exp_to_next_level=exp_next,
        stat_points=stat_pts,
        strength=str_val,
        endurance=end_val,
        agility=agi_val,
        vitality=vit_val
    )
    
    print(f"👑 Admin updated user #{target_id} ({username}): Level {level}, Admin={is_admin}")
    
    return jsonify({
        'success': True,
        'message': f"Updated stats for user '{username}' successfully."
    })


@app.route('/api/admin/users/<int:target_id>/reset-password', methods=['POST'])
@admin_required
def admin_reset_password(target_id: int):
    """Force password reset for any user"""
    data = request.json or {}
    new_password = data.get('new_password') or ''
    
    if not new_password or len(new_password) < 4:
        return jsonify({'error': 'Password must be at least 4 characters long'}), 400
        
    user = user_manager.get_user_by_id(target_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    user_manager.reset_password_admin(target_id, new_password)
    print(f"👑 Admin reset password for user #{target_id} ({user['username']})")
    
    return jsonify({
        'success': True,
        'message': f"Password for '{user['username']}' has been updated."
    })


@app.route('/api/admin/users/<int:target_id>/delete', methods=['POST'])
@admin_required
def admin_delete_user(target_id: int):
    """Delete a user account and all associated records"""
    current_admin_id = session['user_id']
    if target_id == current_admin_id:
        return jsonify({'error': 'You cannot delete your own admin account while logged in.'}), 400
        
    user = user_manager.get_user_by_id(target_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    user_manager.delete_user_cascade(target_id)
    print(f"👑 Admin deleted user #{target_id} ({user['username']})")
    
    return jsonify({
        'success': True,
        'message': f"User '{user['username']}' and all associated data deleted."
    })


@app.route('/api/admin/god-mode', methods=['POST'])
@admin_required
def admin_activate_god_mode():
    """Grant God Mode (Level 100, Rank SS, Max Attributes, 500 Stat Points)"""
    data = request.json or {}
    target_id = data.get('target_user_id') or session['user_id']
    
    user = user_manager.get_user_by_id(target_id)
    if not user:
        return jsonify({'error': 'Target user not found'}), 404
        
    stats_manager.grant_god_mode(target_id)
    print(f"⚡ God Mode activated for user #{target_id} ({user['username']})!")
    
    return jsonify({
        'success': True,
        'message': f"⚡ God Mode activated for '{user['username']}'! Level 100 & max attributes granted."
    })


@app.route('/api/admin/activity', methods=['GET'])
@admin_required
def admin_get_activity():
    """Get system-wide activity feed across all users"""
    conn = db.get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT wh.id, wh.user_id, u.username, wh.workout_date, wh.total_exercises,
               wh.total_reps, wh.total_duration_minutes, wh.exp_gained, wh.created_at
        FROM workout_history wh
        JOIN users u ON wh.user_id = u.id
        ORDER BY wh.created_at DESC
        LIMIT 50
    ''')
    workouts = [dict(r) for r in cursor.fetchall()]
    
    cursor.execute('''
        SELECT qc.id, qc.user_id, u.username, qc.exercise_name, qc.reps_completed,
               qc.sets_completed, qc.weight_used, qc.completed_at
        FROM quest_completions qc
        JOIN users u ON qc.user_id = u.id
        ORDER BY qc.completed_at DESC
        LIMIT 50
    ''')
    completions = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        'success': True,
        'workouts': workouts,
        'completions': completions
    })


@app.route('/api/admin/exercises', methods=['GET'])
@admin_required
def admin_get_exercises():
    """Get exercise catalog"""
    exercises = exercise_manager.get_all_exercises()
    return jsonify({'success': True, 'exercises': exercises})


# ==========================================
# 🛑 PENALTY ZONE & HUNTER CARD API ENDPOINTS
# ==========================================

@app.route('/api/penalty/status', methods=['GET'])
@login_required
def get_penalty_status():
    """Penalty feature completely disabled"""
    return jsonify({
        'success': True,
        'has_penalty': False,
        'penalty': None
    })


@app.route('/api/quest/skip', methods=['POST'])
@login_required
def skip_workout():
    """Skip today's workout and trigger Penalty Zone emergency quest"""
    user_id = session.get('user_id')
    username = session.get('username', 'Unknown')
    
    quest_data = quest_generator.generate_penalty_quest(user_id)
    penalty = penalty_manager.create_penalty(
        user_id=user_id,
        quest_data=quest_data,
        duration_hours=4,
        reason="Skipped Daily Workout Protocol"
    )
    print(f"🚨 User '{username}' skipped workout -> Penalty Zone Initiated (ID: {penalty.get('id')})")
    
    return jsonify({
        'success': True,
        'message': 'WARNING: Workout skipped! Emergency Penalty Zone initiated.',
        'penalty': penalty
    })


@app.route('/api/penalty/trigger', methods=['POST'])
@login_required
def trigger_penalty_zone():
    """Trigger a Penalty Zone survival quest for the current user"""
    user_id = session.get('user_id')
    quest_data = quest_generator.generate_penalty_quest(user_id)
    penalty = penalty_manager.create_penalty(
        user_id=user_id,
        quest_data=quest_data,
        duration_hours=4,
        reason="Missed Daily System Workout Protocol"
    )
    return jsonify({
        'success': True,
        'message': 'WARNING: PENALTY QUEST INITIATED!',
        'penalty': penalty
    })


@app.route('/api/penalty/complete', methods=['POST'])
@login_required
def complete_penalty_zone():
    """Submit completion for an active Penalty Zone quest"""
    user_id = session.get('user_id')
    data = request.get_json() or {}
    penalty_id = data.get('penalty_id')

    penalty = penalty_manager.get_active_penalty(user_id)
    if not penalty or penalty.get('status') != 'active':
        return jsonify({'success': False, 'message': 'No active Penalty Quest found'}), 400

    penalty_manager.clear_penalty(penalty['id'], user_id)

    # Award survival bonus EXP (500 EXP)
    exp_gained = 500
    level_result = stats_manager.add_exp(user_id, exp_gained)

    return jsonify({
        'success': True,
        'message': 'PENALTY QUEST CLEARED! You survived the desert of the damned.',
        'exp_gained': exp_gained,
        'level_result': level_result
    })


@app.route('/api/hunter-card/data', methods=['GET'])
@login_required
def get_hunter_card_data():
    """Return structured profile data formatted for the Holographic S-Rank Hunter ID Card"""
    user_id = session.get('user_id')
    user = user_manager.get_user_by_id(user_id)
    stats = stats_manager.get_player_stats(user_id) or {}

    lvl = stats.get('level', 1)
    rank_info = get_hunter_rank(lvl)

    # Get achievement count
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) as cnt FROM achievements WHERE user_id = ?', (user_id,))
    achievements_cnt = cursor.fetchone()['cnt']

    # Get total workouts count
    cursor.execute('SELECT COUNT(*) as cnt FROM daily_quests WHERE user_id = ? AND completed = 1', (user_id,))
    quests_completed = cursor.fetchone()['cnt']
    conn.close()

    return jsonify({
        'success': True,
        'hunter': {
            'username': user.get('username', 'Hunter') if user else 'Hunter',
            'created_at': user.get('created_at', '') if user else '',
            'level': lvl,
            'exp': stats.get('exp', 0),
            'exp_to_next': stats.get('exp_to_next_level', 100),
            'rank': rank_info['rank'],
            'title': rank_info['title'],
            'badge_color': rank_info['badge_color'],
            'glow': rank_info['glow'],
            'border_color': rank_info['border_color'],
            'card_bg': rank_info.get('card_bg'),
            'ring_bg': rank_info.get('ring_bg'),
            'card_shadow': rank_info.get('card_shadow'),
            'emblem': rank_info.get('emblem', '⚔️'),
            'stats': {
                'strength': stats.get('strength', 10),
                'endurance': stats.get('endurance', 10),
                'agility': stats.get('agility', 10),
                'vitality': stats.get('vitality', 10),
            },
            'measurements': {
                'height_cm': stats.get('height_cm', 175),
                'weight_kg': stats.get('weight_kg', 70),
            },
            'achievements_count': achievements_cnt,
            'quests_completed': quests_completed,
            'days_per_week': stats.get('days_per_week', 5)
        }
    })


@app.route('/api/hunter/public/<identifier>', methods=['GET'])
def get_public_hunter_profile(identifier):
    """Get public hunter profile and friendship status for sharing links"""
    current_user_id = session.get('user_id')
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Fetch user by ID if numeric, otherwise by username
    if identifier.isdigit():
        cursor.execute('SELECT id, username, created_at FROM users WHERE id = ?', (int(identifier),))
    else:
        cursor.execute('SELECT id, username, created_at FROM users WHERE LOWER(username) = LOWER(?)', (identifier,))
        
    user = cursor.fetchone()
    if not user:
        conn.close()
        return jsonify({'error': 'Hunter profile not found'}), 404
        
    target_id = user['id']
    stats = stats_manager.get_player_stats(target_id) or {}
    lvl = stats.get('level', 1)
    rank_info = get_hunter_rank(lvl)
    
    cursor.execute('SELECT COUNT(*) as cnt FROM achievements WHERE user_id = ?', (target_id,))
    achievements_cnt = cursor.fetchone()['cnt']
    
    cursor.execute('SELECT COUNT(*) as cnt FROM daily_quests WHERE user_id = ? AND completed = 1', (target_id,))
    quests_completed = cursor.fetchone()['cnt']
    
    friendship_status = 'none'
    if current_user_id:
        if current_user_id == target_id:
            friendship_status = 'self'
        else:
            cursor.execute('''
                SELECT status, user_id FROM friends
                WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)
            ''', (current_user_id, target_id, target_id, current_user_id))
            f = cursor.fetchone()
            if f:
                if f['status'] == 'accepted':
                    friendship_status = 'accepted'
                elif f['user_id'] == current_user_id:
                    friendship_status = 'pending_sent'
                else:
                    friendship_status = 'pending_received'
                    
    conn.close()
    
    return jsonify({
        'success': True,
        'hunter': {
            'id': target_id,
            'username': user['username'],
            'created_at': user['created_at'],
            'level': lvl,
            'exp': stats.get('exp', 0),
            'exp_to_next': stats.get('exp_to_next_level', 100),
            'rank': rank_info['rank'],
            'title': rank_info['title'],
            'badge_color': rank_info['badge_color'],
            'glow': rank_info['glow'],
            'border_color': rank_info['border_color'],
            'card_bg': rank_info.get('card_bg'),
            'ring_bg': rank_info.get('ring_bg'),
            'card_shadow': rank_info.get('card_shadow'),
            'emblem': rank_info.get('emblem', '⚔️'),
            'stats': {
                'strength': stats.get('strength', 10),
                'endurance': stats.get('endurance', 10),
                'agility': stats.get('agility', 10),
                'vitality': stats.get('vitality', 10),
            },
            'achievements_count': achievements_cnt,
            'quests_completed': quests_completed,
            'friendship_status': friendship_status
        }
    })


# ==========================================
# 💪 1RM CALCULATOR & CUSTOM ROUTINE ENDPOINTS
# ==========================================

@app.route('/api/tools/1rm-calculate', methods=['POST'])
@login_required
def calculate_1rm():
    user_id = session.get('user_id')
    data = request.get_json() or {}

    exercise_name = data.get('exercise_name', 'Bench Press')
    try:
        weight_kg = float(data.get('weight_kg', 0))
        reps = int(data.get('reps', 0))
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Invalid weight or reps'}), 400

    if weight_kg <= 0 or reps <= 0:
        return jsonify({'success': False, 'message': 'Weight and reps must be greater than 0'}), 400

    formulas = StrengthCalculator.calculate_1rm(weight_kg, reps)
    est_1rm = formulas['average']
    percentages = StrengthCalculator.get_working_percentages(est_1rm)

    player_stats = stats_manager.get_player_stats(user_id) or {}
    bodyweight = player_stats.get('weight_kg', 75.0)
    benchmark = StrengthCalculator.get_strength_benchmark(exercise_name, bodyweight, est_1rm)

    routine_manager.log_1rm_test(user_id, exercise_name, weight_kg, reps, est_1rm, benchmark['tier'])

    return jsonify({
        'success': True,
        'exercise_name': exercise_name,
        'weight_kg': weight_kg,
        'reps': reps,
        'formulas': formulas,
        'estimated_1rm': est_1rm,
        'working_percentages': percentages,
        'benchmark': benchmark
    })

@app.route('/api/tools/1rm-history', methods=['GET'])
@login_required
def get_1rm_history():
    user_id = session.get('user_id')
    history = routine_manager.get_1rm_history(user_id)
    return jsonify({'success': True, 'history': history})

@app.route('/api/routines', methods=['GET'])
@login_required
def get_routines():
    user_id = session.get('user_id')
    routines = routine_manager.get_user_routines(user_id)
    return jsonify({'success': True, 'routines': routines})

@app.route('/api/routines', methods=['POST'])
@login_required
def create_routine():
    user_id = session.get('user_id')
    data = request.get_json() or {}

    routine_name = (data.get('routine_name') or '').strip()
    split_type = (data.get('split_type') or 'Custom').strip()
    description = (data.get('description') or '').strip()
    exercises = data.get('exercises') or []

    if not routine_name:
        return jsonify({'success': False, 'message': 'Routine name is required'}), 400

    if not exercises or not isinstance(exercises, list):
        return jsonify({'success': False, 'message': 'At least one exercise is required'}), 400

    routine = routine_manager.create_routine(user_id, routine_name, split_type, exercises, description)
    return jsonify({'success': True, 'routine': routine, 'message': 'Custom routine saved successfully!'})

@app.route('/api/routines/<int:routine_id>', methods=['DELETE'])
@login_required
def delete_routine(routine_id):
    user_id = session.get('user_id')
    success = routine_manager.delete_routine(routine_id, user_id)
    if success:
        return jsonify({'success': True, 'message': 'Routine deleted successfully'})
    return jsonify({'success': False, 'message': 'Routine not found'}), 404

@app.route('/api/routines/<int:routine_id>/launch', methods=['POST'])
@login_required
def launch_routine(routine_id):
    """Launch a custom routine as today's active workout quest"""
    user_id = session.get('user_id')
    routine = routine_manager.get_routine_by_id(routine_id, user_id)
    if not routine:
        return jsonify({'success': False, 'message': 'Routine not found'}), 404

    quest_data = {
        'title': f"CUSTOM ROUTINE: {routine['routine_name'].upper()}",
        'subtitle': f"SPLIT: {routine['split_type'].upper()}",
        'description': routine.get('description') or "Custom user routine launched as daily workout.",
        'exercises': routine['exercises'],
        'exp_reward': 350 + (len(routine['exercises']) * 50),
        'completion_bonus': 100
    }

    conn = db.get_connection()
    cursor = conn.cursor()
    today_str = datetime.now().strftime('%Y-%m-%d')
    quest_json = json.dumps(quest_data)

    cursor.execute('''
        INSERT INTO daily_quests (user_id, quest_date, quest_data, exp_reward)
        VALUES (?, ?, ?, ?)
    ''', (user_id, today_str, quest_json, quest_data['exp_reward']))

    new_quest_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'message': f"🚀 '{routine['routine_name']}' launched as today's active workout!",
        'quest_id': new_quest_id,
        'quest_data': quest_data
    })



if __name__ == '__main__':
    print("\n" + "="*60)
    print("⚔️  BODY SYNC FITNESS SYSTEM")
    print("="*60)
    print("\n🚀 Server starting...")
    print(f"📍 Access at: http://localhost:5000")
    print(f"📊 Database: {db.db_path}")
    print("\n💡 Tip: Check this terminal for quest generation logs")
    print("\n" + "="*60 + "\n")
    run_host = os.environ.get('FLASK_RUN_HOST', '127.0.0.1')
    run_port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    
    app.run(debug=debug_mode, host=run_host, port=run_port)

