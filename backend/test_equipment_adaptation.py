import os
import sys
import unittest

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from models import Database, PlayerStats, WeeklyPlanManager
from quest_generator import AIQuestGenerator
from physique_analyzer import PhysiqueAnalyzer, generate_character_equipment_split

class TestEquipmentAdaptation(unittest.TestCase):
    def setUp(self):
        self.db = Database('test_fitness.db')
        self.stats_mgr = PlayerStats(self.db)
        self.quest_gen = AIQuestGenerator(self.db)
        self.analyzer = PhysiqueAnalyzer()
        self.weekly_mgr = WeeklyPlanManager(self.db)
        self.user_id = 999
        
        # Setup test player
        self.stats_mgr.create_player_stats(
            user_id=self.user_id,
            age=22,
            height_cm=178,
            weight_kg=75,
            experience_level='intermediate',
            body_type='mesomorph',
            equipment='Full Commercial Gym'
        )

    def tearDown(self):
        if os.path.exists('test_fitness.db'):
            try:
                os.remove('test_fitness.db')
            except Exception:
                pass

    def test_exercise_pools_by_equipment(self):
        pool_gym = self.quest_gen.get_exercise_pool('Full Commercial Gym')
        pool_home = self.quest_gen.get_exercise_pool('Home / Bodyweight')
        pool_calisthenics = self.quest_gen.get_exercise_pool('Calisthenics')
        pool_db = self.quest_gen.get_exercise_pool('Dumbbells & Home Setup')

        # Verify Gym pool contains barbell / gym machines in strength
        self.assertIn('barbell_bench_press', pool_gym['strength']['upper_body'])
        self.assertIn('barbell_back_squats', pool_gym['strength']['lower_body'])
        self.assertIn('lat_pulldowns', pool_gym['strength']['upper_body'])

        # Verify Home pool is strictly floor bodyweight
        self.assertIn('push_ups', pool_home['strength']['upper_body'])
        self.assertIn('diamond_push_ups', pool_home['strength']['upper_body'])
        self.assertIn('squats', pool_home['strength']['lower_body'])
        self.assertNotIn('barbell_bench_press', pool_home['strength']['upper_body'])
        self.assertNotIn('leg_press', pool_home['strength']['lower_body'])

        # Verify Calisthenics pool contains bar & gymnastic movements
        self.assertIn('muscle_ups', pool_calisthenics['strength']['upper_body'])
        self.assertIn('handstand_push_ups', pool_calisthenics['strength']['upper_body'])
        self.assertIn('dragon_flags', pool_calisthenics['strength']['core'])
        self.assertIn('pistol_squats', pool_calisthenics['strength']['lower_body'])

        # Verify Dumbbell pool contains dumbbell movements
        self.assertIn('dumbbell_bench_press', pool_db['strength']['upper_body'])
        self.assertIn('goblet_squats', pool_db['strength']['lower_body'])
        self.assertIn('dumbbell_rows', pool_db['strength']['upper_body'])

    def test_daily_quest_equipment_filtering(self):
        # 1. Generate Gym quest
        self.stats_mgr.update_player_stats_settings(self.user_id, equipment='Full Commercial Gym')
        gym_quest = self.quest_gen.generate_daily_quest(self.user_id, [], [])
        self.assertIsNotNone(gym_quest)
        gym_exercises = [ex['name'] for ex in gym_quest['exercises']]
        print("Generated Gym Quest Exercises:", gym_exercises)

        # 2. Switch to Home and regenerate
        self.stats_mgr.update_player_stats_settings(self.user_id, equipment='Home / Bodyweight')
        home_quest = self.quest_gen.regenerate_daily_quest(self.user_id, [], [])
        self.assertIsNotNone(home_quest)
        home_exercises = [ex['name'] for ex in home_quest['exercises']]
        print("Generated Home Quest Exercises:", home_exercises)

        # Ensure no barbell or cable exercises in home quest
        for ex in home_exercises:
            self.assertNotIn('barbell', ex.lower())
            self.assertNotIn('cable', ex.lower())
            self.assertNotIn('machine', ex.lower())

    def test_character_equipment_split_generation(self):
        # Test Sung Jin-Woo split for Home vs Gym
        md_home, days_home = generate_character_equipment_split('Sung Jin-Woo', 'Home / Bodyweight')
        md_gym, days_gym = generate_character_equipment_split('Sung Jin-Woo', 'Full Commercial Gym')

        self.assertEqual(len(days_home), 7)
        self.assertEqual(len(days_gym), 7)

        # Home day 1 should have Diamond Push-ups / bodyweight
        home_ex_names = [e['name'] for e in days_home[0]['exercises']]
        self.assertIn('Diamond Push-ups', home_ex_names)

        # Gym day 1 should have Barbell Bench Press
        gym_ex_names = [e['name'] for e in days_gym[0]['exercises']]
        self.assertIn('Barbell Bench Press', gym_ex_names)

    def test_adapt_physique_quest_to_equipment(self):
        # Create active character quest
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO physique_quests (user_id, target_name, source_type, is_active, quest_log_markdown)
            VALUES (?, ?, ?, 1, ?)
        ''', (self.user_id, 'Sung Jin-Woo', 'character', 'Initial Gym Markdown'))
        quest_id = cursor.lastrowid
        conn.commit()
        conn.close()

        active_quest = {
            'id': quest_id,
            'target_name': 'Sung Jin-Woo',
            'source_type': 'character'
        }

        user_stats = self.stats_mgr.get_player_stats(self.user_id)

        # Adapt from Gym to Home
        res = self.analyzer.adapt_physique_quest_to_equipment(
            user_id=self.user_id,
            active_quest=active_quest,
            new_equipment='Home / Bodyweight',
            user_stats=user_stats,
            db=self.db
        )

        self.assertTrue(res['success'])
        self.assertEqual(res['equipment'], 'Home / Bodyweight')
        self.assertEqual(len(res['days']), 7)

        # Check DB weekly plan
        days = self.weekly_mgr.get_all_days(self.user_id)
        self.assertIsNotNone(days)
        self.assertEqual(len(days), 7)
        
        # Day 1 should be bodyweight push & core
        day1_exercises = days[0]['exercises']
        print("Adapted Day 1 Exercises for Home:", [e['name'] for e in day1_exercises])
        self.assertTrue(any('Push-up' in e['name'] for e in day1_exercises))


class TestFlaskEquipmentEndpoints(unittest.TestCase):
    def setUp(self):
        from app import app
        app.config['TESTING'] = True
        self.client = app.test_client()
        self.user_id = 998
        
        from models import Database, User, PlayerStats
        db = Database()
        user_mgr = User(db)
        stats_mgr = PlayerStats(db)
        
        # Create test user
        user = user_mgr.get_user_by_username('test_equipment_hunter')
        if not user:
            user_mgr.create_user('test_equipment_hunter', 'hunterpass123', 'hunter@solo.test')
            user = user_mgr.get_user_by_username('test_equipment_hunter')
            
        self.user_id = user['id']
        stats = stats_mgr.get_player_stats(self.user_id)
        if not stats:
            stats_mgr.create_player_stats(
                user_id=self.user_id,
                age=25,
                height_cm=180,
                weight_kg=80,
                experience_level='intermediate',
                body_type='mesomorph',
                equipment='Full Commercial Gym',
                injuries='None'
            )
        else:
            stats_mgr.update_player_stats_settings(
                user_id=self.user_id,
                equipment='Full Commercial Gym',
                injuries='None'
            )

    def test_change_equipment_endpoint(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id

        # 1. Change equipment from Gym to Home
        res = self.client.post('/api/player/change-equipment', json={
            'equipment': 'Home / Bodyweight'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['equipment'], 'Home / Bodyweight')
        self.assertIsNotNone(data['quest'])
        print("Endpoint switched to Home. New Quest:", data['quest']['title'], [e['name'] for e in data['quest']['exercises']])

        # 2. Change equipment to Dumbbells
        res = self.client.post('/api/player/change-equipment', json={
            'equipment': 'Dumbbells & Home Setup'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['equipment'], 'Dumbbells & Home Setup')
        print("Endpoint switched to Dumbbells. New Quest:", data['quest']['title'], [e['name'] for e in data['quest']['exercises']])

        # 3. Change equipment to Calisthenics without injury (Success)
        res = self.client.post('/api/player/change-equipment', json={
            'equipment': 'Calisthenics'
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['equipment'], 'Calisthenics')
        print("Endpoint switched to Calisthenics. New Quest:", data['quest']['title'], [e['name'] for e in data['quest']['exercises']])

        # 4. User registers fatal shoulder injury and attempts to switch to Calisthenics (Rejected 403)
        from models import Database, PlayerStats
        db = Database()
        stats_mgr = PlayerStats(db)
        stats_mgr.update_player_stats_settings(self.user_id, injuries='Shoulder Discomfort (Rotator Cuff)')

        res = self.client.post('/api/player/change-equipment', json={
            'equipment': 'Calisthenics'
        })
        self.assertEqual(res.status_code, 403)
        data = res.get_json()
        self.assertFalse(data['success'])
        self.assertTrue(data['blocked_by_injury'])
        self.assertIn('Shoulder Discomfort', data['injury_detected'])
        print("Injury Lock Rejection Verified:", data['message'])

        # 5. User forces safe override (Success)
        res = self.client.post('/api/player/change-equipment', json={
            'equipment': 'Calisthenics',
            'force_override': True
        })
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        print("Force Safe Override Verified. New Quest:", data['quest']['title'])


if __name__ == '__main__':
    unittest.main()
