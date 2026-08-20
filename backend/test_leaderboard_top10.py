import unittest
import json
from app import app, db

class TestLeaderboardTop10(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_leaderboard_top10_limit(self):
        with self.app.session_transaction() as sess:
            sess['user_id'] = 1
            sess['username'] = 'admin'
        
        response = self.app.get('/api/leaderboard?scope=global')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        leaderboard = data.get('leaderboard', [])
        
        print(f"[*] Leaderboard count returned: {len(leaderboard)}")
        self.assertLessEqual(len(leaderboard), 10, "Leaderboard must not exceed 10 entries")
        
        response_f = self.app.get('/api/leaderboard?scope=friends')
        self.assertEqual(response_f.status_code, 200)
        data_f = json.loads(response_f.data)
        leaderboard_f = data_f.get('leaderboard', [])
        self.assertLessEqual(len(leaderboard_f), 10, "Friends leaderboard must not exceed 10 entries")
        print("[*] Top 10 Leaderboard Test Passed Successfully!")

if __name__ == '__main__':
    unittest.main()
