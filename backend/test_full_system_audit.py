import sys
import io
import urllib.request
import urllib.parse
import json
import http.cookiejar
import re
import time

# Fix Windows console encoding for UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_URL = "http://127.0.0.1:5000"

def run_audit():
    print("=" * 60)
    print("[*] INITIATING FULL LIVE SYSTEM & OPERATIONAL AUDIT")
    print("=" * 60)
    
    # Setup cookie jar for session authentication
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    
    passed = 0
    failed = 0
    
    def log_test(name, success, detail=""):
        nonlocal passed, failed
        if success:
            passed += 1
            print(f"  [PASS] {name} | {detail}")
        else:
            failed += 1
            print(f"  [FAIL] {name} | {detail}")

    # 1. Test Homepage & HTML Integrity
    try:
        req = urllib.request.Request(f"{BASE_URL}/")
        with opener.open(req) as resp:
            html = resp.read().decode('utf-8')
            log_test("GET / (Homepage HTML)", resp.status == 200, f"Status: {resp.status}")
            
            # Check Recent Achievements is NOT in HTML
            has_recent_achieve = "Recent Achievements" in html or "id=\"recent-achievements\"" in html
            log_test("Recent Achievements Removed", not has_recent_achieve, "Recent Achievements is completely absent from DOM")
            
            # Check 1RM Calc is NOT in HTML
            has_1rm = "1RM Calc" in html or "id=\"tab-calculator\"" in html
            log_test("1RM Calculator Tab Removed", not has_1rm, "1RM Calc is completely absent from DOM & Nav")
            
            # Check Stat allocation section is present
            has_stat_alloc = "stat-points-section" in html and "stat-allocation" in html
            log_test("Stat Points Allocation Section Present", has_stat_alloc, "Pills present in DOM")
            
            # Check Weekly activity card and round bubbles grid
            has_weekly = "weekly-bubbles-grid" in html
            log_test("Weekly Activity Bubbles Grid Present", has_weekly, "Bubbles container present")
            
            # Check consistency bar is removed
            has_consistency_bar = "weekly-consistency-fill" in html
            log_test("Weekly Consistency Bar Removed", not has_consistency_bar, "Consistency calculation bar removed")
    except Exception as e:
        log_test("GET / (Homepage HTML)", False, str(e))

    # 2. Test Static Files Integrity
    try:
        req_css = urllib.request.Request(f"{BASE_URL}/static/css/style.css")
        with opener.open(req_css) as resp:
            css = resp.read().decode('utf-8')
            log_test("GET /static/css/style.css", resp.status == 200, f"Size: {len(css)} bytes")
            has_2x2 = re.search(r'\.stat-allocation\s*\{[^}]*grid-template-columns:\s*repeat\(2,\s*1fr\)', css) is not None
            log_test("Stat Allocation 2x2 CSS Grid", has_2x2, "repeat(2, 1fr) configured")
            has_bubble_clean = ".day-bubble-clean" in css
            log_test("Clean Round Day Bubbles CSS", has_bubble_clean, ".day-bubble-clean defined")
    except Exception as e:
        log_test("Static CSS Integrity", False, str(e))

    try:
        req_js = urllib.request.Request(f"{BASE_URL}/static/js/app.js")
        with opener.open(req_js) as resp:
            js = resp.read().decode('utf-8')
            log_test("GET /static/js/app.js", resp.status == 200, f"Size: {len(js)} bytes")
    except Exception as e:
        log_test("Static JS Integrity", False, str(e))

    # 3. Test Registration & Auto-Login
    audit_username = f"audit_{int(time.time())}"
    try:
        reg_data = json.dumps({
            "username": audit_username,
            "email": f"{audit_username}@system.audit",
            "password": "Password123!"
        }).encode('utf-8')
        req_reg = urllib.request.Request(
            f"{BASE_URL}/api/register",
            data=reg_data,
            headers={"Content-Type": "application/json"}
        )
        with opener.open(req_reg) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            log_test("POST /api/register (Live User)", data.get('success') is True, f"Registered: {audit_username}")
    except Exception as e:
        log_test("POST /api/register", False, str(e))

    # 4. Test Profile Setup
    try:
        setup_data = json.dumps({
            "age": 22,
            "height_cm": 178,
            "weight_kg": 72,
            "target_weight": 76,
            "primary_focus_areas": ["strength", "muscle_gain"],
            "experience_level": "intermediate",
            "days_per_week": 5,
            "body_type": "mesomorph",
            "injuries": "None",
            "equipment": "Full Commercial Gym"
        }).encode('utf-8')
        req_setup = urllib.request.Request(
            f"{BASE_URL}/api/setup-profile",
            data=setup_data,
            headers={"Content-Type": "application/json"}
        )
        with opener.open(req_setup) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            log_test("POST /api/setup-profile", data.get('success') is True, "Profile and initial quests established")
    except Exception as e:
        log_test("POST /api/setup-profile", False, str(e))

    # 5. Test Player Stats API
    try:
        req_stats = urllib.request.Request(f"{BASE_URL}/api/stats")
        with opener.open(req_stats) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            stats = data.get('stats', {})
            success = stats is not None and 'level' in stats
            log_test("GET /api/stats", success, f"Level {stats.get('level')} • Rank: {stats.get('rank')} • Eq: {stats.get('equipment')}")
    except Exception as e:
        log_test("GET /api/stats", False, str(e))

    # 6. Test Weekly Activity API
    try:
        req_week = urllib.request.Request(f"{BASE_URL}/api/weekly-activity")
        with opener.open(req_week) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            success = data.get('success') is True
            days = data.get('week_days', [])
            log_test("GET /api/weekly-activity", success and len(days) == 7, f"Returned {len(days)} days, Streak: {data.get('active_streak')}, EXP: {data.get('weekly_exp_earned')}")
    except Exception as e:
        log_test("GET /api/weekly-activity", False, str(e))

    # 7. Test Progress Chart API
    try:
        req_chart = urllib.request.Request(f"{BASE_URL}/api/stats/progress?days=30")
        with opener.open(req_chart) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            success = data.get('success') is True
            items = data.get('exp_progress', [])
            log_test("GET /api/stats/progress (Chart Data)", success, f"Returned {len(items)} progress points")
    except Exception as e:
        log_test("GET /api/stats/progress", False, str(e))

    # 8. Test Today Quest API
    try:
        req_quest = urllib.request.Request(f"{BASE_URL}/api/quest/today")
        with opener.open(req_quest) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            success = resp.status == 200 and 'quest' in data
            quest = data.get('quest', {})
            ex_count = len(quest.get('exercises', []))
            log_test("GET /api/quest/today", success, f"Title: '{quest.get('title')}' with {ex_count} exercises")
    except Exception as e:
        log_test("GET /api/quest/today", False, str(e))

    # 9. Test Equipment Switching Endpoints
    for eq in ["Home / Bodyweight", "Dumbbells", "Full Commercial Gym"]:
        try:
            eq_data = json.dumps({"equipment": eq}).encode('utf-8')
            req_eq = urllib.request.Request(
                f"{BASE_URL}/api/player/change-equipment",
                data=eq_data,
                headers={"Content-Type": "application/json"}
            )
            with opener.open(req_eq) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                success = data.get('success') is True
                new_q = data.get('quest', {})
                log_test(f"POST /api/player/change-equipment ({eq})", success, f"Adapted quest: {new_q.get('title')}")
        except Exception as e:
            log_test(f"POST /api/player/change-equipment ({eq})", False, str(e))

    # 10. Test Hunter License Card Data API
    try:
        req_card = urllib.request.Request(f"{BASE_URL}/api/hunter-card/data")
        with opener.open(req_card) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            success = data.get('success') is True
            hunter = data.get('hunter', {})
            log_test("GET /api/hunter-card/data", success, f"License: {hunter.get('title')} • Level: {hunter.get('level')}")
    except Exception as e:
        log_test("GET /api/hunter-card/data", False, str(e))

    # 11. Test Leaderboard De-duplication API (Global & Friends)
    try:
        req_lb = urllib.request.Request(f"{BASE_URL}/api/leaderboard?scope=global")
        with opener.open(req_lb) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            lb = data.get('leaderboard', [])
            ids = [p['id'] for p in lb]
            has_duplicates = len(ids) != len(set(ids))
            log_test("GET /api/leaderboard (No Duplicates)", not has_duplicates, f"Total {len(lb)} unique entries, duplicates: {len(ids) - len(set(ids))}")
    except Exception as e:
        log_test("GET /api/leaderboard", False, str(e))

    print("=" * 60)
    print(f"[*] AUDIT SUMMARY: {passed} PASSED, {failed} FAILED")
    print("=" * 60)
    return failed == 0

if __name__ == "__main__":
    success = run_audit()
    sys.exit(0 if success else 1)
