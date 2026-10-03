import pytest
import sys
import os
from unittest.mock import Mock, patch

# Add backend directory to sys.path so 'import models' works inside quest_generator.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from quest_generator import AIQuestGenerator

@pytest.fixture
def mock_db():
    return Mock()

@pytest.fixture
def quest_generator(mock_db):
    return AIQuestGenerator(mock_db)

def test_get_exercise_pool(quest_generator):
    assert 'push_ups' in quest_generator.get_exercise_pool('none')['strength']['upper_body']
    # 'push_ups' is in bodyweight, calisthenics, gym might vary. 
    # Let's check specific equipment
    calisthenics_pool = quest_generator.get_exercise_pool('calisthenics')
    assert 'muscle_ups' in calisthenics_pool['strength']['upper_body']
    
    gym_pool = quest_generator.get_exercise_pool('Full Commercial Gym')
    assert 'barbell_bench_press' in gym_pool['strength']['upper_body']

def test_calculate_difficulty_level_beginner(quest_generator, mock_db):
    # Mocking PlayerStats and ExerciseManager
    with patch('models.PlayerStats') as mock_player_stats, \
         patch('models.ExerciseManager') as mock_exercise_manager:
        
        # Beginner stats
        mock_stats = mock_player_stats.return_value
        mock_stats.get_player_stats.return_value = {
            'level': 1,
            'strength': 10, 'endurance': 10, 'agility': 10, 'vitality': 10
        }
        
        mock_em = mock_exercise_manager.return_value
        mock_em.get_user_exercises.return_value = []

        difficulty = quest_generator.calculate_difficulty_level(1)
        # base_difficulty=1, stat_modifier=0 (40-40=0), max_modifier=0
        assert difficulty == 1

def test_calculate_difficulty_level_advanced(quest_generator, mock_db):
    with patch('models.PlayerStats') as mock_player_stats, \
         patch('models.ExerciseManager') as mock_exercise_manager:
        
        mock_stats = mock_player_stats.return_value
        mock_stats.get_player_stats.return_value = {
            'level': 20,
            'strength': 50, 'endurance': 40, 'agility': 30, 'vitality': 20
        } # total = 140. 140 - 40 = 100 // 25 = 4
        
        mock_em = mock_exercise_manager.return_value
        mock_em.get_user_exercises.return_value = [
            {'exercise_name': 'push_ups', 'personal_record': 40}, # +3
            {'exercise_name': 'pull_ups', 'max_reps': 20} # +3
        ]

        difficulty = quest_generator.calculate_difficulty_level(1)
        # 20 (base) + 4 (stats) + 6 (PRs) = 30
        assert difficulty == 30

def test_get_exercise_count(quest_generator):
    # difficulty 1, endurance 10 => bonus_diff=0, bonus_end=0. min(3, 8) = 3
    assert quest_generator.get_exercise_count(1, 10) == 3
    
    # difficulty 50, endurance 40 => bonus_diff=5, bonus_end=2. 3+5+2 = 10. min(10, 8) = 8
    assert quest_generator.get_exercise_count(50, 40) == 8
    
    # difficulty 100, endurance 100 => cap at 8
    assert quest_generator.get_exercise_count(100, 100) == 8

def test_get_beginner_target(quest_generator):
    # push_ups base = 10
    # difficulty 0 -> 10 * (1) = 10
    assert quest_generator.get_beginner_target('push_ups', 0) == 10
    
    # difficulty 10 -> 10 * (1 + 1) = 20
    assert quest_generator.get_beginner_target('push_ups', 10) == 20
    
    # difficulty 50 -> 10 * (1 + 5) = 60
    assert quest_generator.get_beginner_target('push_ups', 50) == 60

def test_calculate_rest_time(quest_generator):
    # For cardio, rest = 45 + (5 - diff//10) * 15
    # For diff 0: 45 + 5*15 = 120
    assert quest_generator.calculate_rest_time(0, 'cardio') == 120
    # For diff 50: 45 + 0*15 = 45
    assert quest_generator.calculate_rest_time(50, 'cardio') == 45
    
    # For strength, rest = 60 + (5 - diff//10) * 20
    # For diff 0: 60 + 5*20 = 160
    assert quest_generator.calculate_rest_time(0, 'strength') == 160
    # For diff 50: 60 + 0*20 = 60
    assert quest_generator.calculate_rest_time(50, 'strength') == 60

@patch('quest_generator.random')
def test_generate_exercise_task_beginner(mock_random, quest_generator, mock_db):
    # Control randomness for deterministic test
    mock_random.choice.side_effect = lambda x: list(x)[0]
    mock_random.uniform.return_value = 1.10
    
    with patch('models.ExerciseManager') as mock_exercise_manager, \
         patch('models.PlayerStats') as mock_player_stats:
        
        mock_stats = mock_player_stats.return_value
        mock_stats.get_player_stats.return_value = {'equipment': 'none'}
        
        mock_em = mock_exercise_manager.return_value
        mock_em.get_exercise_by_name.return_value = None # No PR history
        
        task = quest_generator.generate_exercise_task(
            user_id=1, 
            focus_areas=['strength'], 
            difficulty=5, 
            existing_exercises=[], 
            exercise_index=0
        )
        
        # Difficulty 5 -> Sets = max(2, min(5//5 + 2, 5)) = 3 sets
        assert task['sets'] == 3
        # Should be a strength upper_body exercise (due to mock_random returning first item)
        assert task['category'] == 'strength'
        # Target for push_ups at difficulty 5 -> base 10 * (1 + 0.5) = 15
        assert isinstance(task['target_reps'], int)

def test_generate_quest_title(quest_generator):
    title = quest_generator.generate_quest_title(10, ['strength'])
    # Should include 'Rank' and 'D' (rank for diff 10 is C? diff < 20 -> C)
    assert 'Rank]' in title
    assert 'C Rank' in title or 'D Rank' in title # diff=10 -> C Rank

