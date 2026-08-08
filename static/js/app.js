// Body Sync Fitness - Main Application JavaScript

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

function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const isPassword = input.type === 'password';
    input.type = isPassword ? 'text' : 'password';
    
    if (btn) {
        if (isPassword) {
            btn.innerHTML = `
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                    <line x1="1" y1="1" x2="23" y2="23"></line>
                </svg>
            `;
            btn.title = "Hide Password";
        } else {
            btn.innerHTML = `
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                    <circle cx="12" cy="12" r="3"></circle>
                </svg>
            `;
            btn.title = "Show Password";
        }
    }
}

function showLogin() {
    document.getElementById('login-form').style.display = 'block';
    document.getElementById('register-form').style.display = 'none';
}

function showRegister() {
    document.getElementById('login-form').style.display = 'none';
    document.getElementById('register-form').style.display = 'block';
}

async function register() {
    const usernameInput = document.getElementById('register-username');
    const emailInput = document.getElementById('register-email');
    const passwordInput = document.getElementById('register-password');
    const registerBtn = document.querySelector('#register-form button');
    
    const username = usernameInput ? usernameInput.value.trim() : '';
    const email = emailInput ? emailInput.value.trim() : '';
    const password = passwordInput ? passwordInput.value : '';
    
    if (!username || !email || !password) {
        showError('register-error', 'All fields are required');
        return;
    }
    
    // Prevent accidental double clicks / taps on mobile
    if (registerBtn) {
        registerBtn.disabled = true;
        registerBtn.innerText = 'Creating Account...';
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
            showToast('Registration successful! Welcome Hunter.');
            await checkAuth();
        } else {
            showError('register-error', data.error);
        }
    } catch (error) {
        showError('register-error', 'Registration failed. Please try again.');
    } finally {
        if (registerBtn) {
            registerBtn.disabled = false;
            registerBtn.innerText = 'Create Account';
        }
    }
}

async function quickLoginDemo() {
    const usernameInput = document.getElementById('login-username');
    const passwordInput = document.getElementById('login-password');
    if (usernameInput) usernameInput.value = 'me';
    if (passwordInput) passwordInput.value = '123456';
    await login();
}


async function login() {
    const usernameInput = document.getElementById('login-username');
    const passwordInput = document.getElementById('login-password');
    const loginBtn = document.getElementById('login-submit-btn') || document.querySelector('#login-form button[type="submit"]');
    
    const username = usernameInput ? usernameInput.value.trim() : '';
    const password = passwordInput ? passwordInput.value : '';
    
    if (!username || !password) {
        showError('login-error', 'Please enter your username/email and password.');
        return;
    }
    
    if (loginBtn) {
        loginBtn.disabled = true;
        loginBtn.innerText = 'Accessing System...';
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password }),
            credentials: 'include'
        });
        
        const data = await response.json().catch(() => ({}));
        
        if (response.ok) {
            currentUser = data.user;
            showToast(`Welcome back, ${data.user.username}!`);
            
            if (data.user.has_stats) {
                showScreen('dashboard-screen');
                loadDashboard();
            } else {
                showScreen('setup-screen');
            }
        } else {
            showError('login-error', data.error || 'Incorrect username or password');
        }
    } catch (error) {
        console.error('Login error:', error);
        showError('login-error', 'Connection failed. Please try again.');
    } finally {
        if (loginBtn) {
            loginBtn.disabled = false;
            loginBtn.innerText = 'Enter the System';
        }
    }
}

// Utility to safely escape text for HTML insertion
function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

async function logout() {
    try {
        await fetch(`${API_BASE}/api/logout`, {
            method: 'POST',
            credentials: 'include'
        });
        
        if (window._socialNotificationInterval) {
            clearInterval(window._socialNotificationInterval);
            window._socialNotificationInterval = null;
        }
        
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
            updateAdminNavVisibility();
            
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
        await loadWeeklyActivity();
        
        // Load today's quest preview
        await loadTodaysQuest();
        
        // Set username
        if (document.getElementById('nav-username')) document.getElementById('nav-username').textContent = currentUser.username;
        if (document.getElementById('nav-username-mobile')) document.getElementById('nav-username-mobile').textContent = currentUser.username;
        if (document.getElementById('player-name')) document.getElementById('player-name').textContent = currentUser.username;
        
        // Update admin panel navigation link visibility
        updateAdminNavVisibility();
        
        // Check for pending friend requests & notification badge
        checkPendingBadgeNotification();
        if (!window._socialNotificationInterval) {
            window._socialNotificationInterval = setInterval(checkPendingBadgeNotification, 15000);
        }
    } catch (error) {
        console.error('Failed to load dashboard:', error);
    }
}

async function checkPendingBadgeNotification() {
    if (!currentUser) return;
    try {
        const response = await fetch(`${API_BASE}/api/friends/pending`, {
            credentials: 'include'
        });
        if (!response.ok) return;
        const data = await response.json();
        const incoming = data.incoming || data.pending || [];
        updatePendingBadge(incoming.length);
    } catch (e) {
        // ignore background fetch error
    }
}

function updatePlayerCard(stats) {
    if (!stats) return;
    
    const rank = getRankFromLevel(stats.level);
    const expPercent = Math.min(100, Math.max(0, (stats.exp / stats.exp_to_next_level) * 100));
    
    // Dashboard elements
    const dashLevel = document.getElementById('player-level');
    if (dashLevel) dashLevel.textContent = stats.level;
    const dashStr = document.getElementById('stat-strength');
    if (dashStr) dashStr.textContent = stats.strength;
    const dashEnd = document.getElementById('stat-endurance');
    if (dashEnd) dashEnd.textContent = stats.endurance;
    const dashAgi = document.getElementById('stat-agility');
    if (dashAgi) dashAgi.textContent = stats.agility;
    const dashVit = document.getElementById('stat-vitality');
    if (dashVit) dashVit.textContent = stats.vitality;
    
    const dashExpFill = document.getElementById('exp-fill');
    if (dashExpFill) dashExpFill.style.width = `${expPercent}%`;
    const dashExpText = document.getElementById('exp-text');
    if (dashExpText) dashExpText.textContent = `${stats.exp} / ${stats.exp_to_next_level}`;
    
    const dashRank = document.getElementById('player-rank');
    if (dashRank) dashRank.textContent = rank;
    
    // Quest Tab Mini Profile Bar
    const questLevel = document.getElementById('quest-player-level');
    if (questLevel) questLevel.textContent = stats.level;
    const questName = document.getElementById('quest-player-name');
    if (questName && currentUser) questName.textContent = currentUser.username || 'Hunter';
    const questRank = document.getElementById('quest-player-rank');
    if (questRank) questRank.textContent = rank;
    const questExpFill = document.getElementById('quest-exp-fill');
    if (questExpFill) questExpFill.style.width = `${expPercent}%`;
    const questExpText = document.getElementById('quest-exp-text');
    if (questExpText) questExpText.textContent = `${stats.exp} / ${stats.exp_to_next_level}`;
    
    // Show stat points if available
    const statPointsSec = document.getElementById('stat-points-section');
    if (statPointsSec) {
        if (stats.stat_points > 0) {
            statPointsSec.style.display = 'block';
            document.getElementById('available-points').textContent = stats.stat_points;
        } else {
            statPointsSec.style.display = 'none';
        }
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
// ADMINISTRATOR & OVERLORD DASHBOARD FUNCTIONS
// ============================================================================

let adminUsersCache = [];

function updateAdminNavVisibility() {
    const isAdmin = currentUser && currentUser.is_admin;
    document.querySelectorAll('.admin-only-link').forEach(el => {
        el.style.display = isAdmin ? 'inline-flex' : 'none';
    });
}

function switchAdminSubTab(subTabName) {
    document.querySelectorAll('.admin-subnav-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.admin-subview').forEach(view => view.style.display = 'none');

    const activeBtn = document.getElementById(`admin-subtab-btn-${subTabName}`);
    const activeView = document.getElementById(`admin-subview-${subTabName}`);

    if (activeBtn) activeBtn.classList.add('active');
    if (activeView) activeView.style.display = 'block';

    if (subTabName === 'exercises') {
        loadAdminExercises();
    }
}

async function loadAdminTab() {
    if (!currentUser || !currentUser.is_admin) {
        showToast('Administrator access required');
        showTab('dashboard');
        return;
    }

    await Promise.all([
        loadAdminStats(),
        loadAdminUsers(),
        loadAdminActivityFeed()
    ]);
}

async function loadAdminStats() {
    try {
        const response = await fetch(`${API_BASE}/api/admin/stats`, { credentials: 'include' });
        const data = await response.json();
        if (response.ok && data.success) {
            const s = data.stats;
            const u = document.getElementById('admin-metric-users');
            if (u) u.textContent = s.total_users || 0;
            const a = document.getElementById('admin-metric-admins');
            if (a) a.textContent = `${s.total_admins || 0} Admin(s)`;
            const w = document.getElementById('admin-metric-workouts');
            if (w) w.textContent = s.total_workouts || 0;
            const q = document.getElementById('admin-metric-quests');
            if (q) q.textContent = s.total_quests_completed || 0;
            const st = document.getElementById('admin-metric-status');
            if (st) st.textContent = s.system_status || 'ONLINE';
        }
    } catch (e) {
        console.error('Failed to load admin stats:', e);
    }
}

async function loadAdminUsers() {
    const tbody = document.getElementById('admin-users-tbody');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="7" class="loading">Loading hunters database...</td></tr>';

    try {
        const searchInput = document.getElementById('admin-user-search');
        const query = searchInput ? searchInput.value.trim() : '';
        const url = query ? `${API_BASE}/api/admin/users?search=${encodeURIComponent(query)}` : `${API_BASE}/api/admin/users`;

        const response = await fetch(url, { credentials: 'include' });
        const data = await response.json();

        if (response.ok && data.success) {
            adminUsersCache = data.users || [];
            renderAdminUsers(adminUsersCache);
        } else {
            tbody.innerHTML = `<tr><td colspan="7" class="error-message">${data.error || 'Failed to load user list'}</td></tr>`;
        }
    } catch (e) {
        console.error('Failed to load admin users:', e);
        tbody.innerHTML = '<tr><td colspan="7" class="error-message">Connection error loading users</td></tr>';
    }
}

function renderAdminUsers(users) {
    const tbody = document.getElementById('admin-users-tbody');
    if (!tbody) return;

    if (users.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="no-data">No hunters found matching query</td></tr>';
        return;
    }

    tbody.innerHTML = users.map(u => {
        const isSelf = currentUser && currentUser.id === u.id;
        const isAdmin = Boolean(u.is_admin);
        const roleBadge = isAdmin
            ? '<span class="status-badge" style="background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.4); font-weight: 800; font-size: 0.72rem; padding: 3px 8px; border-radius: 6px;">👑 OVERLORD ADMIN</span>'
            : '<span class="status-badge" style="background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); font-weight: 700; font-size: 0.72rem; padding: 3px 8px; border-radius: 6px;">🏹 HUNTER</span>';

        const rankLetter = getRankLetterFromLevel(u.level || 1);
        const rankBadgeStyle = {
            'SS': 'background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%); color: #fff; box-shadow: 0 0 10px rgba(245, 158, 11, 0.4);',
            'S':  'background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%); color: #fff;',
            'A':  'background: linear-gradient(135deg, #a855f7 0%, #6366f1 100%); color: #fff;',
            'B':  'background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: #fff;',
            'C':  'background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); color: #fff;',
            'D':  'background: linear-gradient(135deg, #64748b 0%, #334155 100%); color: #fff;',
            'E':  'background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: #0f172a;'
        }[rankLetter] || 'background: #334155; color: #fff;';

        const statsPills = u.level
            ? `<div style="display: flex; gap: 4px; flex-wrap: wrap;">
                 <span style="font-size: 0.72rem; background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.3); padding: 2px 6px; border-radius: 6px; font-weight: 700;">STR ${u.strength || 10}</span>
                 <span style="font-size: 0.72rem; background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); padding: 2px 6px; border-radius: 6px; font-weight: 700;">END ${u.endurance || 10}</span>
                 <span style="font-size: 0.72rem; background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3); padding: 2px 6px; border-radius: 6px; font-weight: 700;">AGI ${u.agility || 10}</span>
                 <span style="font-size: 0.72rem; background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3); padding: 2px 6px; border-radius: 6px; font-weight: 700;">VIT ${u.vitality || 10}</span>
               </div>`
            : '<span style="color: #64748b; font-size: 0.78rem;">Uninitialized</span>';

        return `
            <tr>
                <td style="font-weight: 700; color: #94a3b8; font-family: 'Orbitron', sans-serif; font-size: 0.85rem;">#${u.id}</td>
                <td>
                    <div style="font-weight: 700; color: #f8fafc; font-size: 0.92rem; display: flex; align-items: center; gap: 8px;">
                        <span style="width: 28px; height: 28px; border-radius: 50%; background: rgba(99, 102, 241, 0.2); border: 1px solid rgba(99, 102, 241, 0.4); display: flex; align-items: center; justify-content: center; font-size: 0.75rem; font-weight: 800; color: #a5b4fc;">${(u.username || 'H')[0].toUpperCase()}</span>
                        ${escapeHtml(u.username)}
                        ${isSelf ? '<span style="font-size: 0.68rem; background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.4); padding: 1px 5px; border-radius: 4px; font-weight: 800;">YOU</span>' : ''}
                    </div>
                </td>
                <td style="color: #cbd5e1; font-size: 0.85rem;">${escapeHtml(u.email || '')}</td>
                <td>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="padding: 2px 8px; border-radius: 6px; font-family: 'Orbitron', sans-serif; font-size: 0.75rem; font-weight: 900; ${rankBadgeStyle}">${rankLetter}</span>
                        <div>
                            <div style="font-weight: 700; color: #f59e0b; font-size: 0.82rem; font-family: 'Orbitron', sans-serif;">${u.rank || 'E-Rank'}</div>
                            <div style="font-size: 0.72rem; color: #94a3b8;">Lvl ${u.level || 1} • ${u.exp || 0} EXP</div>
                        </div>
                    </div>
                </td>
                <td>${statsPills}</td>
                <td>${roleBadge}</td>
                <td style="text-align: right;">
                    <div style="display: flex; gap: 6px; justify-content: flex-end; flex-wrap: wrap;">
                        <button class="btn btn-small btn-secondary" onclick="openAdminEditModal(${u.id})" title="Edit user stats and permissions">✏️ Edit</button>
                        <button class="btn btn-small" onclick="activateGodMode(${u.id})" style="background: rgba(245, 158, 11, 0.18); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.4); font-weight: 700;" title="Grant Max Stats & Level 100">⚡ God Mode</button>
                        <button class="btn btn-small btn-secondary" onclick="openAdminResetPasswordModal(${u.id}, '${escapeHtml(u.username)}')" title="Reset Password">🔑 Password</button>
                        ${!isSelf ? `<button class="btn btn-small btn-danger" onclick="adminDeleteUser(${u.id}, '${escapeHtml(u.username)}')" title="Delete Account">🗑️ Delete</button>` : ''}
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

let adminFilterTimeout = null;
function filterAdminUsers() {
    if (adminFilterTimeout) clearTimeout(adminFilterTimeout);
    adminFilterTimeout = setTimeout(() => {
        loadAdminUsers();
    }, 300);
}

function openAdminEditModal(userId) {
    const user = adminUsersCache.find(u => u.id === userId);
    if (!user) return;

    document.getElementById('admin-edit-user-id').value = user.id;
    document.getElementById('admin-edit-username').value = user.username || '';
    document.getElementById('admin-edit-email').value = user.email || '';
    document.getElementById('admin-edit-is-admin').checked = Boolean(user.is_admin);

    document.getElementById('admin-edit-level').value = user.level || 1;
    document.getElementById('admin-edit-exp').value = user.exp || 0;
    document.getElementById('admin-edit-stat-points').value = user.stat_points || 0;

    document.getElementById('admin-edit-strength').value = user.strength || 10;
    document.getElementById('admin-edit-endurance').value = user.endurance || 10;
    document.getElementById('admin-edit-agility').value = user.agility || 10;
    document.getElementById('admin-edit-vitality').value = user.vitality || 10;

    const modal = document.getElementById('admin-edit-user-modal');
    if (modal) modal.style.display = 'flex';
}

function closeAdminEditModal() {
    const modal = document.getElementById('admin-edit-user-modal');
    if (modal) modal.style.display = 'none';
}

async function saveAdminUserStats() {
    const userId = parseInt(document.getElementById('admin-edit-user-id').value);
    if (!userId) return;

    const payload = {
        username: document.getElementById('admin-edit-username').value.trim(),
        email: document.getElementById('admin-edit-email').value.trim(),
        is_admin: document.getElementById('admin-edit-is-admin').checked,
        level: parseInt(document.getElementById('admin-edit-level').value) || 1,
        exp: parseInt(document.getElementById('admin-edit-exp').value) || 0,
        stat_points: parseInt(document.getElementById('admin-edit-stat-points').value) || 0,
        strength: parseInt(document.getElementById('admin-edit-strength').value) || 10,
        endurance: parseInt(document.getElementById('admin-edit-endurance').value) || 10,
        agility: parseInt(document.getElementById('admin-edit-agility').value) || 10,
        vitality: parseInt(document.getElementById('admin-edit-vitality').value) || 10
    };

    try {
        const response = await fetch(`${API_BASE}/api/admin/users/${userId}/update-stats`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
            credentials: 'include'
        });

        const data = await response.json();
        if (response.ok && data.success) {
            showToast(data.message || 'User stats updated successfully');
            closeAdminEditModal();
            await loadAdminTab();
            if (currentUser && currentUser.id === userId) {
                await loadDashboard();
            }
        } else {
            showToast(data.error || 'Failed to update user stats');
        }
    } catch (e) {
        console.error('Failed to save admin user stats:', e);
        showToast('Error updating user stats');
    }
}

function openAdminResetPasswordModal(userId, username) {
    document.getElementById('admin-reset-pwd-user-id').value = userId;
    document.getElementById('admin-reset-pwd-target-info').textContent = `Resetting password for Hunter '${username}' (ID: ${userId})`;
    document.getElementById('admin-reset-new-password').value = '';

    const modal = document.getElementById('admin-reset-password-modal');
    if (modal) modal.style.display = 'flex';
}

function closeAdminResetPasswordModal() {
    const modal = document.getElementById('admin-reset-password-modal');
    if (modal) modal.style.display = 'none';
}

async function submitAdminPasswordReset() {
    const userId = parseInt(document.getElementById('admin-reset-pwd-user-id').value);
    const newPassword = document.getElementById('admin-reset-new-password').value;

    if (!newPassword || newPassword.length < 4) {
        showToast('Password must be at least 4 characters long');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/admin/users/${userId}/reset-password`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ new_password: newPassword }),
            credentials: 'include'
        });

        const data = await response.json();
        if (response.ok && data.success) {
            showToast(data.message || 'Password reset successfully');
            closeAdminResetPasswordModal();
        } else {
            showToast(data.error || 'Failed to reset password');
        }
    } catch (e) {
        console.error('Failed to reset password:', e);
        showToast('Error resetting password');
    }
}

async function adminDeleteUser(userId, username) {
    if (!confirm(`⚠️ Are you SURE you want to delete hunter '${username}' (ID: ${userId})?\n\nThis will permanently delete their account, workout logs, stats, and all associated data.`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/admin/users/${userId}/delete`, {
            method: 'POST',
            credentials: 'include'
        });

        const data = await response.json();
        if (response.ok && data.success) {
            showToast(data.message || 'User deleted');
            await loadAdminTab();
        } else {
            showToast(data.error || 'Failed to delete user');
        }
    } catch (e) {
        console.error('Failed to delete user:', e);
        showToast('Error deleting user');
    }
}

async function activateGodMode(targetUserId = null) {
    const uid = targetUserId || (currentUser ? currentUser.id : null);
    if (!uid) return;

    try {
        const response = await fetch(`${API_BASE}/api/admin/god-mode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target_user_id: uid }),
            credentials: 'include'
        });

        const data = await response.json();
        if (response.ok && data.success) {
            showToast(data.message || '⚡ God Mode activated!');
            await loadAdminTab();
            if (!targetUserId || (currentUser && targetUserId === currentUser.id)) {
                await loadDashboard();
            }
        } else {
            showToast(data.error || 'Failed to activate God Mode');
        }
    } catch (e) {
        console.error('God mode error:', e);
        showToast('Error activating God Mode');
    }
}

async function loadAdminActivityFeed() {
    const feed = document.getElementById('admin-activity-feed');
    if (!feed) return;

    try {
        const response = await fetch(`${API_BASE}/api/admin/activity`, { credentials: 'include' });
        const data = await response.json();

        if (response.ok && data.success) {
            const workouts = data.workouts || [];
            if (workouts.length === 0) {
                feed.innerHTML = '<p class="no-data">No system workouts recorded yet.</p>';
                return;
            }

            feed.innerHTML = workouts.map(w => `
                <div style="padding: 12px 16px; background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="width: 32px; height: 32px; border-radius: 50%; background: rgba(16, 185, 129, 0.2); border: 1px solid rgba(16, 185, 129, 0.4); display: flex; align-items: center; justify-content: center; font-size: 0.85rem;">💪</span>
                        <div>
                            <span style="font-weight: 700; color: #f8fafc; font-size: 0.92rem;">${escapeHtml(w.username)}</span>
                            <span style="color: #94a3b8; font-size: 0.85rem; margin-left: 6px;">completed <strong style="color: #34d399;">${w.total_exercises} exercise(s)</strong> (${w.total_reps} total reps)</span>
                        </div>
                    </div>
                    <div style="text-align: right; font-size: 0.78rem; color: #94a3b8;">
                        <div style="color: #f59e0b; font-weight: 800; font-family: 'Orbitron', sans-serif;">+${w.exp_gained} EXP</div>
                        <div>${new Date(w.created_at || w.workout_date).toLocaleDateString()}</div>
                    </div>
                </div>
            `).join('');
        }
    } catch (e) {
        console.error('Failed to load admin activity feed:', e);
    }
}

async function loadAdminExercises() {
    const listEl = document.getElementById('admin-exercises-list');
    if (!listEl) return;

    try {
        const response = await fetch(`${API_BASE}/api/admin/exercises`, { credentials: 'include' });
        const data = await response.json();

        if (response.ok && data.success) {
            const exercises = data.exercises || [];
            if (exercises.length === 0) {
                listEl.innerHTML = '<p class="no-data">No custom exercise records found.</p>';
                return;
            }

            listEl.innerHTML = `
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px;">
                    ${exercises.map(ex => `
                        <div style="padding: 16px; background: rgba(15, 23, 42, 0.8); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; transition: transform 0.2s;">
                            <div style="font-weight: 800; font-family: 'Orbitron', sans-serif; color: #f8fafc; font-size: 0.95rem;">${escapeHtml(ex.exercise_name || ex.name || 'Exercise')}</div>
                            <div style="font-size: 0.75rem; font-weight: 700; color: #f59e0b; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px;">${escapeHtml(ex.category || 'general')}</div>
                            <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 8px;">Personal Record: <strong style="color: #38bdf8;">${ex.personal_record || 0}</strong></div>
                        </div>
                    `).join('')}
                </div>
            `;
        }
    } catch (e) {
        console.error('Failed to load admin exercises:', e);
    }
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
    
    let titleHtml = quest.title || 'Daily Quest';
    if (quest.target_name && !quest.title.includes(quest.target_name)) {
        titleHtml = `⚔️ Main Story Quest: Becoming ${quest.target_name}`;
    }
    
    document.getElementById('quest-title').innerHTML = `
        ${quest.target_name ? `<span class="quest-target-badge">🎭 Target: ${quest.target_name}</span><br>` : ''}
        ${titleHtml}
    `;
    
    const rankLetter = getQuestRankLetter(quest.difficulty || 1);
    document.getElementById('quest-difficulty').textContent = `Rank: ${rankLetter}`;
    document.getElementById('quest-reward').textContent = 
        `Reward: ${quest.exp_reward || 0} EXP`;
    
    const content = document.getElementById('quest-content');
    content.innerHTML = '';
    
    if (quest.is_rest_day) {
        content.innerHTML = `
            <div class="card">
                <h3>🛌 Rest Day Activities ${quest.target_name ? `(${quest.target_name}'s Split)` : ''}</h3>
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

function toggleAllQuestCheckboxes(masterCheckbox) {
    const isChecked = masterCheckbox.checked;
    const exerciseChecks = document.querySelectorAll('.exercise-complete-check');
    const setChecks = document.querySelectorAll('.set-complete-check');
    
    exerciseChecks.forEach(cb => { cb.checked = isChecked; });
    setChecks.forEach(cb => { cb.checked = isChecked; });
}

function updateMasterCheckboxState() {
    const exerciseChecks = document.querySelectorAll('.exercise-complete-check');
    const masterCheck = document.getElementById('master-quest-complete-check');
    if (masterCheck && exerciseChecks.length > 0) {
        const allChecked = Array.from(exerciseChecks).every(cb => cb.checked);
        masterCheck.checked = allChecked;
    }
}

function updateExerciseCheckState(exIndex) {
    const setChecks = document.querySelectorAll(`.set-complete-check[data-exercise="${exIndex}"]`);
    const exCheck = document.querySelector(`.exercise-complete-check[data-index="${exIndex}"]`);
    if (exCheck && setChecks.length > 0) {
        const allSetsChecked = Array.from(setChecks).every(cb => cb.checked);
        exCheck.checked = allSetsChecked;
        updateMasterCheckboxState();
    }
}

function createExerciseCard(exercise, index) {
    const setCount = exercise.sets || 3;
    const setCheckboxes = Array.from({ length: setCount }, (_, sIndex) => `
        <label class="set-checkbox-item" style="display: flex; align-items: center; gap: 6px; font-size: 0.85rem; background: var(--dark-bg); padding: 4px 10px; border-radius: 6px; border: 1px solid var(--card-border); cursor: pointer;">
            <input type="checkbox" class="set-complete-check" data-exercise="${index}" data-set="${sIndex}" onchange="updateExerciseCheckState(${index})" style="accent-color: var(--secondary-color); cursor: pointer;">
            <span>Set ${sIndex + 1}</span>
        </label>
    `).join('');

    return `
        <div class="exercise-card" data-exercise-index="${index}" style="border: 1px solid var(--card-border); border-radius: 12px; margin-bottom: 15px; padding: 18px;">
            <div class="exercise-header">
                <div class="exercise-name" style="font-size: 1.15rem; font-weight: 700;">${exercise.name}</div>
                <div class="exercise-category">${exercise.category}</div>
            </div>
            <div class="exercise-details">
                <div class="exercise-detail">
                    <div class="exercise-detail-label">Sets</div>
                    <div class="exercise-detail-value">${exercise.sets || 3}</div>
                </div>
                <div class="exercise-detail">
                    <div class="exercise-detail-label">Target</div>
                    <div class="exercise-detail-value">
                        ${exercise.target_reps ? exercise.target_reps + ' reps' : 
                          (exercise.target_duration_minutes ? exercise.target_duration_minutes + ' min' : '10 reps')}
                    </div>
                </div>
                <div class="exercise-detail">
                    <div class="exercise-detail-label">Rest</div>
                    <div class="exercise-detail-value">${exercise.rest_between_sets || 60}s</div>
                </div>
            </div>
            <p class="info-text">${exercise.description || ''}</p>
            <div class="sets-checkbox-row" style="margin-top: 12px; margin-bottom: 12px; display: flex; gap: 8px; flex-wrap: wrap;">
                ${setCheckboxes}
            </div>
            <div class="exercise-progress" style="background: rgba(16, 185, 129, 0.1); padding: 8px 12px; border-radius: 8px; border: 1px solid rgba(16, 185, 129, 0.3);">
                <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; font-weight: 600;">
                    <input type="checkbox" class="exercise-complete-check" data-index="${index}" onchange="updateMasterCheckboxState()" style="width: 18px; height: 18px; accent-color: var(--secondary-color); cursor: pointer;">
                    <span>Mark ${exercise.name} as Completed</span>
                </label>
            </div>
        </div>
    `;
}

function createRestExerciseCard(exercise, index) {
    return `
        <div class="exercise-card" style="border: 1px solid var(--card-border); border-radius: 12px; margin-bottom: 15px; padding: 18px;">
            <div class="exercise-header">
                <div class="exercise-name" style="font-size: 1.15rem; font-weight: 700;">${exercise.name}</div>
            </div>
            <p>${exercise.description}</p>
            <p><strong>Duration:</strong> ${exercise.duration_minutes} minutes</p>
            <div class="exercise-progress" style="margin-top: 12px; background: rgba(16, 185, 129, 0.1); padding: 8px 12px; border-radius: 8px; border: 1px solid rgba(16, 185, 129, 0.3);">
                <label style="display: flex; align-items: center; gap: 10px; cursor: pointer; font-weight: 600;">
                    <input type="checkbox" class="exercise-complete-check" data-index="${index}" onchange="updateMasterCheckboxState()" style="width: 18px; height: 18px; accent-color: var(--secondary-color); cursor: pointer;">
                    <span>Mark ${exercise.name} as Completed</span>
                </label>
            </div>
        </div>
    `;
}

async function completeQuest() {
    const masterCheck = document.getElementById('master-quest-complete-check');
    if (masterCheck && masterCheck.checked) {
        toggleAllQuestCheckboxes(masterCheck);
    }
    
    const checkboxes = document.querySelectorAll('.exercise-complete-check');
    const allCompleted = Array.from(checkboxes).every(cb => cb.checked);
    
    if (!allCompleted) {
        showToast('Please check off all exercises (or check the Master Completion box) first!');
        return;
    }
    
    // Gather completion data
    const completions = (currentQuest.exercises || []).map((exercise, index) => ({
        exercise_name: exercise.name,
        category: exercise.category,
        sets: exercise.sets || 3,
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
            await loadTodaysQuest();
        } else {
            showToast(data.message || 'Failed to complete quest');
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

const BEST_EXERCISES_PER_GOAL = {
    'strength': [
        { name: 'Diamond Push-ups', sets: 4, reps: '12-15', benefit: 'Progressive overload for chest, triceps & core power' },
        { name: 'Pull-ups / Chin-ups', sets: 3, reps: '8-10', benefit: 'Lats, upper back & bicep pulling strength' },
        { name: 'Bulgarian Split Squats', sets: 4, reps: '12', benefit: 'Unilateral leg strength & quad/glute development' },
        { name: 'Pike Push-ups', sets: 3, reps: '10', benefit: 'Deltoid shoulder strength & overhead push power' }
    ],
    'endurance': [
        { name: 'Full-Body Burpees', sets: 4, reps: '15', benefit: 'Maximal cardiovascular stamina & aerobic speed' },
        { name: 'Jump Rope Intervals', sets: 5, reps: '2 min', benefit: 'Footwork speed & high heart-rate endurance' },
        { name: 'Mountain Climbers', sets: 4, reps: '45 sec', benefit: 'Core stamina & continuous aerobic tempo' },
        { name: 'High Knees Sprint', sets: 6, reps: '30 sec', benefit: 'VO2 max elevation & explosive stamina' }
    ],
    'weight': [
        { name: 'Burpee Circuit Finisher', sets: 4, reps: '12-15', benefit: 'Highest calorie burn per minute of exercise' },
        { name: 'Jump Squats & Lunges', sets: 4, reps: '15', benefit: 'High metabolic demand & leg muscle toning' },
        { name: 'Shadow Boxing', sets: 3, reps: '3 min', benefit: 'Continuous aerobic fat loss & upper body agility' },
        { name: 'Jumping Jacks & Butt Kicks', sets: 4, reps: '45 sec', benefit: 'Sustained heart-rate elevation for fat burn' }
    ],
    'height': [
        { name: 'Bar Dead Hang', sets: 3, reps: '45-60 sec', benefit: 'Spinal decompression & gravity posture alignment' },
        { name: 'Cobra & Cat-Cow Stretch', sets: 3, reps: '60 sec', benefit: 'Spinal flexibility & posture lengthening' },
        { name: 'Pike Toe Touches', sets: 3, reps: '45 sec', benefit: 'Posterior chain hamstring & spine mobility' },
        { name: 'Glute Bridges & Wall Sits', sets: 3, reps: '12', benefit: 'Pelvic alignment & core posture support' }
    ],
    'exercise': [
        { name: 'Progressive Overload Sets', sets: 4, reps: '10-12', benefit: 'Systematic rep & load progression for mastery' },
        { name: 'Tempo / Pause Reps', sets: 3, reps: '8-10', benefit: 'Time under tension & strict execution control' },
        { name: 'Burnout Finisher Set', sets: 1, reps: 'Max', benefit: 'Peak muscle fiber recruitment & stamina' }
    ]
};

function getBestExercisesForGoal(goalType, goalName) {
    const typeKey = (goalType || 'strength').toLowerCase();
    let exercises = BEST_EXERCISES_PER_GOAL[typeKey] || BEST_EXERCISES_PER_GOAL['strength'];
    
    const nameLower = (goalName || '').toLowerCase();
    if (nameLower.includes('push') || nameLower.includes('chest')) {
        return [
            { name: 'Diamond Push-ups', sets: 4, reps: '12-15', benefit: 'Tricep & inner chest overload' },
            { name: 'Wide Push-ups', sets: 3, reps: '15', benefit: 'Outer chest & shoulder breadth' },
            { name: 'Pike Push-ups', sets: 3, reps: '10', benefit: 'Deltoid shoulder strength' },
            { name: 'Decline Push-ups', sets: 3, reps: '12', benefit: 'Upper chest development' }
        ];
    } else if (nameLower.includes('pull') || nameLower.includes('back')) {
        return [
            { name: 'Pull-ups', sets: 4, reps: '8-10', benefit: 'Lat width & back power' },
            { name: 'Chin-ups', sets: 3, reps: '10', benefit: 'Bicep & lower lat recruitment' },
            { name: 'Inverted Rows', sets: 3, reps: '12', benefit: 'Rhomboid & posture thickness' },
            { name: 'Dead Hang', sets: 3, reps: '45 sec', benefit: 'Grip strength & spine lengthening' }
        ];
    } else if (nameLower.includes('squat') || nameLower.includes('leg')) {
        return [
            { name: 'Bulgarian Split Squats', sets: 4, reps: '12', benefit: 'Unilateral quad & glute power' },
            { name: 'Jump Squats', sets: 3, reps: '15', benefit: 'Explosive leg power' },
            { name: 'Wall Sits', sets: 3, reps: '45 sec', benefit: 'Isometric quad endurance' },
            { name: 'Calf Raises', sets: 4, reps: '20', benefit: 'Calf & ankle stability' }
        ];
    } else if (nameLower.includes('abs') || nameLower.includes('core') || nameLower.includes('plank')) {
        return [
            { name: 'Planks & Side Planks', sets: 3, reps: '60 sec', benefit: 'Transverse abdominis stability' },
            { name: 'Hanging Leg Raises', sets: 3, reps: '12', benefit: 'Lower ab development' },
            { name: 'Russian Twists', sets: 3, reps: '20', benefit: 'Oblique strength & rotational power' },
            { name: 'V-Ups', sets: 3, reps: '12', benefit: 'Full abdominal compression' }
        ];
    }
    
    return exercises;
}

async function loadGoals() {
    try {
        const response = await fetch(`${API_BASE}/api/goals`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        const goalsList = document.getElementById('goals-list');
        const activeGoals = (data.goals || []).filter(g => g.status === 'active');
        const completedGoals = (data.goals || []).filter(g => g.status === 'completed');
        const totalGoals = (data.goals || []).length;
        const rate = totalGoals > 0 ? Math.round((completedGoals.length / totalGoals) * 100) : 0;
        
        const activeEl = document.getElementById('goals-count-active');
        if (activeEl) activeEl.textContent = activeGoals.length;
        const compEl = document.getElementById('goals-count-completed');
        if (compEl) compEl.textContent = completedGoals.length;
        const rateEl = document.getElementById('goals-completion-rate');
        if (rateEl) rateEl.textContent = `${rate}%`;
        
        if (!data.goals || data.goals.length === 0) {
            goalsList.innerHTML = '<p class="no-data">No active goals yet. Create one above or choose from the recommended exercise guide below!</p>';
        } else {
            goalsList.innerHTML = data.goals.map(goal => {
                const bestExs = getBestExercisesForGoal(goal.goal_type, goal.goal_name);
                const targetVal = goal.target_value || 1;
                const currentVal = goal.current_value || 0;
                const percent = Math.min(100, Math.round((currentVal / targetVal) * 100));
                
                return `
                    <div class="card" style="margin-bottom: 20px; border: 1px solid var(--card-border);">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px;">
                            <div style="flex: 1; min-width: 240px;">
                                <h3 style="font-size: 1.25rem; font-weight: 800; color: var(--text-primary);">${goal.goal_name}</h3>
                                <div style="display: flex; gap: 10px; align-items: center; margin-top: 6px; flex-wrap: wrap;">
                                    <span class="badge" style="background: var(--primary-color); color: #fff; padding: 2px 8px; border-radius: 4px; text-transform: capitalize; font-size: 0.8rem;">Category: ${goal.goal_type}</span>
                                    <span class="status-badge ${goal.status === 'completed' ? 'status-active' : ''}">${goal.status.toUpperCase()}</span>
                                    ${goal.deadline ? `<span style="font-size: 0.82rem; color: var(--text-secondary);">📅 Deadline: ${goal.deadline}</span>` : ''}
                                </div>
                                
                                <!-- Progress Bar & Numeric Tracker -->
                                <div style="margin-top: 14px; background: rgba(0,0,0,0.2); padding: 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.05);">
                                    <div style="display: flex; justify-content: space-between; font-size: 0.88rem; font-weight: 700; margin-bottom: 6px;">
                                        <span>Goal Target Progress</span>
                                        <span style="color: var(--secondary-color);">${percent}% (${currentVal} / ${targetVal})</span>
                                    </div>
                                    <div class="exp-bar" style="height: 12px; background: rgba(255,255,255,0.1); border-radius: 6px; overflow: hidden;">
                                        <div class="exp-fill" style="width: ${percent}%; height: 100%; background: linear-gradient(90deg, var(--primary-color), var(--secondary-color)); transition: width 0.4s ease;"></div>
                                    </div>
                                    
                                    ${goal.status === 'active' ? `
                                    <div style="display: flex; align-items: center; gap: 6px; margin-top: 10px; flex-wrap: wrap;">
                                        <span style="font-size: 0.82rem; color: var(--text-secondary); font-weight: 600;">Log Progress:</span>
                                        <button class="btn btn-small btn-secondary" onclick="incrementGoalProgress(${goal.id}, ${currentVal}, 1, ${targetVal})">+1</button>
                                        <button class="btn btn-small btn-secondary" onclick="incrementGoalProgress(${goal.id}, ${currentVal}, 5, ${targetVal})">+5</button>
                                        <button class="btn btn-small btn-secondary" onclick="incrementGoalProgress(${goal.id}, ${currentVal}, 10, ${targetVal})">+10</button>
                                        <button class="btn btn-small btn-primary" onclick="updateGoalProgress(${goal.id}, ${currentVal})">✏️ Custom Value</button>
                                    </div>
                                    ` : ''}
                                </div>
                            </div>
                            ${goal.status === 'active' ? `
                            <div>
                                <button class="btn btn-small btn-success" onclick="completeGoal(${goal.id})">✅ Mark Completed</button>
                            </div>
                            ` : ''}
                        </div>
                        
                        <!-- Best Exercises for This Specific Goal -->
                        <div class="best-exercises-for-goal" style="margin-top: 16px; padding: 14px; background: rgba(99, 102, 241, 0.08); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 10px;">
                            <h4 style="color: #a5b4fc; margin-bottom: 10px; font-size: 0.95rem; font-family: 'Orbitron', sans-serif; display: flex; align-items: center; gap: 6px;">
                                🔥 Best Exercises to Achieve "${goal.goal_name}"
                            </h4>
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px;">
                                ${bestExs.map(ex => `
                                    <div style="background: var(--dark-bg); padding: 10px 12px; border-radius: 8px; border: 1px solid var(--card-border);">
                                        <div style="font-weight: 700; color: var(--secondary-color); font-size: 0.9rem;">${ex.name}</div>
                                        <div style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 2px;">
                                            <strong>Target:</strong> ${ex.sets} sets × ${ex.reps}
                                        </div>
                                        <div style="font-size: 0.78rem; color: #94a3b8; margin-top: 4px; line-height: 1.3;">
                                            💡 <em>${ex.benefit}</em>
                                        </div>
                                    </div>
                                `).join('')}
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        loadBestExercisesGuide();
    } catch (error) {
        console.error('Failed to load goals:', error);
    }
}

async function incrementGoalProgress(goalId, currentValue, amount, targetValue) {
    const newVal = currentValue + amount;
    const isCompleted = newVal >= targetValue;
    
    try {
        const response = await fetch(`${API_BASE}/api/goals/${goalId}/update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                current_value: newVal,
                ...(isCompleted ? { status: 'completed' } : {})
            }),
            credentials: 'include'
        });
        const data = await response.json();
        if (response.ok) {
            if (isCompleted) {
                showToast('🎉 Goal 100% Reached & Completed!');
            } else {
                showToast(`Progress logged: +${amount}! (${newVal}/${targetValue})`);
            }
            await loadGoals();
        }
    } catch (error) {
        console.error('Failed to increment goal progress:', error);
    }
}

function loadBestExercisesGuide() {
    const guideDiv = document.getElementById('best-exercises-guide');
    if (!guideDiv) return;
    
    const categories = [
        { key: 'strength', label: '💪 Strength & Muscle', desc: 'Top exercises to maximize power, hypertrophy & muscle strength' },
        { key: 'endurance', label: '🏃 Endurance & Stamina', desc: 'Top exercises for cardiovascular capacity, VO2 max & stamina' },
        { key: 'weight', label: '🔥 Weight Loss & Fat Burn', desc: 'Highest metabolic demand exercises for maximum fat burn' },
        { key: 'height', label: '🧘 Height, Posture & Stretch', desc: 'Spinal decompression, posture reset & flexibility mobility' },
        { key: 'exercise', label: '⚔️ Exercise Mastery', desc: 'Progressive overload & time-under-tension protocols' }
    ];
    
    guideDiv.innerHTML = `
        <div style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 15px;">
            ${categories.map((c, i) => `
                <button class="btn btn-small ${i === 0 ? 'btn-primary' : 'btn-secondary'}" onclick="selectBestExerciseCategory('${c.key}', this)">
                    ${c.label}
                </button>
            `).join('')}
        </div>
        <div id="best-exercise-category-content"></div>
    `;
    
    renderBestExerciseCategoryContent('strength');
}

function selectBestExerciseCategory(catKey, btn) {
    document.querySelectorAll('#best-exercises-guide .btn').forEach(b => {
        b.classList.remove('btn-primary');
        b.classList.add('btn-secondary');
    });
    if (btn) {
        btn.classList.remove('btn-secondary');
        btn.classList.add('btn-primary');
    }
    renderBestExerciseCategoryContent(catKey);
}

function renderBestExerciseCategoryContent(catKey) {
    const contentDiv = document.getElementById('best-exercise-category-content');
    if (!contentDiv) return;
    
    const exercises = BEST_EXERCISES_PER_GOAL[catKey] || BEST_EXERCISES_PER_GOAL['strength'];
    
    contentDiv.innerHTML = `
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px;">
            ${exercises.map(ex => `
                <div class="card" style="background: var(--dark-bg); border: 1px solid var(--card-border); margin: 0; padding: 14px; display: flex; flex-direction: column; justify-content: space-between;">
                    <div>
                        <h4 style="color: var(--secondary-color); font-size: 1rem; margin-bottom: 4px;">${ex.name}</h4>
                        <p style="font-size: 0.85rem; color: var(--text-primary);"><strong>Recommended Target:</strong> ${ex.sets} sets × ${ex.reps}</p>
                        <p style="font-size: 0.8rem; color: var(--text-secondary); margin-top: 6px;">💡 ${ex.benefit}</p>
                    </div>
                    <button class="btn btn-small btn-primary" onclick="quickAddGoal('${catKey}', '${ex.name}', 100)" style="margin-top: 12px; align-self: flex-start;">
                        + Set as My Goal
                    </button>
                </div>
            `).join('')}
        </div>
    `;
}

function quickAddGoal(type, name, defaultTarget) {
    showAddGoalModal();
    const typeSelect = document.getElementById('goal-type');
    const nameInput = document.getElementById('goal-name');
    const targetInput = document.getElementById('goal-target');
    
    if (typeSelect) typeSelect.value = type;
    if (nameInput) nameInput.value = name;
    if (targetInput) targetInput.value = defaultTarget;
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
    const scopeEl = document.getElementById('leaderboard-scope');
    const scope = scopeEl ? scopeEl.value : 'global';
    
    try {
        const response = await fetch(`${API_BASE}/api/leaderboard?scope=${scope}`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        const leaderboard = document.getElementById('leaderboard');
        if (!leaderboard) return;
        
        let podiumsHTML = '';
        if (data.leaderboard && data.leaderboard.length >= 3 && scope === 'global') {
            const top3 = data.leaderboard.slice(0, 3);
            podiumsHTML = `
                <div class="leaderboard-podium-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 20px;">
                    ${top3.map((p, i) => {
                        const rankLetter = getRankLetterFromLevel(p.level || 1);
                        const crown = i === 0 ? '👑 1ST MONARCH' : (i === 1 ? '🥈 2ND HUNTER' : '🥉 3RD HUNTER');
                        const borderStyle = i === 0 
                            ? 'border: 2px solid #f59e0b; background: linear-gradient(135deg, rgba(245, 158, 11, 0.16) 0%, rgba(15, 23, 42, 0.95) 100%); box-shadow: 0 0 25px rgba(245, 158, 11, 0.25);'
                            : (i === 1 ? 'border: 2px solid #38bdf8; background: linear-gradient(135deg, rgba(56, 189, 248, 0.16) 0%, rgba(15, 23, 42, 0.95) 100%);'
                                       : 'border: 2px solid #a855f7; background: linear-gradient(135deg, rgba(168, 85, 247, 0.16) 0%, rgba(15, 23, 42, 0.95) 100%);');
                        return `
                            <div class="card podium-card" style="${borderStyle} padding: 18px; text-align: center; border-radius: 16px; transition: transform 0.25s ease;">
                                <div style="font-size: 0.72rem; font-weight: 900; font-family: 'Orbitron', sans-serif; letter-spacing: 0.8px; margin-bottom: 6px; ${i === 0 ? 'color: #f59e0b;' : (i === 1 ? 'color: #38bdf8;' : 'color: #c084fc;')}">${crown}</div>
                                <div class="clickable-username" onclick="viewHunterProfile(${p.id})" style="font-weight: 800; font-size: 1.05rem; color: #f8fafc; font-family: 'Orbitron', sans-serif;">${escapeHtml(p.username)}</div>
                                <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 4px;">${rankLetter}-Rank • Level ${p.level || 1}</div>
                                <div style="font-size: 0.8rem; font-weight: 800; color: #f59e0b; font-family: 'Orbitron', sans-serif; margin-top: 4px;">${p.exp || 0} EXP</div>
                            </div>
                        `;
                    }).join('')}
                </div>
            `;
        }

        const itemsHTML = data.leaderboard.map((player, index) => {
            let actionBtn = '';
            if (currentUser && player.id === currentUser.id) {
                actionBtn = `<span class="status-badge" style="background: rgba(99, 102, 241, 0.2); color: #a5b4fc;">You</span>`;
            } else if (player.friendship_status === 'accepted') {
                actionBtn = `<span class="status-badge status-active">Friends</span>`;
            } else if (player.friendship_status === 'pending') {
                if (player.request_sender_id === currentUser.id) {
                    actionBtn = `<button class="btn btn-small btn-secondary" onclick="declineFriend(${player.id})">Cancel Request</button>`;
                } else {
                    actionBtn = `
                        <div style="display: flex; gap: 6px;">
                            <button class="btn btn-small btn-success" onclick="acceptFriend(${player.id})">Accept Request</button>
                            <button class="btn btn-small btn-danger" onclick="declineFriend(${player.id})">Cancel</button>
                        </div>
                    `;
                }
            } else {
                actionBtn = `<button class="btn btn-small btn-primary" onclick="addFriend(${player.id})">+ Add Friend</button>`;
            }
            
            return `
                <div class="leaderboard-item ${currentUser && player.id === currentUser.id ? 'highlight' : ''}" style="justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <div class="leaderboard-rank">${index + 1}</div>
                        <div class="leaderboard-info">
                            <div class="leaderboard-name clickable-username" onclick="viewHunterProfile(${player.id})" title="Examine Hunter Profile">${escapeHtml(player.username)}</div>
                            <div class="leaderboard-stats">
                                Level ${player.level || 1} • ${player.exp || 0} EXP
                            </div>
                        </div>
                    </div>
                    <div>
                        ${actionBtn}
                    </div>
                </div>
            `;
        }).join('');

        leaderboard.innerHTML = podiumsHTML + itemsHTML;
    } catch (error) {
        console.error('Failed to load leaderboard:', error);
    }
}

function updatePendingBadge(count) {
    const badge = document.getElementById('social-pending-badge');
    const mobileBadge = document.getElementById('mobile-social-pending-badge');
    
    if (badge) {
        if (count > 0) {
            badge.textContent = ` (${count})`;
            badge.style.display = 'inline';
            badge.style.color = '#f59e0b';
            badge.style.fontWeight = 'bold';
        } else {
            badge.style.display = 'none';
        }
    }
    if (mobileBadge) {
        mobileBadge.textContent = count > 0 ? ` (${count})` : '';
    }
}

async function searchFriends() {
    const queryInput = document.getElementById('friend-search');
    if (!queryInput) return;
    const query = queryInput.value.trim();
    const results = document.getElementById('friend-search-results');
    if (!results) return;
    
    if (query.length < 2) {
        results.innerHTML = '';
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/friends/search?q=${encodeURIComponent(query)}`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        if (!data.users || data.users.length === 0) {
            results.innerHTML = '<p class="no-data" style="margin: 10px 0;">No hunters found matching your query.</p>';
            return;
        }
        
        results.innerHTML = data.users.map(user => {
            let actionBtn = '';
            if (user.friendship_status === 'accepted') {
                actionBtn = `<span class="status-badge status-active">Friends</span>`;
            } else if (user.friendship_status === 'pending') {
                if (user.request_sender_id === currentUser.id) {
                    // User 1 (Sender) sees ONLY Cancel Request button
                    actionBtn = `<button class="btn btn-small btn-secondary" onclick="declineFriend(${user.id})">Cancel Request</button>`;
                } else {
                    // User 2 (Recipient) sees Accept Request and Cancel buttons
                    actionBtn = `
                        <div style="display: flex; gap: 6px;">
                            <button class="btn btn-small btn-success" onclick="acceptFriend(${user.id})">Accept Request</button>
                            <button class="btn btn-small btn-danger" onclick="declineFriend(${user.id})">Cancel</button>
                        </div>
                    `;
                }
            } else {
                actionBtn = `<button class="btn btn-small btn-primary" onclick="addFriend(${user.id})">+ Add Friend</button>`;
            }
            
            return `
                <div class="leaderboard-item" style="margin-bottom: 8px; justify-content: space-between; align-items: center;">
                    <div class="leaderboard-info">
                        <div class="leaderboard-name clickable-username" onclick="viewHunterProfile(${user.id})" title="Examine Hunter Profile">${escapeHtml(user.username)}</div>
                        <div class="leaderboard-stats">Level ${user.level || 1}</div>
                    </div>
                    ${actionBtn}
                </div>
            `;
        }).join('');
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
            showToast(data.message || 'Friend request sent!');
            await loadFriends();
            await searchFriends();
            await loadLeaderboard();
        } else {
            showToast(data.error || 'Failed to send friend request');
        }
    } catch (error) {
        console.error('Failed to add friend:', error);
    }
}

async function acceptFriend(friendId) {
    try {
        const response = await fetch(`${API_BASE}/api/friends/accept`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ friend_id: friendId }),
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(data.message || 'Friend request accepted!');
            await loadFriends();
            await searchFriends();
            await loadLeaderboard();
        } else {
            showToast(data.error || 'Failed to accept friend request');
        }
    } catch (error) {
        console.error('Failed to accept friend:', error);
    }
}

async function declineFriend(friendId) {
    try {
        const response = await fetch(`${API_BASE}/api/friends/decline`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ friend_id: friendId }),
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast(data.message || 'Request updated.');
            await loadFriends();
            await searchFriends();
            await loadLeaderboard();
        } else {
            showToast(data.error || 'Failed to update request');
        }
    } catch (error) {
        console.error('Failed to decline friend:', error);
    }
}

async function removeFriend(friendId, username) {
    if (!confirm(`Remove ${username || 'this hunter'} from your friends list?`)) {
        return;
    }
    await declineFriend(friendId);
}

// Read-Only Hunter Profile Examination
async function viewHunterProfile(userId) {
    if (!userId || userId === 'undefined') {
        showToast('Invalid hunter ID');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/user/${userId}/profile`, {
            credentials: 'include'
        });
        
        const data = await response.json().catch(() => ({}));
        
        if (!response.ok) {
            showToast(data.error || 'Failed to load hunter profile');
            return;
        }
        const user = data.user || {};
        const stats = data.stats || {};
        const physique = data.physique_goal;
        const weeklyPlan = data.weekly_plan || [];
        const rank = data.rank || 'E-Rank Hunter';
        const rankLetter = rank.split('-')[0] || 'E';
        
        // Update Modal UI
        const modal = document.getElementById('hunter-profile-modal');
        if (!modal) return;
        
        document.getElementById('hunter-modal-username').textContent = user.username || 'Hunter';
        document.getElementById('hunter-modal-level').textContent = `Level ${stats.level || 1}`;
        document.getElementById('hunter-modal-rank-title').textContent = rank;
        
        // Rank Badge & Colors
        const rankBadge = document.getElementById('hunter-rank-badge');
        if (rankBadge) {
            rankBadge.textContent = rankLetter;
            const rankStyles = {
                'SS': 'background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%); color: #fff; box-shadow: 0 0 20px rgba(245, 158, 11, 0.6);',
                'S':  'background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%); color: #fff; box-shadow: 0 0 20px rgba(6, 182, 212, 0.6);',
                'A':  'background: linear-gradient(135deg, #a855f7 0%, #6366f1 100%); color: #fff; box-shadow: 0 0 15px rgba(168, 85, 247, 0.5);',
                'B':  'background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: #fff; box-shadow: 0 0 15px rgba(16, 185, 129, 0.4);',
                'C':  'background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); color: #fff; box-shadow: 0 0 12px rgba(59, 130, 246, 0.4);',
                'D':  'background: linear-gradient(135deg, #64748b 0%, #334155 100%); color: #f8fafc;',
                'E':  'background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: #0f172a; box-shadow: 0 0 12px rgba(245, 158, 11, 0.3);'
            };
            rankBadge.setAttribute('style', rankStyles[rankLetter] || rankStyles['E']);
        }
        
        // EXP bar
        const exp = stats.exp || 0;
        const maxExp = stats.exp_to_next_level || 100;
        const expPct = Math.min(100, Math.max(0, (exp / maxExp) * 100));
        document.getElementById('hunter-modal-exp-fill').style.width = `${expPct}%`;
        document.getElementById('hunter-modal-exp-text').textContent = `${exp} / ${maxExp} EXP`;
        
        // Parse Training Focus Badges
        const focusContainer = document.getElementById('hunter-modal-focus-tags');
        if (focusContainer) {
            let focusItems = [];
            const rawFocus = stats.primary_focus_areas;
            
            if (typeof rawFocus === 'string') {
                try {
                    const parsed = JSON.parse(rawFocus);
                    if (Array.isArray(parsed)) {
                        focusItems = parsed;
                    } else {
                        focusItems = rawFocus.split(',').map(s => s.trim());
                    }
                } catch(e) {
                    focusItems = rawFocus.split(',').map(s => s.trim());
                }
            } else if (Array.isArray(rawFocus)) {
                focusItems = rawFocus;
            }
            
            if (focusItems.length === 0) {
                focusItems = ['General Fitness'];
            }
            
            const focusIconMap = {
                'strength': '💪',
                'muscle_gain': '🏋️',
                'endurance': '⚡',
                'flexibility': '🧘',
                'height_growth': '📏',
                'general_fitness': '🎯',
                'fat_loss': '🔥',
                'cardio': '🏃'
            };
            
            focusContainer.innerHTML = focusItems.map(item => {
                const cleanKey = String(item).toLowerCase().replace(/[\s"-]/g, '_');
                const icon = focusIconMap[cleanKey] || '📌';
                const label = String(item)
                    .replace(/[\[\]"_]/g, ' ')
                    .trim()
                    .replace(/\b\w/g, l => l.toUpperCase());
                return `<span class="focus-pill-tag">${icon} ${escapeHtml(label)}</span>`;
            }).join('');
        }
        
        // Target Physique Goal
        const physiqueContainer = document.getElementById('hunter-modal-physique-container');
        if (physique && physique.target_name) {
            const rawTarget = physique.target_name.replace(/[_-]/g, ' ').trim();
            const formattedTarget = rawTarget.replace(/\b\w/g, l => l.toUpperCase());
            document.getElementById('hunter-modal-physique').textContent = `✨ ${formattedTarget}`;
            physiqueContainer.style.display = 'block';
        } else {
            physiqueContainer.style.display = 'none';
        }
        
        // Attributes
        document.getElementById('hunter-modal-str').textContent = stats.strength || 10;
        document.getElementById('hunter-modal-end').textContent = stats.endurance || 10;
        document.getElementById('hunter-modal-agi').textContent = stats.agility || 10;
        document.getElementById('hunter-modal-vit').textContent = stats.vitality || 10;
        
        // Weekly Plan Schedule List
        const scheduleList = document.getElementById('hunter-modal-schedule-list');
        if (weeklyPlan.length === 0) {
            scheduleList.innerHTML = '<p class="no-data" style="margin: 10px 0;">No active custom weekly plan configured.</p>';
        } else {
            const dayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
            scheduleList.innerHTML = weeklyPlan.map(day => {
                const dayName = dayNames[day.day_of_week] || `Day ${day.day_of_week + 1}`;
                const isRest = day.is_rest === 1;
                const badgeColor = isRest ? 'rgba(148, 163, 184, 0.2)' : 'rgba(99, 102, 241, 0.2)';
                const textColor = isRest ? '#94a3b8' : '#a5b4fc';
                
                let exercises = [];
                try {
                    exercises = typeof day.exercises_json === 'string' ? JSON.parse(day.exercises_json) : (day.exercises || []);
                } catch(e) {}
                
                const exerciseSummary = isRest 
                    ? 'Rest & Recovery Day' 
                    : (exercises.length > 0 ? exercises.map(ex => ex.name || ex).join(', ') : (day.focus || 'Training Day'));
                
                return `
                    <div style="padding: 10px 12px; margin-bottom: 8px; background: rgba(30, 41, 59, 0.5); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 8px; display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div style="font-weight: 700; font-size: 0.95rem; color: #f1f5f9;">${dayName} <span style="font-size: 0.8rem; font-weight: normal; color: #94a3b8;">(${day.focus || (isRest ? 'Rest' : 'Workout')})</span></div>
                            <div style="font-size: 0.82rem; color: #cbd5e1; margin-top: 2px;">${exerciseSummary}</div>
                        </div>
                        <span class="status-badge" style="background: ${badgeColor}; color: ${textColor}; font-size: 0.75rem;">
                            ${isRest ? '🛌 Rest' : '⚔️ Train'}
                        </span>
                    </div>
                `;
            }).join('');
        }
        
        // Display Modal
        modal.style.display = 'flex';
    } catch (error) {
        console.error('Failed to view hunter profile:', error);
        showToast('Error opening hunter profile');
    }
}

function closeHunterProfileModal() {
    const modal = document.getElementById('hunter-profile-modal');
    if (modal) modal.style.display = 'none';
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
        
        const incoming = pendingData.incoming || pendingData.pending || [];
        const outgoing = pendingData.outgoing || [];
        
        updatePendingBadge(incoming.length);
        
        // Dedicated top banner card for Incoming Requests
        const banner = document.getElementById('pending-requests-banner');
        const bannerList = document.getElementById('pending-requests-banner-list');
        
        if (incoming.length > 0) {
            if (banner) banner.style.display = 'block';
            if (bannerList) {
                bannerList.innerHTML = incoming.map(p => `
                    <div class="leaderboard-item" style="margin-bottom: 10px; padding: 12px 16px; background: rgba(245, 158, 11, 0.12); border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 10px; display: flex; justify-content: space-between; align-items: center;">
                        <div class="leaderboard-info">
                            <div class="leaderboard-name clickable-username" onclick="viewHunterProfile(${p.id})" title="Examine Hunter Profile" style="font-size: 1.1rem; font-weight: 800; color: #f59e0b;">${escapeHtml(p.username)}</div>
                            <div class="leaderboard-stats">Level ${p.level || 1} • Sent you a friend request</div>
                        </div>
                        <div style="display: flex; gap: 8px;">
                            <button class="btn btn-small btn-success" onclick="acceptFriend(${p.id})">
                                Accept Request
                            </button>
                            <button class="btn btn-small btn-danger" onclick="declineFriend(${p.id})">
                                Cancel
                            </button>
                        </div>
                    </div>
                `).join('');
            }
        } else {
            if (banner) banner.style.display = 'none';
        }
        
        const friendsList = document.getElementById('friends-list');
        if (!friendsList) return;
        
        let html = '';
        
        // Incoming Requests (User 2 / Recipient sees Accept Request & Cancel)
        if (incoming.length > 0) {
            html += `<h4 style="margin-top: 15px; color: #f59e0b; font-weight: 800; font-size: 1.05rem;">📩 Incoming Friend Requests (${incoming.length})</h4>`;
            html += incoming.map(p => `
                <div class="leaderboard-item" style="border-left: 4px solid #f59e0b; margin-bottom: 8px; justify-content: space-between; align-items: center;">
                    <div class="leaderboard-info">
                        <div class="leaderboard-name clickable-username" onclick="viewHunterProfile(${p.id})" title="Examine Hunter Profile" style="font-weight: 700;">${escapeHtml(p.username)}</div>
                        <div class="leaderboard-stats">Level ${p.level || 1}</div>
                    </div>
                    <div style="display: flex; gap: 6px;">
                        <button class="btn btn-small btn-success" onclick="acceptFriend(${p.id})">
                            Accept Request
                        </button>
                        <button class="btn btn-small btn-danger" onclick="declineFriend(${p.id})">
                            Cancel
                        </button>
                    </div>
                </div>
            `).join('');
        }
        
        // Outgoing Requests
        if (outgoing.length > 0) {
            html += `<h4 style="margin-top: 15px; color: #a5b4fc; font-weight: 700; font-size: 1.05rem;">📤 Requests Sent (${outgoing.length})</h4>`;
            html += outgoing.map(p => `
                <div class="leaderboard-item" style="border-left: 4px solid #a5b4fc; margin-bottom: 8px; justify-content: space-between; align-items: center;">
                    <div class="leaderboard-info">
                        <div class="leaderboard-name clickable-username" onclick="viewHunterProfile(${p.id})" title="Examine Hunter Profile" style="font-weight: 700;">${escapeHtml(p.username)}</div>
                        <div class="leaderboard-stats">Level ${p.level || 1} • Waiting for their response</div>
                    </div>
                    <button class="btn btn-small btn-secondary" onclick="declineFriend(${p.id})">
                        ✕ Cancel Request
                    </button>
                </div>
            `).join('');
        }
        
        // Active Friends
        html += `<h4 style="margin-top: 18px; font-weight: 700;">👥 Active Friends (${(data.friends || []).length})</h4>`;
        if (!data.friends || data.friends.length === 0) {
            html += '<p class="no-data">No active friends yet. Use the search bar above to find hunters!</p>';
        } else {
            html += data.friends.map(friend => `
                <div class="leaderboard-item" style="margin-bottom: 8px; justify-content: space-between;">
                    <div class="leaderboard-info">
                        <div class="leaderboard-name clickable-username" onclick="viewHunterProfile(${friend.id})" title="Examine Hunter Profile">${escapeHtml(friend.username)}</div>
                        <div class="leaderboard-stats">Level ${friend.level || 1} • ${friend.exp || 0} EXP</div>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span class="status-badge status-active">Accepted</span>
                        <button class="btn btn-small btn-secondary" onclick="removeFriend(${friend.id}, '${escapeHtml(friend.username)}')" style="padding: 2px 8px; font-size: 0.75rem;">
                            Unfriend
                        </button>
                    </div>
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

function toggleMobileMenu() {
    const navMenu = document.getElementById('nav-menu');
    const navToggle = document.getElementById('nav-toggle');
    if (navMenu) navMenu.classList.toggle('open');
    if (navToggle) navToggle.classList.toggle('open');
}

function showTab(tabName) {
    // Close mobile menu if open
    const navMenu = document.getElementById('nav-menu');
    const navToggle = document.getElementById('nav-toggle');
    if (navMenu) navMenu.classList.remove('open');
    if (navToggle) navToggle.classList.remove('open');

    // Update top and bottom nav links
    document.querySelectorAll('.nav-link, .bottom-nav-link').forEach(link => {
        link.classList.remove('active');
    });
    document.querySelectorAll(`[data-tab="${tabName}"]`).forEach(link => {
        link.classList.add('active');
    });
    
    // Update tab content
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });
    const targetTab = document.getElementById(`tab-${tabName}`);
    if (targetTab) targetTab.classList.add('active');
    
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
    } else if (tabName === 'admin') {
        loadAdminTab();
    }
}

function renderActiveTargetBanner(targetName) {
    const bannerEl = document.getElementById('active-target-banner');
    if (!bannerEl) return;
    
    if (targetName) {
        bannerEl.innerHTML = `
            <div class="target-banner-content active-build-banner">
                <div class="target-banner-info">
                    <span class="target-badge">🎭 ACTIVE TARGET</span>
                    <h2 class="target-title">Training to Become: <span class="target-highlight">${targetName}</span></h2>
                    <p class="target-subtitle">Daily Quests & Main Story Split are dynamically tailored to build ${targetName}'s physique.</p>
                </div>
                <div class="target-banner-actions">
                    ${window._activeQuestLogMarkdown ? `<button class="btn btn-small btn-primary" onclick="openActiveQuestLogModal()">📜 View Quest Log</button>` : ''}
                    <button class="btn btn-small btn-secondary" onclick="showTab('physique')">🔄 Change Target</button>
                </div>
            </div>
        `;
    } else {
        bannerEl.innerHTML = `
            <div class="target-banner-content no-target-banner">
                <div class="target-banner-info">
                    <span class="target-badge inactive">ℹ️ NO TARGET SELECTED</span>
                    <h3 class="target-title">Choose a Character in "Become Like..."</h3>
                    <p class="target-subtitle">Select any anime character or athlete (e.g. Sung Jinwoo, Saitama, Levi) to unlock their custom Main Story Quests!</p>
                </div>
                <div class="target-banner-actions">
                    <button class="btn btn-primary" onclick="showTab('physique')">🎭 Choose Character Target</button>
                </div>
            </div>
        `;
    }
}

function openActiveQuestLogModal() {
    const modal = document.getElementById('active-quest-log-modal');
    const titleEl = document.getElementById('active-quest-log-modal-title');
    const bodyEl = document.getElementById('active-quest-log-modal-body');
    
    if (!modal || !bodyEl) return;
    
    const targetName = window._activeTargetName || 'Target Character';
    const markdown = window._activeQuestLogMarkdown;
    
    if (titleEl) titleEl.textContent = `📜 Quest Log: Becoming ${targetName}`;
    
    if (markdown) {
        bodyEl.innerHTML = typeof marked !== 'undefined' 
            ? marked.parse(markdown) 
            : `<pre>${markdown}</pre>`;
    } else {
        bodyEl.innerHTML = '<p class="no-data">No Quest Log markdown available. Select or analyze a character target in "Become Like..." to generate one.</p>';
    }
    
    modal.classList.add('active');
}

async function loadWeeklySchedule() {
    const grid = document.getElementById('weekly-schedule-grid');
    if (!grid) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/quest/weekly-schedule`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        window._activeTargetName = data.target_name || null;
        window._activeQuestLogMarkdown = data.quest_log_markdown || null;
        
        renderActiveTargetBanner(data.target_name);
        
        const titleEl = document.getElementById('main-story-title');
        const subtitleEl = document.getElementById('main-story-subtitle');
        const viewQuestLogBtn = document.getElementById('view-full-quest-log-btn');
        
        if (data.target_name) {
            if (titleEl) titleEl.textContent = `📖 Main Story Quests — Becoming ${data.target_name}`;
            if (subtitleEl) subtitleEl.textContent = `Weekly training split for ${data.target_name}. Today's active day is highlighted.`;
            if (viewQuestLogBtn) viewQuestLogBtn.style.display = data.quest_log_markdown ? 'inline-block' : 'none';
        } else {
            if (titleEl) titleEl.textContent = '📖 Main Story Quests';
            if (subtitleEl) subtitleEl.textContent = 'Your complete weekly training split (Monday to Sunday). Select a character in Become Like... to personalize.';
            if (viewQuestLogBtn) viewQuestLogBtn.style.display = 'none';
        }
        
        if (!data.schedule || data.schedule.length === 0) {
            grid.innerHTML = '<p class="no-data">No Main Story Quests generated yet.</p>';
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
        console.error('Failed to load Main Story Quests schedule:', error);
        if (grid) grid.innerHTML = '<p class="error-message">Failed to load Main Story Quests schedule</p>';
    }
}

function getRankLetterFromLevel(level) {
    if (level >= 100) return 'SS';
    if (level >= 80) return 'S';
    if (level >= 60) return 'A';
    if (level >= 40) return 'B';
    if (level >= 25) return 'C';
    if (level >= 10) return 'D';
    return 'E';
}

function getRankTitleFromLevel(level) {
    return `${getRankLetterFromLevel(level)}-Rank Hunter`;
}

async function loadWeeklyActivity() {
    const grid = document.getElementById('weekly-bubbles-grid');
    const rankUpsCountEl = document.getElementById('rank-ups-count');
    if (!grid) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/weekly-activity`, {
            credentials: 'include'
        });
        const data = await response.json();
        
        if (response.ok && data.success) {
            if (rankUpsCountEl) {
                rankUpsCountEl.textContent = data.rank_ups || 0;
            }
            
            grid.innerHTML = (data.week_days || []).map(day => {
                const count = day.count || 0;
                const isToday = day.is_today;
                const activeClass = count > 0 ? 'workout-active-fill' : 'rest-hollow-circle';
                const todayClass = isToday ? 'today-active-ring' : '';
                
                return `
                    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1;">
                        <div class="day-bubble ${activeClass} ${todayClass}" title="${day.date}: ${count} workout(s) ${count > 0 ? '(Completed)' : '(Rest Day)'}">
                            ${day.day_code}
                        </div>
                    </div>
                `;
            }).join('');
        }
    } catch (error) {
        console.error('Failed to load weekly activity:', error);
    }
}

function updateStatusTabCard() {
    if (!currentStats) return;
    
    const level = currentStats.level || 1;
    const exp = currentStats.exp || 0;
    const maxExp = currentStats.exp_to_next_level || 100;
    const rankTitle = getRankTitleFromLevel(level);
    const rankLetter = getRankLetterFromLevel(level);
    
    const badge = document.getElementById('status-rank-badge');
    const title = document.getElementById('status-rank-title');
    const levelExp = document.getElementById('status-level-exp');
    
    if (badge) {
        badge.textContent = rankLetter;
        const rankStyles = {
            'SS': 'background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%); color: #fff; box-shadow: 0 0 20px rgba(245, 158, 11, 0.6);',
            'S':  'background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%); color: #fff; box-shadow: 0 0 20px rgba(6, 182, 212, 0.6);',
            'A':  'background: linear-gradient(135deg, #a855f7 0%, #6366f1 100%); color: #fff; box-shadow: 0 0 15px rgba(168, 85, 247, 0.5);',
            'B':  'background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: #fff; box-shadow: 0 0 15px rgba(16, 185, 129, 0.4);',
            'C':  'background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); color: #fff; box-shadow: 0 0 12px rgba(59, 130, 246, 0.4);',
            'D':  'background: linear-gradient(135deg, #64748b 0%, #334155 100%); color: #f8fafc;',
            'E':  'background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: #0f172a; box-shadow: 0 0 12px rgba(245, 158, 11, 0.3);'
        };
        badge.setAttribute('style', rankStyles[rankLetter] || rankStyles['E']);
    }
    if (title) title.textContent = rankTitle;
    if (levelExp) levelExp.textContent = `Level ${level} • ${exp} / ${maxExp} EXP`;
    
    loadWeeklyActivity();
}

function openAllRanksModal() {
    const modal = document.getElementById('all-ranks-modal');
    const ranksList = document.getElementById('all-ranks-list');
    if (!modal || !ranksList) return;
    
    const userLevel = currentStats ? (currentStats.level || 1) : 1;
    const currentLetter = getRankLetterFromLevel(userLevel);
    
    const allRanks = [
        { letter: 'SS', title: 'SS-Rank Hunter', levels: 'Level 100+', style: 'background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%); color: #fff;', desc: 'Supreme Monarch Tier - Absolute Dominance' },
        { letter: 'S', title: 'S-Rank Hunter', levels: 'Level 80 – 99', style: 'background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%); color: #fff;', desc: 'National Level Hunter - Elite Powerhouse' },
        { letter: 'A', title: 'A-Rank Hunter', levels: 'Level 60 – 79', style: 'background: linear-gradient(135deg, #a855f7 0%, #6366f1 100%); color: #fff;', desc: 'High-Tier Raid Commander' },
        { letter: 'B', title: 'B-Rank Hunter', levels: 'Level 40 – 59', style: 'background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: #fff;', desc: 'Advanced Striker Tier' },
        { letter: 'C', title: 'C-Rank Hunter', levels: 'Level 25 – 39', style: 'background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); color: #fff;', desc: 'Intermediate Hunter Tier' },
        { letter: 'D', title: 'D-Rank Hunter', levels: 'Level 10 – 24', style: 'background: linear-gradient(135deg, #64748b 0%, #334155 100%); color: #f8fafc;', desc: 'Novice Combatant Tier' },
        { letter: 'E', title: 'E-Rank Hunter', levels: 'Level 1 – 9', style: 'background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: #0f172a;', desc: 'Awakened Trainee Tier' }
    ];
    
    ranksList.innerHTML = allRanks.map(r => {
        const isCurrent = r.letter === currentLetter;
        const borderStyle = isCurrent ? 'border: 2px solid #f59e0b; background: rgba(245, 158, 11, 0.12);' : 'border: 1px solid rgba(255, 255, 255, 0.08); background: rgba(15, 23, 42, 0.6);';
        
        return `
            <div style="padding: 12px 14px; border-radius: 12px; ${borderStyle} display: flex; justify-content: space-between; align-items: center;">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="width: 38px; height: 38px; border-radius: 10px; ${r.style} display: flex; align-items: center; justify-content: center; font-family: 'Orbitron', sans-serif; font-size: 1.25rem; font-weight: 900;">
                        ${r.letter}
                    </div>
                    <div>
                        <div style="font-weight: 700; font-size: 0.95rem; color: #f8fafc; font-family: 'Orbitron', sans-serif; display: flex; align-items: center;">
                            ${r.title}
                            ${isCurrent ? `<span class="status-badge" style="background: rgba(245, 158, 11, 0.25); color: #f59e0b; margin-left: 8px; font-size: 0.7rem; font-weight: 800;">👈 YOUR RANK</span>` : ''}
                        </div>
                        <div style="font-size: 0.78rem; color: #94a3b8; margin-top: 2px;">${r.desc} • <strong style="color: #60a5fa;">${r.levels}</strong></div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    modal.style.display = 'flex';
}

function closeAllRanksModal() {
    const modal = document.getElementById('all-ranks-modal');
    if (modal) modal.style.display = 'none';
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
            const gradient = ctx.createLinearGradient(0, 0, 0, 260);
            gradient.addColorStop(0, 'rgba(99, 102, 241, 0.4)');
            gradient.addColorStop(1, 'rgba(99, 102, 241, 0.0)');

            progressChartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels.length > 0 ? labels : ['No Data'],
                    datasets: [{
                        label: 'EXP Progress',
                        data: expValues.length > 0 ? expValues : [0],
                        borderColor: '#6366f1',
                        borderWidth: 3,
                        backgroundColor: gradient,
                        fill: true,
                        tension: 0.35,
                        pointBackgroundColor: '#38bdf8',
                        pointBorderColor: '#6366f1',
                        pointBorderWidth: 2,
                        pointRadius: 5,
                        pointHoverRadius: 8
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        mode: 'index',
                        intersect: false
                    },
                    plugins: {
                        legend: { 
                            display: true,
                            labels: { color: '#f1f5f9', font: { family: 'Orbitron', size: 12, weight: 'bold' } } 
                        },
                        tooltip: {
                            backgroundColor: 'rgba(15, 23, 42, 0.95)',
                            titleColor: '#38bdf8',
                            bodyColor: '#f8fafc',
                            borderColor: '#6366f1',
                            borderWidth: 1,
                            padding: 10
                        }
                    },
                    scales: {
                        x: { 
                            ticks: { color: '#94a3b8', font: { size: 11 } }, 
                            grid: { color: 'rgba(255, 255, 255, 0.05)' } 
                        },
                        y: { 
                            ticks: { color: '#94a3b8', font: { size: 11 } }, 
                            grid: { color: 'rgba(255, 255, 255, 0.05)' }, 
                            beginAtZero: true 
                        }
                    }
                }
            });
        }
    } catch (error) {
        console.error('Failed to update charts:', error);
    }
}

async function loadProgressData() {
    try {
        updateStatusTabCard();
        await updateCharts();
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
