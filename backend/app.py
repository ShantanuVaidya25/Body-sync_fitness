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

from models import Database, User, PlayerStats, ExerciseManager, WeeklyPlanManager, UserSettings
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

# Auto-seed default admin account on server startup
try:
    user_manager.ensure_admin_user()
except Exception as e:
    print(f"⚠️ Admin account initialization error: {e}")

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
    """Get 7-day weekly workout activity calendar data for Sunday to Saturday"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    user_id = session['user_id']
    conn = db.get_connection()
    cursor = conn.cursor()
    
    today = datetime.now().date()
    days_since_sunday = (today.weekday() + 1) % 7
    sunday = today - timedelta(days=days_since_sunday)
    
    day_codes = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']
    week_days = []
    
    for i in range(7):
        current_date = sunday + timedelta(days=i)
        date_str = current_date.strftime('%Y-%m-%d')
        
        cursor.execute('''
            SELECT COUNT(*) FROM quest_completions 
            WHERE user_id = ? AND DATE(completed_at) = ?
        ''', (user_id, date_str))
        count = cursor.fetchone()[0] or 0
        
        if count == 0:
            cursor.execute('''
                SELECT total_exercises FROM workout_history 
                WHERE user_id = ? AND workout_date = ?
            ''', (user_id, date_str))
            row = cursor.fetchone()
            if row and row[0]:
                count = row[0]
                
        week_days.append({
            'day_code': day_codes[i],
            'date': date_str,
            'count': count,
            'is_today': current_date == today
        })
        
    stats = stats_manager.get_player_stats(user_id)
    current_level = stats['level'] if stats else 1
    
    cursor.execute('''
        SELECT COUNT(DISTINCT DATE(completed_at)) FROM quest_completions WHERE user_id = ?
    ''', (user_id,))
    total_completed_days = cursor.fetchone()[0] or 0
    
    rank_ups = (current_level - 1) + total_completed_days
    conn.close()
    
    return jsonify({
        'success': True,
        'rank_ups': rank_ups,
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
    
    if not all([age, height_cm, weight_kg]):
        return jsonify({'error': 'Missing required fields'}), 400
    
    if not primary_focus_areas:
        return jsonify({'error': 'Please select at least one objective from your Primary Objective Path'}), 400
    
    # Create player stats
    success = stats_manager.create_player_stats(
        user_id, age, height_cm, weight_kg,
        target_height, target_weight,
        primary_focus_areas, experience_level, days_per_week
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
            print(f"   EXP gained: {result['exp_gained']}")
            if result['level_result'].get('leveled_up'):
                print(f"   🎉 LEVEL UP! New level: {result['level_result']['new_level']}")
        
        return jsonify(result)
        
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
    """Update goal progress"""
    data = request.json
    user_id = session['user_id']
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if 'current_value' in data:
        updates.append('current_value = ?')
        params.append(data['current_value'])
    
    if 'status' in data:
        updates.append('status = ?')
        params.append(data['status'])
        if data['status'] == 'completed':
            updates.append('completed_at = ?')
            params.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    
    params.extend([user_id, goal_id])
    
    cursor.execute(f'''
        UPDATE goals 
        SET {', '.join(updates)}
        WHERE user_id = ? AND id = ?
    ''', params)
    
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
    
    try:
        result = analyzer.generate_quest_log(
            target_name=target_name,
            image_path=image_path
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
            target_name=result.get('target_name')
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
    analyzer = get_analyzer_for_user(user_id)
    weekly_result = analyzer.extract_structured_weekly_plan(quest_log_markdown, target_name=target_name)
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
        WHERE u.username LIKE ? AND u.id != ?
        LIMIT 20
    ''', (user_id, user_id, f'%{query}%', user_id))
    
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
    """Get global or friends leaderboard with friendship status"""
    user_id = session['user_id']
    scope = request.args.get('scope', 'global')
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    if scope == 'friends':
        cursor.execute('''
            SELECT u.id, u.username, ps.level, ps.exp, ps.strength, 
                   ps.endurance, ps.agility, ps.vitality,
                   f_sub.status as friendship_status,
                   f_sub.user_id as request_sender_id
            FROM player_stats ps
            JOIN users u ON (ps.user_id = u.id)
            LEFT JOIN friends f_sub ON (
                (f_sub.user_id = ? AND f_sub.friend_id = u.id) OR 
                (f_sub.user_id = u.id AND f_sub.friend_id = ?)
            )
            WHERE ps.user_id IN (
                SELECT friend_id FROM friends 
                WHERE user_id = ? AND status = 'accepted'
            ) OR ps.user_id = ?
            ORDER BY ps.level DESC, ps.exp DESC
            LIMIT 50
        ''', (user_id, user_id, user_id, user_id))
    else:
        cursor.execute('''
            SELECT u.id, u.username, ps.level, ps.exp, ps.strength,
                   ps.endurance, ps.agility, ps.vitality,
                   f_sub.status as friendship_status,
                   f_sub.user_id as request_sender_id
            FROM player_stats ps
            JOIN users u ON (ps.user_id = u.id)
            LEFT JOIN friends f_sub ON (
                (f_sub.user_id = ? AND f_sub.friend_id = u.id) OR 
                (f_sub.user_id = u.id AND f_sub.friend_id = ?)
            )
            ORDER BY ps.level DESC, ps.exp DESC
            LIMIT 100
        ''', (user_id, user_id))
    
    leaderboard = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return jsonify({'leaderboard': leaderboard})


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
    """Get progress data for charts"""
    user_id = session['user_id']
    days = request.args.get('days', 30, type=int)
    
    conn = db.get_connection()
    cursor = conn.cursor()
    
    # Get daily EXP gains
    cursor.execute('''
        SELECT quest_date as date, SUM(exp_reward) as exp
        FROM daily_quests
        WHERE user_id = ? 
        AND quest_date >= date('now', ? || ' days')
        AND completed = 1
        GROUP BY quest_date
        ORDER BY quest_date
    ''', (user_id, -days))
    
    exp_data = [dict(row) for row in cursor.fetchall()]
    
    # Get workout completions
    cursor.execute('''
        SELECT quest_date as date, COUNT(*) as workouts
        FROM daily_quests
        WHERE user_id = ?
        AND quest_date >= date('now', ? || ' days')
        AND completed = 1
        GROUP BY quest_date
        ORDER BY quest_date
    ''', (user_id, -days))
    
    workout_data = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
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
            'system_status': 'OVERLORD_OPERATIONAL'
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


if __name__ == '__main__':
    print("\n" + "="*60)
    print("⚔️  BODY SYNC FITNESS SYSTEM")
    print("="*60)
    print("\n🚀 Server starting...")
    print(f"📍 Access at: http://localhost:5000")
    print(f"📊 Database: {db.db_path}")
    print("\n💡 Tip: Check this terminal for quest generation logs")
    print("\n" + "="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)

