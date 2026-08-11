"""
Body Sync Fitness - AI Quest Generator
Generates personalized daily quests based on user stats, goals, and progression
"""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json
import math


class AIQuestGenerator:
    """AI-powered daily quest generator with progressive difficulty"""
    
    def __init__(self, db):
        self.db = db
        
        # Exercise categories and variations
        self.exercise_pool = {
            'strength': {
                'upper_body': [
                    'push_ups', 'pull_ups', 'dips', 'diamond_push_ups',
                    'wide_push_ups', 'pike_push_ups', 'archer_push_ups',
                    'decline_push_ups', 'clapping_push_ups', 'handstand_push_ups'
                ],
                'core': [
                    'crunches', 'planks', 'side_planks', 'russian_twists',
                    'bicycle_crunches', 'leg_raises', 'mountain_climbers',
                    'flutter_kicks', 'v_ups', 'hollow_body_holds'
                ],
                'lower_body': [
                    'squats', 'lunges', 'jump_squats', 'pistol_squats',
                    'bulgarian_splits', 'calf_raises', 'wall_sits',
                    'step_ups', 'glute_bridges', 'single_leg_deadlifts'
                ]
            },
            'cardio': {
                'running': ['sprints', 'jog', 'interval_run', 'hill_sprints'],
                'bodyweight': ['burpees', 'jumping_jacks', 'high_knees', 'butt_kicks'],
                'other': ['jump_rope', 'shadow_boxing', 'stair_climbing']
            },
            'flexibility': {
                'stretching': ['yoga', 'dynamic_stretches', 'static_stretches'],
                'mobility': ['hip_circles', 'arm_circles', 'neck_rolls']
            }
        }
        
        # Rest and recovery indicators
        self.recovery_metrics = {
            'low_intensity': 0.5,
            'medium_intensity': 1.0,
            'high_intensity': 1.5,
            'very_high_intensity': 2.0
        }
    
    def calculate_difficulty_level(self, user_id: int) -> int:
        """Calculate user's current difficulty level based on stats and history"""
        from models import PlayerStats, ExerciseManager
        
        stats_manager = PlayerStats(self.db)
        exercise_manager = ExerciseManager(self.db)
        
        stats = stats_manager.get_player_stats(user_id)
        exercises = exercise_manager.get_user_exercises(user_id)
        
        if not stats:
            return 1
        
        # Base difficulty on level
        base_difficulty = stats['level']
        
        # Adjust based on stat total
        stat_total = (stats['strength'] + stats['endurance'] + 
                     stats['agility'] + stats['vitality'])
        stat_modifier = stat_total // 50  # +1 difficulty per 50 total stats
        
        # Adjust based on exercise mastery
        mastery_modifier = len([e for e in exercises if e['personal_record'] > 50]) // 5
        
        return min(base_difficulty + stat_modifier + mastery_modifier, 100)
    
    def generate_daily_quest(self, user_id: int, goals: List[Dict],
                            primary_focus_areas: List[str] = None) -> Dict:
        """Generate a personalized daily quest based on goals and stats"""
        from models import PlayerStats, ExerciseManager, WeeklyPlanManager
        
        stats_manager = PlayerStats(self.db)
        exercise_manager = ExerciseManager(self.db)
        weekly_plan_manager = WeeklyPlanManager(self.db)
        
        stats = stats_manager.get_player_stats(user_id)
        exercises = exercise_manager.get_user_exercises(user_id)
        difficulty = self.calculate_difficulty_level(user_id)
        
        todays_plan = weekly_plan_manager.get_plan_for_today(user_id)
        if todays_plan is None:
            active_physique = self.get_active_physique_quest(user_id)
            if active_physique:
                from physique_analyzer import parse_weekly_plan_from_markdown
                fallback_days = parse_weekly_plan_from_markdown(
                    active_physique.get('quest_log_markdown', ''),
                    active_physique.get('target_name')
                )
                weekly_plan_manager.save_weekly_plan(user_id, active_physique['id'], fallback_days)
                todays_plan = weekly_plan_manager.get_plan_for_today(user_id)

        if todays_plan is not None:
            if todays_plan['is_rest']:
                return self.generate_rest_day_quest(user_id, plan_focus=todays_plan.get('focus'))
            return self.build_quest_from_weekly_plan(user_id, todays_plan, difficulty)
        
        # Check if today should be a rest day
        if self.should_rest_today(user_id):
            return self.generate_rest_day_quest(user_id)
        
        # Prefer the user's explicit multi-select "Primary Objective Path" choices.
        # Fall back to inferring focus from active goal entries if none are set.
        if primary_focus_areas is None:
            primary_focus_areas = stats_manager.get_primary_focus_areas(user_id) if stats else []
        
        if primary_focus_areas:
            focus_areas = self.map_objective_paths(primary_focus_areas)
        else:
            focus_areas = self.analyze_goals(goals)
        
        # Generate quest structure
        quest = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'title': self.generate_quest_title(difficulty, focus_areas),
            'difficulty': difficulty,
            'exercises': [],
            'exp_reward': self.calculate_exp_reward(difficulty),
            'completion_bonus': self.calculate_exp_reward(difficulty) // 2,
            'focus_areas': focus_areas
        }
        
        # Generate exercises based on focus areas
        exercise_count = self.get_exercise_count(difficulty, stats['endurance'])
        
        for i in range(exercise_count):
            exercise = self.generate_exercise_task(
                user_id, focus_areas, difficulty, exercises, i
            )
            quest['exercises'].append(exercise)
        
        # Add variety with optional bonus tasks
        if difficulty >= 5 and random.random() < 0.3:
            bonus = self.generate_bonus_task(user_id, difficulty)
            quest['bonus_task'] = bonus
        
        return quest
    
    def should_rest_today(self, user_id: int) -> bool:
        """Determine if user should rest based on recent activity"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Check last 7 days of activity
        cursor.execute('''
            SELECT COUNT(*) as workout_days
            FROM daily_quests
            WHERE user_id = ? 
            AND quest_date >= date('now', '-7 days')
            AND completed = 1
        ''', (user_id,))
        
        result = cursor.fetchone()
        workout_days = result['workout_days'] if result else 0
        
        today_str = datetime.now().strftime('%Y-%m-%d')
        # Check if scheduled rest day
        cursor.execute('''
            SELECT COUNT(*) as rest_scheduled
            FROM rest_schedule
            WHERE user_id = ? AND rest_day = ?
        ''', (user_id, today_str))
        
        rest_scheduled = cursor.fetchone()['rest_scheduled']
        conn.close()
        
        # Rest if: scheduled rest day OR worked out 6+ days straight
        return rest_scheduled > 0 or workout_days >= 6
    
    def get_active_physique_quest(self, user_id: int) -> Optional[Dict]:
        """Fetch active physique build goal for the user if present"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, target_name, source_type, image_path, quest_log_markdown, created_at
            FROM physique_quests
            WHERE user_id = ? AND is_active = 1
            ORDER BY created_at DESC LIMIT 1
        ''', (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def generate_rest_day_quest(self, user_id: int, plan_focus: str = None) -> Dict:
        """Generate a recovery-focused quest for rest days"""
        active_physique = self.get_active_physique_quest(user_id)
        target_name = active_physique.get('target_name') if active_physique else None
        
        if target_name:
            title = f'🛌 Main Story Quest: Becoming {target_name} (Rest & Recovery)'
            notes = f'Scheduled rest day from {target_name}\'s training split ({plan_focus or "Recovery"}). Growth occurs during rest!'
        else:
            title = '🛌 Recovery Day: Active Rest'
            notes = 'Rest is crucial for growth. Take it easy today, Hunter!'
        
        if plan_focus and not target_name:
            notes = f'Scheduled rest day from your active build plan ({plan_focus}). Recovery is part of the training, not a break from it.'
        
        return {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'title': title,
            'target_name': target_name,
            'physique_quest_id': active_physique.get('id') if active_physique else None,
            'difficulty': 1,
            'is_rest_day': True,
            'exercises': [
                {
                    'name': 'Light Stretching',
                    'category': 'flexibility',
                    'sets': 1,
                    'duration_minutes': 15,
                    'description': 'Gentle full-body stretching routine'
                },
                {
                    'name': 'Walking',
                    'category': 'cardio',
                    'sets': 1,
                    'duration_minutes': 20,
                    'description': 'Light walk to promote blood flow'
                },
                {
                    'name': 'Meditation or Deep Breathing',
                    'category': 'recovery',
                    'sets': 1,
                    'duration_minutes': 10,
                    'description': 'Mental recovery and relaxation'
                }
            ],
            'exp_reward': 50,
            'completion_bonus': 25,
            'notes': notes
        }
    
    def build_quest_from_weekly_plan(self, user_id: int, plan_entry: Dict,
                                     difficulty: int) -> Dict:
        """
        Convert today's entry from the user's active "Become Like..." weekly
        training split into the same quest schema the rest of the app uses,
        so it renders and completes identically to an algorithmic quest.
        """
        active_physique = self.get_active_physique_quest(user_id)
        target_name = active_physique.get('target_name') if active_physique else None
        
        cardio_keywords = ('run', 'sprint', 'jump rope', 'row', 'bike', 'cycling',
                           'cardio', 'hiit', 'jog', 'burpee', 'mountain climber')
        flexibility_keywords = ('stretch', 'yoga', 'mobility', 'foam roll')
        
        exercises = []
        for ex in plan_entry.get('exercises', []):
            name_lower = ex.get('name', '').lower()
            if any(kw in name_lower for kw in cardio_keywords):
                category = 'cardio'
            elif any(kw in name_lower for kw in flexibility_keywords):
                category = 'flexibility'
            else:
                category = 'strength'
            
            # Parse a usable integer target from strings like "8-10", "12", "15 min", or "until failure"
            reps_str = str(ex.get('reps', '10')).strip()
            digits = ''.join(c for c in reps_str.split('-')[0] if c.isdigit())
            parsed_val = int(digits) if digits else 10
            
            target_reps = parsed_val if category != 'flexibility' else None
            target_duration = parsed_val if category == 'flexibility' else None
            
            exercises.append({
                'name': ex.get('name', 'Exercise'),
                'category': category,
                'sets': ex.get('sets', 3),
                'target_reps': target_reps,
                'target_duration_minutes': target_duration,
                'rest_between_sets': ex.get('rest_seconds', 60),
                'exp_per_set': 10 + difficulty,
                'description': ex.get('notes') or (f"Part of {target_name}'s workout split" if target_name else "Part of your build-goal training split")
            })
        
        title = f"⚔️ Main Story Quest: Becoming {target_name} - {plan_entry.get('focus', 'Training Day')}" if target_name else f"⚔️ Main Story Quest: {plan_entry.get('focus', 'Training Day')}"

        return {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'title': title,
            'target_name': target_name,
            'physique_quest_id': active_physique.get('id') if active_physique else None,
            'difficulty': difficulty,
            'from_weekly_plan': True,
            'exercises': exercises,
            'exp_reward': self.calculate_exp_reward(difficulty),
            'completion_bonus': self.calculate_exp_reward(difficulty) // 2,
            'focus_areas': [plan_entry.get('focus', '')]
        }
    
    def get_weekly_schedule(self, user_id: int) -> Dict:
        """Get the full 7-day planned quest schedule for the user (Monday through Sunday)"""
        from models import WeeklyPlanManager
        weekly_plan_manager = WeeklyPlanManager(self.db)
        
        active_physique = self.get_active_physique_quest(user_id)
        target_name = active_physique.get('target_name') if active_physique else None
        physique_quest_id = active_physique.get('id') if active_physique else None
        quest_log_markdown = active_physique.get('quest_log_markdown') if active_physique else None

        difficulty = self.calculate_difficulty_level(user_id)
        today_weekday = datetime.now().weekday()  # Monday=0 ... Sunday=6
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        plan_days = weekly_plan_manager.get_all_days(user_id)
        if not plan_days and active_physique:
            from physique_analyzer import parse_weekly_plan_from_markdown
            fallback_days = parse_weekly_plan_from_markdown(
                active_physique.get('quest_log_markdown', ''),
                active_physique.get('target_name')
            )
            weekly_plan_manager.save_weekly_plan(user_id, active_physique['id'], fallback_days)
            plan_days = weekly_plan_manager.get_all_days(user_id)

        schedule = []
        
        if plan_days:
            # Plan exists from active "Become Like..." build goal
            for day in plan_days:
                w_day = day.get('day_of_week', 0)
                is_today = (w_day == today_weekday)
                is_rest = bool(day.get('is_rest', False))
                
                if is_rest:
                    quest_data = self.generate_rest_day_quest(user_id, plan_focus=day.get('focus'))
                else:
                    quest_data = self.build_quest_from_weekly_plan(user_id, day, difficulty)
                
                schedule.append({
                    'day_of_week': w_day,
                    'day_label': day.get('day_label') or day_names[w_day % 7],
                    'focus': day.get('focus', 'Workout'),
                    'is_rest': is_rest,
                    'is_today': is_today,
                    'quest': quest_data
                })
        else:
            # Algorithmic 7-day schedule based on primary objective path / goals
            for w_day in range(7):
                is_today = (w_day == today_weekday)
                is_rest = (w_day == 6)  # Default Sunday rest day
                
                if is_rest:
                    quest_data = self.generate_rest_day_quest(user_id)
                    focus = "Rest & Recovery"
                else:
                    focus_areas = ['strength', 'cardio', 'flexibility']
                    quest_data = {
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'title': f"⚔️ Daily Trial: Day {w_day+1}",
                        'difficulty': difficulty,
                        'exercises': [
                            self.generate_exercise_task(user_id, focus_areas, difficulty, [], i)
                            for i in range(min(3 + difficulty // 10, 6))
                        ],
                        'exp_reward': self.calculate_exp_reward(difficulty),
                        'completion_bonus': self.calculate_exp_reward(difficulty) // 2
                    }
                    focus = "General Conditioning"
                
                schedule.append({
                    'day_of_week': w_day,
                    'day_label': day_names[w_day],
                    'focus': focus,
                    'is_rest': is_rest,
                    'is_today': is_today,
                    'quest': quest_data
                })
        
        return {
            'has_active_build_goal': len(plan_days) > 0,
            'target_name': target_name,
            'physique_quest_id': physique_quest_id,
            'quest_log_markdown': quest_log_markdown,
            'schedule': schedule
        }
    
    # Maps the multi-select "Primary Objective Path" options (chosen at setup)
    # to the internal training focus categories used by exercise selection.
    OBJECTIVE_PATH_MAP = {
        'strength': ['strength'],
        'muscle_gain': ['strength'],
        'weight_loss': ['cardio', 'strength'],
        'endurance': ['cardio'],
        'flexibility': ['flexibility'],
        'height_growth': ['flexibility', 'strength'],
        'general_fitness': ['strength', 'cardio', 'flexibility'],
        'athletic_performance': ['cardio', 'strength', 'flexibility'],
    }
    
    def map_objective_paths(self, selected_paths: List[str]) -> List[str]:
        """Convert multi-selected objective paths into weighted training focus areas"""
        focus_areas = []
        for path in selected_paths:
            focus_areas.extend(self.OBJECTIVE_PATH_MAP.get(path, []))
        
        if not focus_areas:
            return ['strength', 'cardio', 'flexibility']
        
        return list(dict.fromkeys(focus_areas))  # de-dupe, preserve order/weighting
    
    def analyze_goals(self, goals: List[Dict]) -> List[str]:
        """Analyze user goals to determine training focus"""
        focus_areas = []
        
        for goal in goals:
            if goal['status'] != 'active':
                continue
            
            goal_type = goal['goal_type'].lower()
            
            if 'strength' in goal_type or 'muscle' in goal_type:
                focus_areas.append('strength')
            elif 'weight' in goal_type or 'fat' in goal_type:
                focus_areas.append('cardio')
            elif 'endurance' in goal_type or 'stamina' in goal_type:
                focus_areas.append('cardio')
            elif 'flexibility' in goal_type:
                focus_areas.append('flexibility')
            elif 'height' in goal_type:
                focus_areas.append('flexibility')
                focus_areas.append('strength')
        
        # Default to balanced if no specific goals
        if not focus_areas:
            focus_areas = ['strength', 'cardio', 'flexibility']
        
        return list(set(focus_areas))  # Remove duplicates
    
    def generate_quest_title(self, difficulty: int, focus_areas: List[str]) -> str:
        """Generate an epic quest title"""
        prefixes = [
            "⚔️ Daily Training:", "🔥 Hunter's Challenge:", "💪 Power-Up Mission:",
            "🎯 Today's Trial:", "⭐ Leveling Quest:", "🏆 Elite Training:",
            "🌟 Advancement Task:", "⚡ Growth Protocol:"
        ]
        
        focus_names = {
            'strength': ['Strength', 'Power', 'Might'],
            'cardio': ['Endurance', 'Stamina', 'Speed'],
            'flexibility': ['Agility', 'Mobility', 'Grace']
        }
        
        focus_text = " & ".join([
            random.choice(focus_names.get(area, ['Training']))
            for area in focus_areas[:2]
        ])
        
        rank = self.get_rank_name(difficulty)
        
        return f"{random.choice(prefixes)} {focus_text} [{rank} Rank]"
    
    def get_rank_name(self, difficulty: int) -> str:
        """Get rank name based on difficulty"""
        if difficulty < 5:
            return "E"
        elif difficulty < 10:
            return "D"
        elif difficulty < 20:
            return "C"
        elif difficulty < 35:
            return "B"
        elif difficulty < 50:
            return "A"
        elif difficulty < 70:
            return "S"
        else:
            return "SS"
    
    def get_exercise_count(self, difficulty: int, endurance: int) -> int:
        """Calculate number of exercises based on difficulty and endurance"""
        base_count = 3
        difficulty_bonus = difficulty // 10
        endurance_bonus = endurance // 20
        
        return min(base_count + difficulty_bonus + endurance_bonus, 8)
    
    def generate_exercise_task(self, user_id: int, focus_areas: List[str],
                               difficulty: int, existing_exercises: List[Dict],
                               exercise_index: int) -> Dict:
        """Generate a single exercise task"""
        from models import ExerciseManager
        
        exercise_manager = ExerciseManager(self.db)
        
        # Select category based on focus and rotation
        if exercise_index == 0:
            category = 'strength'
        elif exercise_index == 1 and 'cardio' in focus_areas:
            category = 'cardio'
        else:
            category = random.choice(focus_areas)
        
        # Get exercise name
        if category == 'strength':
            subcategory = random.choice(list(self.exercise_pool['strength'].keys()))
            exercise_name = random.choice(self.exercise_pool['strength'][subcategory])
        elif category == 'cardio':
            subcategory = random.choice(list(self.exercise_pool['cardio'].keys()))
            exercise_name = random.choice(self.exercise_pool['cardio'][subcategory])
        else:
            subcategory = random.choice(list(self.exercise_pool['flexibility'].keys()))
            exercise_name = random.choice(self.exercise_pool['flexibility'][subcategory])
        
        # Get user's history with this exercise
        exercise_record = exercise_manager.get_exercise_by_name(user_id, exercise_name)
        
        # Calculate target reps/duration
        if exercise_record:
            base_target = exercise_record['max_reps'] or exercise_record['max_duration_seconds']
            # Progress by 5-10% each time
            target = int(base_target * random.uniform(1.05, 1.15))
        else:
            # Beginner values
            target = self.get_beginner_target(exercise_name, difficulty)
        
        # Calculate sets
        sets = max(2, min(difficulty // 5 + 2, 5))
        
        # Create task
        task = {
            'name': self.format_exercise_name(exercise_name),
            'category': category,
            'sets': sets,
            'target_reps': target if category != 'flexibility' else None,
            'target_duration_minutes': max(1, math.ceil(target / 60)) if category == 'flexibility' else None,
            'rest_between_sets': self.calculate_rest_time(difficulty, category),
            'exp_per_set': 10 + difficulty,
            'description': self.get_exercise_description(exercise_name)
        }
        
        return task
    
    def format_exercise_name(self, exercise_name: str) -> str:
        """Format exercise name for display"""
        return ' '.join(word.capitalize() for word in exercise_name.split('_'))
    
    def get_beginner_target(self, exercise_name: str, difficulty: int) -> int:
        """Get beginner-friendly target for an exercise"""
        beginner_targets = {
            'push_ups': 10, 'pull_ups': 3, 'squats': 15, 'lunges': 10,
            'planks': 30, 'crunches': 15, 'burpees': 8, 'jumping_jacks': 20,
            'sprints': 30, 'jog': 300, 'mountain_climbers': 15
        }
        
        base = beginner_targets.get(exercise_name, 10)
        return int(base * (1 + difficulty * 0.1))
    
    def calculate_rest_time(self, difficulty: int, category: str) -> int:
        """Calculate rest time between sets in seconds"""
        if category == 'cardio':
            return 45 + (5 - difficulty // 10) * 15
        elif category == 'strength':
            return 60 + (5 - difficulty // 10) * 20
        else:
            return 30
    
    def get_exercise_description(self, exercise_name: str) -> str:
        """Get motivational description for exercise"""
        descriptions = {
            'push_ups': 'Build upper body strength and core stability',
            'pull_ups': 'Ultimate back and bicep developer',
            'squats': 'Leg power and explosive strength',
            'burpees': 'Full-body conditioning and stamina',
            'planks': 'Core strength and endurance',
            'sprints': 'Speed and explosive power training'
        }
        
        return descriptions.get(exercise_name, 'Progress your skills and power!')
    
    def generate_bonus_task(self, user_id: int, difficulty: int) -> Dict:
        """Generate optional bonus task for extra rewards"""
        bonus_tasks = [
            {
                'name': '💎 Perfect Form Challenge',
                'description': 'Complete all exercises with perfect form',
                'exp_bonus': 100 + difficulty * 10
            },
            {
                'name': '⚡ Speed Run',
                'description': 'Complete the workout 20% faster than usual',
                'exp_bonus': 150 + difficulty * 15
            },
            {
                'name': '🔥 Extra Set',
                'description': 'Add one extra set to each exercise',
                'exp_bonus': 200 + difficulty * 20
            },
            {
                'name': '🎯 Personal Record',
                'description': 'Beat at least one personal record today',
                'exp_bonus': 250 + difficulty * 25
            }
        ]
        
        return random.choice(bonus_tasks)
    
    def calculate_exp_reward(self, difficulty: int) -> int:
        """Calculate base EXP reward for completing quest"""
        base_exp = 50
        return int(base_exp * (1 + difficulty * 0.15))
    
    def save_daily_quest(self, user_id: int, quest: Dict) -> int:
        """Save generated quest to database"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        quest_data = json.dumps(quest)
        
        cursor.execute('''
            INSERT INTO daily_quests 
            (user_id, quest_date, quest_data, exp_reward)
            VALUES (?, ?, ?, ?)
        ''', (user_id, quest['date'], quest_data, quest['exp_reward']))
        
        quest_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return quest_id
    
    def get_todays_quest(self, user_id: int) -> Optional[Dict]:
        """Get today's quest for user"""
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        today_str = datetime.now().strftime('%Y-%m-%d')
        cursor.execute('''
            SELECT * FROM daily_quests
            WHERE user_id = ? AND quest_date = ?
            ORDER BY created_at DESC
            LIMIT 1
        ''', (user_id, today_str))
        
        quest_row = cursor.fetchone()
        conn.close()
        
        if quest_row:
            quest_data = json.loads(quest_row['quest_data'])
            quest_data['id'] = quest_row['id']
            quest_data['completed'] = bool(quest_row['completed'])
            
            active_physique = self.get_active_physique_quest(user_id)
            if active_physique:
                quest_data['target_name'] = active_physique.get('target_name')
                quest_data['physique_quest_id'] = active_physique.get('id')
                if not quest_data.get('title', '').startswith('⚔️ Main Story Quest') and not quest_data.get('title', '').startswith('🛌 Main Story Quest'):
                    focus_text = quest_data.get('focus_areas', ['Training'])[0] if quest_data.get('focus_areas') else 'Training'
                    quest_data['title'] = f"⚔️ Main Story Quest: Becoming {active_physique.get('target_name')} - {focus_text}"
            return quest_data
        
        return None

    def regenerate_daily_quest(self, user_id: int, goals: List[Dict],
                               primary_focus_areas: List[str] = None) -> Dict:
        """Delete today's uncompleted quest if present, then generate and save a fresh one"""
        today_str = datetime.now().strftime('%Y-%m-%d')
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Delete uncompleted quest for today
        cursor.execute('''
            DELETE FROM daily_quests
            WHERE user_id = ? AND quest_date = ? AND completed = 0
        ''', (user_id, today_str))
        
        conn.commit()
        conn.close()
        
        # Generate new quest
        quest = self.generate_daily_quest(user_id, goals, primary_focus_areas)
        quest_id = self.save_daily_quest(user_id, quest)
        quest['id'] = quest_id
        return quest
    
    def complete_quest(self, user_id: int, quest_id: int, 
                      exercise_completions: List[Dict]) -> Dict:
        """Mark quest as completed and award rewards"""
        from models import PlayerStats, ExerciseManager
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        
        # Get quest details
        cursor.execute('SELECT * FROM daily_quests WHERE id = ?', (quest_id,))
        quest_row = cursor.fetchone()
        
        if not quest_row or quest_row['completed']:
            conn.close()
            return {'success': False, 'message': 'Quest not found or already completed'}
        
        quest_data = json.loads(quest_row['quest_data'])
        
        # Save exercise completions
        for completion in exercise_completions:
            cursor.execute('''
                INSERT INTO quest_completions
                (user_id, quest_id, exercise_name, reps_completed, sets_completed,
                 weight_used, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, quest_id, completion.get('exercise_name'),
                  completion.get('reps', 0), completion.get('sets', 0),
                  completion.get('weight', 0), completion.get('duration', 0)))
        
        # Mark quest as completed
        cursor.execute('''
            UPDATE daily_quests
            SET completed = 1, completed_at = ?
            WHERE id = ?
        ''', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), quest_id))
        
        conn.commit()
        conn.close()
        
        # Award EXP
        stats_manager = PlayerStats(self.db)
        total_exp = quest_data['exp_reward'] + quest_data.get('completion_bonus', 0)
        level_result = stats_manager.add_exp(user_id, total_exp)
        
        # Update exercise records
        exercise_manager = ExerciseManager(self.db)
        for completion in exercise_completions:
            exercise_manager.add_or_update_exercise(
                user_id,
                completion.get('exercise_name'),
                completion.get('category', 'strength'),
                completion.get('reps', 0),
                completion.get('weight', 0),
                completion.get('duration', 0)
            )
        
        return {
            'success': True,
            'exp_gained': total_exp,
            'level_result': level_result,
            'message': 'Quest completed! You are growing stronger, Hunter!'
        }

    def generate_penalty_quest(self, user_id: int) -> Dict:
        """Generate a Solo Leveling Penalty Zone survival circuit quest"""
        from models import PlayerStats
        stats_mgr = PlayerStats(self.db)
        stats = stats_mgr.get_player_stats(user_id) or {}
        lvl = stats.get('level', 1)

        # Scale pushups, situps, squats, and running based on level
        pushups = min(20 + (lvl * 2), 100)
        situps = min(20 + (lvl * 2), 100)
        squats = min(20 + (lvl * 2), 100)
        run_km = min(2 + (lvl // 10), 10)

        exercises = [
            {
                'name': 'Push-Ups (Penalty Protocol)',
                'target_reps': pushups,
                'target_sets': 4,
                'reps_per_set': max(5, pushups // 4),
                'category': 'strength'
            },
            {
                'name': 'Sit-Ups (Penalty Protocol)',
                'target_reps': situps,
                'target_sets': 4,
                'reps_per_set': max(5, situps // 4),
                'category': 'core'
            },
            {
                'name': 'Bodyweight Squats (Penalty Protocol)',
                'target_reps': squats,
                'target_sets': 4,
                'reps_per_set': max(5, squats // 4),
                'category': 'lower_body'
            },
            {
                'name': f'Survival Run ({run_km} KM / High-Intensity Cardio)',
                'target_reps': run_km * 1000,
                'target_sets': 1,
                'reps_per_set': run_km * 1000,
                'category': 'cardio'
            }
        ]

        return {
            'title': 'WARNING: PENALTY QUEST INITIATED',
            'subtitle': 'SURVIVAL QUEST: SURVIVE THE DESERT OF THE DAMNED',
            'description': 'Failure to complete the daily system protocol has triggered the Penalty Quest. You must complete all survival exercises before the timer expires.',
            'exercises': exercises,
            'exp_reward': 500 + (lvl * 20),
            'penalty_duration_hours': 4,
            'warning': 'If you fail to survive within 4 hours, temporary stat penalties will be enforced by the System.'
        }

