// Solo Leveling Fitness - Main Application JavaScript

// Global state
let currentUser = null;
let currentStats = null;
let currentQuest = null;

// API Base URL
const API_BASE = '';

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    checkAuth();
});

// ============================================================================
// AUTHENTICATION FUNCTIONS
// ============================================================================

function showLogin() {
    document.getElementById('login-form').style.display = 'block';
    document.getElementById('register-form').style.display = 'none';
}

function showRegister() {
    document.getElementById('login-form').style.display = 'none';
    document.getElementById('register-form').style.display = 'block';
}

async function register() {
    const username = document.getElementById('register-username').value;
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;
    
    if (!username || !email || !password) {
        showError('register-error', 'All fields are required');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, password }),
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast('Registration successful! Please login.');
            showLogin();
        } else {
            showError('register-error', data.error);
        }
    } catch (error) {
        showError('register-error', 'Registration failed. Please try again.');
    }
}

async function login() {
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    
    if (!username || !password) {
        showError('login-error', 'All fields are required');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentUser = data.user;
            
            if (data.user.has_stats) {
                await loadDashboard();
                showScreen('dashboard-screen');
            } else {
                showScreen('setup-screen');
            }
        } else {
            showError('login-error', data.error);
        }
    } catch (error) {
        showError('login-error', 'Login failed. Please try again.');
    }
}

async function logout() {
    try {
        await fetch(`${API_BASE}/api/logout`, {
            method: 'POST',
            credentials: 'include'
        });
        
        currentUser = null;
        currentStats = null;
        showScreen('auth-screen');
        showToast('Logged out successfully');
    } catch (error) {
        console.error('Logout failed:', error);
    }
}

async function checkAuth() {
    try {
        const response = await fetch(`${API_BASE}/api/check-auth`, {
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (data.authenticated) {
            currentUser = data.user;
            
            if (data.user.has_stats) {
                await loadDashboard();
                showScreen('dashboard-screen');
            } else {
                showScreen('setup-screen');
            }
        } else {
            showScreen('auth-screen');
        }
    } catch (error) {
        showScreen('auth-screen');
    }
}

// ============================================================================
// PROFILE SETUP
// ============================================================================

function addExerciseInput() {
    const container = document.getElementById('exercise-inputs');
    const newRow = document.createElement('div');
    newRow.className = 'exercise-input-row';
    newRow.innerHTML = `
        <select class="exercise-select">
            <option value="push_ups">Push-ups</option>
            <option value="pull_ups">Pull-ups</option>
            <option value="squats">Squats</option>
            <option value="sit_ups">Sit-ups</option>
            <option value="plank">Plank (seconds)</option>
            <option value="running">Running (minutes)</option>
        </select>
        <input type="number" class="exercise-reps" placeholder="Max reps or time">
        <button class="btn-small" onclick="this.parentElement.remove()">-</button>
    `;
    container.appendChild(newRow);
}

async function setupProfile() {
    const age = parseInt(document.getElementById('setup-age').value);
    const height_cm = parseFloat(document.getElementById('setup-height').value);
    const weight_kg = parseFloat(document.getElementById('setup-weight').value);
    const target_height = parseFloat(document.getElementById('setup-target-height').value) || height_cm;
    const target_weight = parseFloat(document.getElementById('setup-target-weight').value) || weight_kg;
    const experience_level = document.getElementById('setup-experience').value;
    const days_per_week = parseInt(document.getElementById('setup-days-per-week').value);
    
    if (!age || !height_cm || !weight_kg) {
        showError('setup-error', 'Please fill in all required fields');
        return;
    }
    
    // Gather multi-select Primary Objective Path
    const checkedObjectives = document.querySelectorAll('input[name="objective-path"]:checked');
    const primary_focus_areas = Array.from(checkedObjectives).map(cb => cb.value);
    
    if (primary_focus_areas.length === 0) {
        showError('objective-path-error', 'Select at least one objective — you can pick more than one!');
        return;
    }
    document.getElementById('objective-path-error').textContent = '';
    
    // Gather exercise data
    const exerciseRows = document.querySelectorAll('.exercise-input-row');
    const initial_exercises = [];
    
    exerciseRows.forEach(row => {
        const name = row.querySelector('.exercise-select').value;
        const value = parseInt(row.querySelector('.exercise-reps').value);
        
        if (value) {
            let cat = 'strength';
            if (name.includes('running') || name.includes('sprints') || name.includes('jog')) {
                cat = 'cardio';
            } else if (name.includes('plank') || name.includes('stretching') || name.includes('yoga')) {
                cat = 'flexibility';
            }
            initial_exercises.push({
                name: name,
                category: cat,
                max_reps: cat !== 'strength' ? 0 : value,
                max_duration: cat !== 'strength' ? value : 0
            });
        }
    });
    
    try {
        const response = await fetch(`${API_BASE}/api/setup-profile`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                age, height_cm, weight_kg, target_height, target_weight,
                primary_focus_areas, experience_level, days_per_week,
                initial_exercises
            }),
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(data.message);
            await loadDashboard();
            showScreen('dashboard-screen');
        } else {
            showError('setup-error', data.error);
        }
    } catch (error) {
        showError('setup-error', 'Setup failed. Please try again.');
    }
}

// ============================================================================
// DASHBOARD FUNCTIONS
// ============================================================================

async function loadDashboard() {
    try {
        // Load stats
        const statsResponse = await fetch(`${API_BASE}/api/stats`, {
            credentials: 'include'
        });
        const statsData = await statsResponse.json();
        currentStats = statsData.stats;
        
        // Update UI
        updatePlayerCard(currentStats);
        updateQuickStats();
        
        // Load today's quest preview
        await loadTodaysQuest();
        
        // Set username
        document.getElementById('nav-username').textContent = currentUser.username;
        document.getElementById('player-name').textContent = currentUser.username;
    } catch (error) {
        console.error('Failed to load dashboard:', error);
    }
}

function updatePlayerCard(stats) {
    document.getElementById('player-level').textContent = stats.level;
    document.getElementById('stat-strength').textContent = stats.strength;
    document.getElementById('stat-endurance').textContent = stats.endurance;
    document.getElementById('stat-agility').textContent = stats.agility;
    document.getElementById('stat-vitality').textContent = stats.vitality;
    
    // Update EXP bar
    const expPercent = (stats.exp / stats.exp_to_next_level) * 100;
    document.getElementById('exp-fill').style.width = `${expPercent}%`;
    document.getElementById('exp-text').textContent = 
        `${stats.exp} / ${stats.exp_to_next_level}`;
    
    // Update rank
    const rank = getRankFromLevel(stats.level);
    document.getElementById('player-rank').textContent = rank;
    
    // Show stat points if available
    if (stats.stat_points > 0) {
        document.getElementById('stat-points-section').style.display = 'block';
        document.getElementById('available-points').textContent = stats.stat_points;
    } else {
        document.getElementById('stat-points-section').style.display = 'none';
    }
}

function getRankFromLevel(level) {
    if (level < 5) return 'E-Rank Hunter';
    if (level < 10) return 'D-Rank Hunter';
    if (level < 20) return 'C-Rank Hunter';
    if (level < 35) return 'B-Rank Hunter';
    if (level < 50) return 'A-Rank Hunter';
    if (level < 70) return 'S-Rank Hunter';
    return 'SS-Rank Hunter';
}

async function allocateStatPoint(stat) {
    const allocation = {
        strength: stat === 'strength' ? 1 : 0,
        endurance: stat === 'endurance' ? 1 : 0,
        agility: stat === 'agility' ? 1 : 0,
        vitality: stat === 'vitality' ? 1 : 0
    };
    
    try {
        const response = await fetch(`${API_BASE}/api/stats/allocate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(allocation),
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentStats = data.stats;
            updatePlayerCard(currentStats);
            showToast('Stat point allocated!');
        }
    } catch (error) {
        console.error('Failed to allocate stat:', error);
    }
}

async function updateQuickStats() {
    try {
        const historyResponse = await fetch(`${API_BASE}/api/quest/history?days=7`, {
            credentials: 'include'
        });
        const historyData = await historyResponse.json();
        
        const completedQuests = historyData.quests.filter(q => q.completed);
        document.getElementById('daily-streak').textContent = 
            `${calculateStreak(completedQuests)} days`;
        document.getElementById('total-quests').textContent = completedQuests.length;
        
        // Height and weight progress
        if (currentStats) {
            const heightDiff = currentStats.height_cm - currentStats.initial_height;
            const weightDiff = currentStats.weight_kg - currentStats.initial_weight;
            
            document.getElementById('height-progress').textContent = 
                `${heightDiff >= 0 ? '+' : ''}${heightDiff.toFixed(1)} cm`;
            document.getElementById('weight-progress').textContent = 
                `${weightDiff >= 0 ? '+' : ''}${weightDiff.toFixed(1)} kg`;
        }
    } catch (error) {
        console.error('Failed to update quick stats:', error);
    }
}

function calculateStreak(quests) {
    if (quests.length === 0) return 0;
    
    quests.sort((a, b) => new Date(b.date) - new Date(a.date));
    let streak = 0;
    let currentDate = new Date();
    currentDate.setHours(0, 0, 0, 0);
    
    for (const quest of quests) {
        const questDate = new Date(quest.date);
        questDate.setHours(0, 0, 0, 0);
        
        const daysDiff = Math.floor((currentDate - questDate) / (1000 * 60 * 60 * 24));
        
        if (daysDiff === streak) {
            streak++;
        } else {
            break;
        }
    }
    
    return streak;
}

// ============================================================================
// QUEST FUNCTIONS
// ============================================================================

async function loadTodaysQuest() {
    try {
        const response = await fetch(`${API_BASE}/api/quest/today`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        if (!response.ok || !data.quest) {
            if (data.needs_setup) {
                showScreen('setup-screen');
                return;
            }
            throw new Error(data.error || 'Failed to load quest');
        }
        
        currentQuest = data.quest;
        
        // Update quest preview
        const preview = document.getElementById('quest-preview');
        preview.innerHTML = `
            <h3>${currentQuest.title}</h3>
            <p>${(currentQuest.exercises || []).length} exercises • ${currentQuest.exp_reward || 0} EXP</p>
            ${currentQuest.completed ? '<p class="quest-completed">✅ Completed!</p>' : ''}
        `;
        
        // Update full quest view
        displayFullQuest(currentQuest);
        await loadWeeklySchedule();
    } catch (error) {
        console.error('Failed to load quest:', error);
        document.getElementById('quest-preview').innerHTML = 
            '<p class="error-message">Failed to load quest</p>';
    }
}

function getQuestRankLetter(difficulty) {
    if (difficulty < 5) return 'E';
    if (difficulty < 10) return 'D';
    if (difficulty < 20) return 'C';
    if (difficulty < 35) return 'B';
    if (difficulty < 50) return 'A';
    if (difficulty < 70) return 'S';
    return 'SS';
}

function displayFullQuest(quest) {
    if (!quest) return;
    
    document.getElementById('quest-title').textContent = quest.title || 'Daily Quest';
    const rankLetter = getQuestRankLetter(quest.difficulty || 1);
    document.getElementById('quest-difficulty').textContent = `Rank: ${rankLetter}`;
    document.getElementById('quest-reward').textContent = 
        `Reward: ${quest.exp_reward || 0} EXP`;
    
    const content = document.getElementById('quest-content');
    content.innerHTML = '';
    
    if (quest.is_rest_day) {
        content.innerHTML = `
            <div class="card">
                <h3>🛌 Rest Day Activities</h3>
                <p>${quest.notes || 'Rest and recover today, Hunter!'}</p>
            </div>
        `;
        (quest.exercises || []).forEach((exercise, index) => {
            content.innerHTML += createRestExerciseCard(exercise, index);
        });
    } else {
        (quest.exercises || []).forEach((exercise, index) => {
            content.innerHTML += createExerciseCard(exercise, index);
        });
        
        if (quest.bonus_task) {
            content.innerHTML += `
                <div class="card">
                    <h3>💎 Bonus Challenge</h3>
                    <p><strong>${quest.bonus_task.name}</strong></p>
                    <p>${quest.bonus_task.description}</p>
                    <p>Bonus: +${quest.bonus_task.exp_bonus} EXP</p>
                </div>
            `;
        }
    }
    
    // Disable complete button if already completed
    const completeBtn = document.getElementById('complete-quest-btn');
    if (completeBtn) {
        if (quest.completed) {
            completeBtn.disabled = true;
            completeBtn.textContent = '✅ Quest Completed';
        } else {
            completeBtn.disabled = false;
            completeBtn.textContent = '✅ Complete Quest';
        }
    }
}

function createExerciseCard(exercise, index) {
    return `
        <div class="exercise-card" data-exercise-index="${index}">
            <div class="exercise-header">
                <div class="exercise-name">${exercise.name}</div>
                <div class="exercise-category">${exercise.category}</div>
            </div>
            <div class="exercise-details">
                <div class="exercise-detail">
                    <div class="exercise-detail-label">Sets</div>
                    <div class="exercise-detail-value">${exercise.sets}</div>
                </div>
                <div class="exercise-detail">
                    <div class="exercise-detail-label">Target</div>
                    <div class="exercise-detail-value">
                        ${exercise.target_reps ? exercise.target_reps + ' reps' : 
                          exercise.target_duration_minutes + ' min'}
                    </div>
                </div>
                <div class="exercise-detail">
                    <div class="exercise-detail-label">Rest</div>
                    <div class="exercise-detail-value">${exercise.rest_between_sets}s</div>
                </div>
            </div>
            <p class="info-text">${exercise.description}</p>
            <div class="exercise-progress">
                <label>
                    <input type="checkbox" class="exercise-complete-check" data-index="${index}">
                    Mark as completed
                </label>
            </div>
        </div>
    `;
}

function createRestExerciseCard(exercise, index) {
    return `
        <div class="exercise-card">
            <div class="exercise-header">
                <div class="exercise-name">${exercise.name}</div>
            </div>
            <p>${exercise.description}</p>
            <p><strong>Duration:</strong> ${exercise.duration_minutes} minutes</p>
        </div>
    `;
}

async function completeQuest() {
    const checkboxes = document.querySelectorAll('.exercise-complete-check');
    const allCompleted = Array.from(checkboxes).every(cb => cb.checked);
    
    if (!allCompleted) {
        showToast('Please complete all exercises first!');
        return;
    }
    
    // Gather completion data
    const completions = currentQuest.exercises.map((exercise, index) => ({
        exercise_name: exercise.name,
        category: exercise.category,
        sets: exercise.sets,
        reps: exercise.target_reps || 0,
        duration: exercise.target_duration_minutes ? exercise.target_duration_minutes * 60 : 0
    }));
    
    try {
        const response = await fetch(`${API_BASE}/api/quest/complete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                quest_id: currentQuest.id,
                completions: completions
            }),
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showQuestCompletionModal(data);
            await loadDashboard();
        }
    } catch (error) {
        console.error('Failed to complete quest:', error);
        showToast('Failed to complete quest. Please try again.');
    }
}

function showQuestCompletionModal(result) {
    const modal = document.getElementById('quest-completion-modal');
    const rewards = document.getElementById('completion-rewards');
    
    let rewardHTML = `
        <div style="font-size: 3rem; margin: 20px 0;">🎉</div>
        <p style="font-size: 1.2rem; margin-bottom: 20px;">
            You gained <strong>${result.exp_gained} EXP</strong>!
        </p>
    `;
    
    if (result.level_result.leveled_up) {
        rewardHTML += `
            <div style="background: var(--success-gradient); padding: 20px; border-radius: 12px; margin: 20px 0;">
                <h3 style="font-size: 2rem;">⬆️ LEVEL UP!</h3>
                <p style="font-size: 1.5rem;">Level ${result.level_result.new_level}</p>
                <p>You gained ${result.level_result.levels_gained} level(s) and 
                   ${result.level_result.stat_points} stat points!</p>
            </div>
        `;
    }
    
    rewards.innerHTML = rewardHTML;
    modal.classList.add('active');
}

async function generateNewQuest() {
    if (!confirm('This will replace your current quest for today with a new one. Continue?')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/quest/regenerate`, {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();
        
        if (response.ok && data.quest) {
            currentQuest = data.quest;
            displayFullQuest(currentQuest);
            showToast('New quest generated!');
            await loadDashboard();
        } else {
            showToast(data.error || 'Failed to generate new quest');
        }
    } catch (error) {
        console.error('Failed to regenerate quest:', error);
        showToast('Error regenerating quest.');
    }
}

// ============================================================================
// GOALS FUNCTIONS
// ============================================================================

async function loadGoals() {
    try {
        const response = await fetch(`${API_BASE}/api/goals`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        const goalsList = document.getElementById('goals-list');
        
        if (data.goals.length === 0) {
            goalsList.innerHTML = '<p class="no-data">No goals yet. Create one to get started!</p>';
            return;
        }
        
        goalsList.innerHTML = data.goals.map(goal => `
            <div class="card" style="margin-bottom: 15px;">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px;">
                    <div>
                        <h3>${goal.goal_name}</h3>
                        <p><strong>Type:</strong> ${goal.goal_type}</p>
                        <p><strong>Progress:</strong> ${goal.current_value} / ${goal.target_value}</p>
                        <p><strong>Status:</strong> <span class="status-badge ${goal.status === 'completed' ? 'status-active' : ''}">${goal.status}</span></p>
                        ${goal.deadline ? `<p><strong>Deadline:</strong> ${goal.deadline}</p>` : ''}
                    </div>
                    ${goal.status === 'active' ? `
                    <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                        <button class="btn btn-small btn-secondary" onclick="updateGoalProgress(${goal.id}, ${goal.current_value})">Update Progress</button>
                        <button class="btn btn-small btn-success" onclick="completeGoal(${goal.id})">Mark Complete</button>
                    </div>
                    ` : ''}
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to load goals:', error);
    }
}

async function updateGoalProgress(goalId, currentValue) {
    const newVal = prompt('Enter updated progress value:', currentValue);
    if (newVal === null) return;
    const parsedVal = parseFloat(newVal);
    if (isNaN(parsedVal)) return;

    try {
        const response = await fetch(`${API_BASE}/api/goals/${goalId}/update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ current_value: parsedVal }),
            credentials: 'include'
        });
        const data = await response.json();
        if (response.ok) {
            showToast(data.message || 'Goal updated!');
            await loadGoals();
        }
    } catch (error) {
        console.error('Failed to update goal progress:', error);
    }
}

async function completeGoal(goalId) {
    try {
        const response = await fetch(`${API_BASE}/api/goals/${goalId}/update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: 'completed' }),
            credentials: 'include'
        });
        const data = await response.json();
        if (response.ok) {
            showToast('Goal marked as completed! 🎉');
            await loadGoals();
        }
    } catch (error) {
        console.error('Failed to complete goal:', error);
    }
}

function showAddGoalModal() {
    document.getElementById('add-goal-modal').classList.add('active');
}

async function addGoal() {
    const goalType = document.getElementById('goal-type').value;
    const goalName = document.getElementById('goal-name').value;
    const targetValue = parseFloat(document.getElementById('goal-target').value);
    const deadline = document.getElementById('goal-deadline').value;
    
    if (!goalName || !targetValue) {
        showToast('Please fill in all required fields');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/goals/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                goal_type: goalType,
                goal_name: goalName,
                target_value: targetValue,
                deadline: deadline || null
            }),
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(data.message);
            closeModal();
            await loadGoals();
        }
    } catch (error) {
        console.error('Failed to add goal:', error);
    }
}

// ============================================================================
// SOCIAL FUNCTIONS
// ============================================================================

async function loadLeaderboard() {
    const scope = document.getElementById('leaderboard-scope').value;
    
    try {
        const response = await fetch(`${API_BASE}/api/leaderboard?scope=${scope}`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        const leaderboard = document.getElementById('leaderboard');
        
        leaderboard.innerHTML = data.leaderboard.map((player, index) => `
            <div class="leaderboard-item ${player.id === currentUser.id ? 'highlight' : ''}">
                <div class="leaderboard-rank">${index + 1}</div>
                <div class="leaderboard-info">
                    <div class="leaderboard-name">${player.username}</div>
                    <div class="leaderboard-stats">
                        Level ${player.level} • ${player.exp} EXP
                    </div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to load leaderboard:', error);
    }
}

async function searchFriends() {
    const query = document.getElementById('friend-search').value;
    
    if (query.length < 2) {
        document.getElementById('friend-search-results').innerHTML = '';
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/friends/search?q=${query}`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        const results = document.getElementById('friend-search-results');
        results.innerHTML = data.users.map(user => `
            <div class="leaderboard-item">
                <div class="leaderboard-info">
                    <div class="leaderboard-name">${user.username}</div>
                    <div class="leaderboard-stats">Level ${user.level || 1}</div>
                </div>
                <button class="btn btn-small" onclick="addFriend(${user.id})">
                    Add Friend
                </button>
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to search friends:', error);
    }
}

async function addFriend(friendId) {
    try {
        const response = await fetch(`${API_BASE}/api/friends/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ friend_id: friendId }),
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(data.message);
            await loadFriends();
        } else {
            showToast(data.error || 'Failed to add friend');
        }
    } catch (error) {
        console.error('Failed to add friend:', error);
    }
}

async function loadFriends() {
    try {
        // Load accepted friends
        const response = await fetch(`${API_BASE}/api/friends`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        // Load pending requests
        const pendingResponse = await fetch(`${API_BASE}/api/friends/pending`, {
            credentials: 'include'
        });
        const pendingData = await pendingResponse.json();
        
        const friendsList = document.getElementById('friends-list');
        if (!friendsList) return;
        
        let html = '';
        
        if (pendingData.pending && pendingData.pending.length > 0) {
            html += `<h4 style="margin-top: 15px; color: var(--warning-color);">📩 Pending Requests</h4>`;
            html += pendingData.pending.map(p => `
                <div class="leaderboard-item" style="border-left: 4px solid var(--warning-color); margin-bottom: 8px;">
                    <div class="leaderboard-info">
                        <div class="leaderboard-name">${p.username}</div>
                        <div class="leaderboard-stats">Level ${p.level || 1}</div>
                    </div>
                    <button class="btn btn-small btn-success" onclick="acceptFriend(${p.id})">
                        Accept
                    </button>
                </div>
            `).join('');
        }
        
        html += `<h4 style="margin-top: 15px;">👥 Active Friends</h4>`;
        if (!data.friends || data.friends.length === 0) {
            html += '<p class="no-data">No friends added yet. Use the search bar above to find hunters!</p>';
        } else {
            html += data.friends.map(friend => `
                <div class="leaderboard-item" style="margin-bottom: 8px;">
                    <div class="leaderboard-info">
                        <div class="leaderboard-name">${friend.username}</div>
                        <div class="leaderboard-stats">Level ${friend.level || 1} • ${friend.exp || 0} EXP</div>
                    </div>
                    <span class="status-badge status-active">Accepted</span>
                </div>
            `).join('');
        }
        
        friendsList.innerHTML = html;
    } catch (error) {
        console.error('Failed to load friends:', error);
    }
}

// ============================================================================
// PHYSIQUE ANALYZER FUNCTIONS ("Become Like...")
// ============================================================================

let physiqueMode = 'name'; // 'name' or 'image'
let selectedPhysiqueImage = null;

function setPhysiqueMode(mode) {
    physiqueMode = mode;
    
    document.getElementById('mode-btn-name').classList.toggle('active', mode === 'name');
    document.getElementById('mode-btn-image').classList.toggle('active', mode === 'image');
    
    document.getElementById('physique-name-input').style.display = mode === 'name' ? 'block' : 'none';
    document.getElementById('physique-image-input').style.display = mode === 'image' ? 'block' : 'none';
}

document.addEventListener('change', (e) => {
    if (e.target.id === 'physique-image-file') {
        const file = e.target.files[0];
        selectedPhysiqueImage = file || null;
        
        const preview = document.getElementById('physique-image-preview');
        if (file) {
            const reader = new FileReader();
            reader.onload = (evt) => {
                preview.innerHTML = `<img src="${evt.target.result}" class="physique-preview-img" alt="Preview">`;
            };
            reader.readAsDataURL(file);
        } else {
            preview.innerHTML = '';
        }
    }
});

async function checkPhysiqueConfigured() {
    try {
        const response = await fetch(`${API_BASE}/api/physique/status`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        document.getElementById('physique-not-configured').style.display = 
            data.configured ? 'none' : 'block';
        document.getElementById('physique-shared-key-notice').style.display =
            (data.configured && !data.using_personal_key && data.shared_key_available) ? 'block' : 'none';
    } catch (error) {
        console.error('Failed to check physique analyzer status:', error);
    }
}

async function loadApiKeyStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/settings/api-key`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        const statusDiv = document.getElementById('api-key-status');
        const removeBtn = document.getElementById('remove-api-key-btn');
        
        if (data.has_personal_key) {
            statusDiv.innerHTML = '<span class="status-badge status-active">✅ Personal key active</span>';
            removeBtn.style.display = 'inline-block';
        } else if (data.shared_key_available) {
            statusDiv.innerHTML = '<span class="status-badge status-shared">Using site\'s shared key</span>';
            removeBtn.style.display = 'none';
        } else {
            statusDiv.innerHTML = '<span class="status-badge status-none">No key configured — add one below</span>';
            removeBtn.style.display = 'none';
        }
    } catch (error) {
        console.error('Failed to load API key status:', error);
    }
}

async function saveApiKey() {
    const input = document.getElementById('api-key-input');
    const errorEl = document.getElementById('api-key-error');
    const key = input.value.trim();
    
    errorEl.textContent = '';
    
    if (!key) {
        errorEl.textContent = 'Enter an API key first';
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/settings/api-key`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: key }),
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(data.message);
            input.value = '';
            await loadApiKeyStatus();
            await checkPhysiqueConfigured();
        } else {
            errorEl.textContent = data.error || 'Failed to save key';
        }
    } catch (error) {
        errorEl.textContent = 'Failed to save key. Please try again.';
        console.error('Save API key error:', error);
    }
}

async function removeApiKey() {
    if (!confirm('Remove your personal API key? You\'ll fall back to the site\'s shared key if one is available.')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/settings/api-key`, {
            method: 'DELETE',
            credentials: 'include'
        });
        const data = await response.json();
        
        if (response.ok) {
            showToast(data.message);
            await loadApiKeyStatus();
            await checkPhysiqueConfigured();
        }
    } catch (error) {
        console.error('Failed to remove API key:', error);
    }
}

async function analyzePhysique() {
    const errorEl = document.getElementById('physique-error');
    errorEl.textContent = '';
    
    const formData = new FormData();
    
    if (physiqueMode === 'name') {
        const targetName = document.getElementById('physique-target-name').value.trim();
        if (!targetName) {
            errorEl.textContent = 'Enter a character or person\'s name';
            return;
        }
        formData.append('target_name', targetName);
    } else {
        if (!selectedPhysiqueImage) {
            errorEl.textContent = 'Please select a photo to upload';
            return;
        }
        formData.append('image', selectedPhysiqueImage);
    }
    
    document.getElementById('physique-loading').style.display = 'block';
    document.getElementById('physique-result-card').style.display = 'none';
    document.getElementById('analyze-btn').disabled = true;
    
    try {
        const response = await fetch(`${API_BASE}/api/physique/analyze`, {
            method: 'POST',
            body: formData,
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            displayPhysiqueResult(data);
            await loadPhysiqueHistory();
            await loadTodaysQuest();
            await loadWeeklySchedule();
            showToast('Quest Log generated! Your 7-day build schedule is now active.');
        } else {
            errorEl.textContent = data.error || 'Analysis failed. Please try again.';
            if (data.setup_required) {
                document.getElementById('physique-not-configured').style.display = 'block';
            }
        }
    } catch (error) {
        errorEl.textContent = 'Analysis failed. Please check your connection and try again.';
        console.error('Physique analysis error:', error);
    } finally {
        document.getElementById('physique-loading').style.display = 'none';
        document.getElementById('analyze-btn').disabled = false;
    }
}

function displayPhysiqueResult(data) {
    const resultCard = document.getElementById('physique-result-card');
    const titleEl = document.getElementById('physique-result-title');
    const contentEl = document.getElementById('physique-result-content');
    
    titleEl.textContent = `🎯 Quest Log: Becoming ${data.target_name}`;
    contentEl.innerHTML = typeof marked !== 'undefined' 
        ? marked.parse(data.quest_log_markdown)
        : `<pre>${data.quest_log_markdown}</pre>`;
    
    resultCard.style.display = 'block';
    resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

async function loadPhysiqueHistory() {
    try {
        const response = await fetch(`${API_BASE}/api/physique/history`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        const historyDiv = document.getElementById('physique-history');
        
        if (data.history.length === 0) {
            historyDiv.innerHTML = '<p class="no-data">No build goals analyzed yet. Try one above!</p>';
            return;
        }
        
        historyDiv.innerHTML = data.history.map(item => `
            <div class="physique-history-item ${item.is_active ? 'active-build' : ''}">
                <div class="physique-history-info">
                    <div class="physique-history-name">
                        ${item.is_active ? '⭐ ' : ''}${item.target_name}
                        <span class="physique-history-source">(${item.source_type === 'image' ? '📷 photo' : '📝 named'})</span>
                    </div>
                    <div class="physique-history-date">${new Date(item.created_at).toLocaleDateString()}</div>
                </div>
                <div class="physique-history-actions">
                    <button class="btn btn-small" onclick="viewPhysiqueHistoryItem(${item.id})">View</button>
                    ${!item.is_active ? `<button class="btn btn-small" onclick="activatePhysiqueGoal(${item.id})">Set Active</button>` : ''}
                    <button class="btn btn-small btn-danger" onclick="deletePhysiqueHistoryItem(${item.id})">Delete</button>
                </div>
            </div>
        `).join('');
        
        // Store for viewing
        window._physiqueHistoryCache = data.history;
    } catch (error) {
        console.error('Failed to load physique history:', error);
    }
}

function viewPhysiqueHistoryItem(id) {
    const item = (window._physiqueHistoryCache || []).find(h => h.id === id);
    if (item) {
        displayPhysiqueResult({
            target_name: item.target_name,
            quest_log_markdown: item.quest_log_markdown
        });
    }
}

async function activatePhysiqueGoal(id) {
    try {
        const response = await fetch(`${API_BASE}/api/physique/${id}/activate`, {
            method: 'POST',
            credentials: 'include'
        });
        const data = await response.json();
        
        if (response.ok) {
            showToast(data.message);
            await loadPhysiqueHistory();
            await loadTodaysQuest();
            await loadWeeklySchedule();
        }
    } catch (error) {
        console.error('Failed to activate build goal:', error);
    }
}

async function deletePhysiqueHistoryItem(id) {
    if (!confirm('Delete this Quest Log permanently?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/physique/${id}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        const data = await response.json();
        
        if (response.ok) {
            showToast(data.message);
            await loadPhysiqueHistory();
        }
    } catch (error) {
        console.error('Failed to delete quest log:', error);
    }
}

// ============================================================================
// UI HELPER FUNCTIONS
// ============================================================================

function showScreen(screenId) {
    document.querySelectorAll('.screen').forEach(screen => {
        screen.classList.remove('active');
    });
    document.getElementById(screenId).classList.add('active');
}

function showTab(tabName) {
    // Update nav links
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    document.getElementById(`tab-${tabName}`).classList.add('active');
    
    // Load data for specific tabs
    if (tabName === 'quest') {
        loadTodaysQuest();
        loadWeeklySchedule();
    } else if (tabName === 'stats') {
        loadProgressData();
    } else if (tabName === 'goals') {
        loadGoals();
    } else if (tabName === 'physique') {
        checkPhysiqueConfigured();
        loadPhysiqueHistory();
        loadApiKeyStatus();
    } else if (tabName === 'social') {
        loadLeaderboard();
        loadFriends();
    }
}

async function loadWeeklySchedule() {
    const grid = document.getElementById('weekly-schedule-grid');
    if (!grid) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/quest/weekly-schedule`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        if (!data.schedule || data.schedule.length === 0) {
            grid.innerHTML = '<p class="no-data">No weekly schedule generated yet.</p>';
            return;
        }
        
        grid.innerHTML = data.schedule.map(item => {
            const isToday = item.is_today;
            const isRest = item.is_rest;
            const exercises = item.quest ? (item.quest.exercises || []) : [];
            
            let exerciseListHtml = '';
            if (isRest) {
                exerciseListHtml = `<p>🛌 <em>Active Recovery & Rest</em></p>`;
            } else if (exercises.length > 0) {
                exerciseListHtml = `
                    <ul>
                        ${exercises.slice(0, 4).map(ex => `
                            <li>• <strong>${ex.name}</strong> ${ex.sets ? '(' + ex.sets + ' sets)' : ''}</li>
                        `).join('')}
                        ${exercises.length > 4 ? `<li><em>+ ${exercises.length - 4} more exercise(s)</em></li>` : ''}
                    </ul>
                `;
            } else {
                exerciseListHtml = `<p>No exercises listed</p>`;
            }
            
            return `
                <div class="weekly-day-card ${isToday ? 'today-highlight' : ''} ${isRest ? 'rest-day-card' : ''}">
                    <div>
                        <div class="weekly-day-header">
                            <span class="weekly-day-title">${item.day_label}</span>
                            <span class="weekly-day-badge ${isToday ? 'today-badge' : ''}">
                                ${isToday ? 'TODAY' : (isRest ? 'REST' : 'WORKOUT')}
                            </span>
                        </div>
                        <div class="weekly-day-focus">${item.focus}</div>
                        <div class="weekly-day-exercises">${exerciseListHtml}</div>
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Failed to load weekly schedule:', error);
        if (grid) grid.innerHTML = '<p class="error-message">Failed to load weekly schedule</p>';
    }
}

let progressChartInstance = null;

async function updateCharts() {
    const timeframeSelect = document.getElementById('chart-timeframe');
    const days = timeframeSelect ? timeframeSelect.value : 30;
    
    try {
        const response = await fetch(`${API_BASE}/api/stats/progress?days=${days}`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        const canvas = document.getElementById('progress-chart');
        if (!canvas) return;
        
        const labels = (data.exp_progress || []).map(item => item.date);
        const expValues = (data.exp_progress || []).map(item => item.exp);
        
        if (progressChartInstance) {
            progressChartInstance.destroy();
        }
        
        if (typeof Chart !== 'undefined') {
            const ctx = canvas.getContext('2d');
            progressChartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels.length > 0 ? labels : ['No Data'],
                    datasets: [{
                        label: 'Daily EXP Gained',
                        data: expValues.length > 0 ? expValues : [0],
                        borderColor: '#6366f1',
                        backgroundColor: 'rgba(99, 102, 241, 0.2)',
                        fill: true,
                        tension: 0.3
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { labels: { color: '#f1f5f9' } }
                    },
                    scales: {
                        x: { ticks: { color: '#94a3b8' }, grid: { color: '#334155' } },
                        y: { ticks: { color: '#94a3b8' }, grid: { color: '#334155' } }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Failed to update charts:', error);
    }
}

async function loadQuestHistory() {
    try {
        const response = await fetch(`${API_BASE}/api/quest/history?days=30`, {
            credentials: 'include'
        });
        const data = await response.json();
        const historyDiv = document.getElementById('quest-history');
        if (!historyDiv) return;
        
        if (!data.quests || data.quests.length === 0) {
            historyDiv.innerHTML = '<p class="no-data">No completed quest history yet</p>';
            return;
        }
        
        historyDiv.innerHTML = data.quests.map(quest => `
            <div class="card" style="margin-bottom: 10px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h4>${quest.title}</h4>
                        <p style="font-size: 0.9rem; color: var(--text-secondary);">Date: ${quest.date} • EXP: ${quest.exp_reward}</p>
                    </div>
                    <span class="status-badge ${quest.completed ? 'status-active' : 'status-none'}">
                        ${quest.completed ? 'Completed' : 'Pending'}
                    </span>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to load quest history:', error);
    }
}

async function loadProgressData() {
    try {
        await updateCharts();
        await loadQuestHistory();
        
        // Load exercise records
        const exercisesResponse = await fetch(`${API_BASE}/api/exercises`, {
            credentials: 'include'
        });
        const exercisesData = await exercisesResponse.json();
        
        const recordsDiv = document.getElementById('exercise-records');
        if (exercisesData.exercises.length === 0) {
            recordsDiv.innerHTML = '<p class="no-data">No exercise records yet</p>';
        } else {
            recordsDiv.innerHTML = exercisesData.exercises.map(ex => `
                <div class="card" style="margin-bottom: 10px;">
                    <h4>${ex.exercise_name}</h4>
                    <p>Personal Record: ${ex.personal_record} ${ex.max_reps ? 'reps' : 'seconds'}</p>
                    <p>Last performed: ${new Date(ex.last_performed).toLocaleDateString()}</p>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Failed to load progress data:', error);
    }
}

function showError(elementId, message) {
    const element = document.getElementById(elementId);
    element.textContent = message;
    setTimeout(() => {
        element.textContent = '';
    }, 5000);
}

function showToast(message) {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

function closeModal() {
    document.querySelectorAll('.modal').forEach(modal => {
        modal.classList.remove('active');
    });
}

// Close modals when clicking outside
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal')) {
        closeModal();
    }
});
