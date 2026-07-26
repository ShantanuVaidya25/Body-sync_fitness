# ⚔️ SOLO LEVELING FITNESS SYSTEM

**An AI-Powered Fitness Progression System Inspired by Solo Leveling**

Transform your fitness journey into an epic RPG adventure! Level up, gain stats, complete daily quests, and become the strongest version of yourself.

---

## 🌟 FEATURES

### Core Gameplay Systems

#### 1. **RPG-Style Progression**
- **Level System**: Gain EXP from completing quests and workouts
- **Stat Points**: Allocate points to Strength, Endurance, Agility, and Vitality
- **Rank System**: Progress from E-Rank to SS-Rank Hunter
- **Experience Curve**: Dynamic leveling that scales with your growth

#### 2. **AI-Powered Daily Quests**
- **Personalized Quest Generation**: AI analyzes your goals, stats, and progress
- **Adaptive Difficulty**: Quests scale based on your level and capabilities
- **Variety & Rotation**: Never get the same boring routine
- **Recovery Management**: Automatic rest day scheduling based on workout intensity
- **Progressive Overload**: Gradual increases in reps, sets, and intensity

#### 3. **Smart Recovery System**
- **Intelligent Rest Days**: System detects when you need recovery
- **Active Recovery Quests**: Light stretching, walking, and meditation on rest days
- **Workout Streak Tracking**: Monitor consistency without burnout
- **Recovery Metrics**: Balance intensity with adequate rest

#### 4. **Goal-Oriented Training**
- **Custom Goals**: Set strength, endurance, weight, or height goals
- **AI Quest Customization**: Daily quests automatically adapt to your goals
- **Progress Tracking**: Visual progress charts and statistics
- **Deadline Management**: Optional deadlines for time-bound goals

#### 5. **Comprehensive Exercise Tracking**
- **Personal Records**: Track max reps, weights, and durations
- **Exercise History**: Complete workout history with timestamps
- **Progressive Targets**: AI increases targets based on your PRs
- **Exercise Variety**: 50+ exercises across strength, cardio, and flexibility

#### 6. **Social & Competition Features**
- **Friends System**: Add friends and compare progress
- **Leaderboards**: Global and friends-only rankings
- **Level Competition**: See who's the strongest Hunter
- **Social Motivation**: Train together and push each other

#### 7. **Body Measurement Tracking**
- **Height & Weight Monitoring**: Track physical changes over time
- **Progress Visualization**: See your transformation journey
- **Target Goals**: Set and track target measurements
- **Weekly Updates**: Regular check-ins to monitor progress

---

## 🎯 PRIMARY OBJECTIVE PATH (Multi-Select Goals)

During profile setup, you now select **one or more** training objectives:

- 💪 Strength
- 🏋️ Muscle Gain
- 🔥 Weight Loss
- 🏃 Endurance & Stamina
- 🧘 Flexibility & Mobility
- 📏 Height Growth
- ❤️ General Fitness & Health
- ⚡ Sport / Athletic Performance

You can pick as many as apply. The AI blends them together — e.g. selecting 
**Muscle Gain + Endurance** generates quests mixing strength work with cardio 
conditioning, rather than forcing you to choose one lane. Your first quest is 
generated immediately after setup, and every quest afterward is built around 
this combination. You can update your objective path anytime via the 
`/api/goals/objective-path` endpoint.

---

## 🎭 "BECOME LIKE..." — AI PHYSIQUE ANALYZER

A standout feature: name an anime character or real person (or upload a 
reference photo), and Claude acts as a **Master Fitness RPG Game Master** to:

1. **Analyze the physique** — dominant muscle groups, body-fat style 
   (lean/bulky/athletic), and the training approach needed.
2. **Generate a full Quest Log**:
   - **Daily Dailies** — nutrition & lifestyle habits
   - **Main Story Quests** — a weekly training split for that specific build
   - **Side Quests** — fun, thematic optional challenges
   - **Level Up Milestones** — how you'll know you're progressing

### Setup Required

This feature calls the Anthropic API and needs your own API key:

1. Get a key at **https://console.anthropic.com/**
2. Set it as an environment variable before starting the server:

   **Mac/Linux:**
   ```bash
   export ANTHROPIC_API_KEY="your-key-here"
   cd backend
   python app.py
   ```

   **Windows (Command Prompt):**
   ```cmd
   set ANTHROPIC_API_KEY=your-key-here
   cd backend
   python app.py
   ```

   **Windows (PowerShell):**
   ```powershell
   $env:ANTHROPIC_API_KEY="your-key-here"
   cd backend
   python app.py
   ```

3. Install the SDK (already in requirements.txt): `pip install anthropic`

Without the key, the rest of the app works normally — you'll just see a 
warning banner on the "Become Like..." tab until it's configured.

### How It Works

- **Name mode**: Type any character or public figure's name. The prompt is 
  sent as text to Claude.
- **Photo mode**: Upload a JPG/PNG/WEBP reference photo. It's sent as an 
  image alongside the same structured prompt, so the physique analysis is 
  grounded in the actual photo rather than a name lookup.
- Every analysis is saved to your account under **Past Build Goals**, so you 
  can revisit, reactivate, or delete previous Quest Logs at any time.
- Only one Quest Log is "active" as your current build goal at a time.

---

## 🚀 INSTALLATION & SETUP

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Modern web browser (Chrome, Firefox, Safari, Edge)

### Step 1: Clone or Download

```bash
# If you have the files in a folder, navigate to it
cd solo_leveling_fitness
```

### Step 2: Install Dependencies

```bash
# Install required Python packages
pip install -r requirements.txt
```

### Step 3: Run the Application

```bash
# Navigate to backend folder
cd backend

# Run the Flask server
python app.py
```

The server will start at `http://localhost:5000`

### Step 4: Access the Application

Open your web browser and go to:
```
http://localhost:5000
```

---

## 📖 USER GUIDE

### Getting Started

#### 1. **Create Your Account**
- Click "Register Here" on the login page
- Enter username, email, and password
- Click "Create Account"

#### 2. **System Initialization**
- Enter your age, height (cm), and weight (kg)
- Set target height and weight (optional)
- Input your current exercise capabilities:
  - Example: Push-ups: 20 max reps
  - Example: Running: 10 minutes
- Add more exercises as needed
- Click "Begin My Journey"

#### 3. **Dashboard Overview**
Your dashboard shows:
- **Hunter Profile**: Level, rank, EXP bar, and stats
- **Today's Overview**: Streak, completed quests, body progress
- **Daily Quest Preview**: Quick look at today's mission
- **Recent Achievements**: Your accomplishments

#### 4. **Complete Daily Quests**
- Navigate to "Daily Quest" tab
- Review all exercises in your quest
- Complete each exercise (sets, reps, rest times)
- Check off exercises as you complete them
- Click "Complete Quest" when done
- Celebrate your EXP and possible level up!

#### 5. **Allocate Stat Points**
When you level up:
- Check your dashboard for available stat points
- Click the stat buttons to allocate:
  - **💪 Strength**: Increases physical power
  - **🏃 Endurance**: Improves stamina and cardio
  - **⚡ Agility**: Enhances speed and coordination
  - **❤️ Vitality**: Boosts recovery and health

#### 6. **Set Goals**
- Go to "Goals" tab
- Click "+ Add Goal"
- Choose goal type (Strength, Endurance, Weight, Height, Exercise)
- Enter goal name and target value
- Set optional deadline
- Goals automatically customize your daily quests!

#### 7. **Track Progress**
- Visit "Stats & Progress" tab
- View your EXP progression chart
- Check exercise records and personal bests
- Review quest completion history

#### 8. **Social Features**
- Add friends by searching their username
- Compare levels on the leaderboard
- Choose between Global or Friends-only rankings
- Compete and motivate each other!

---

## 🎯 QUEST SYSTEM EXPLAINED

### How Quests Are Generated

The AI Quest Generator considers:

1. **Your Stats**
   - Current level determines base difficulty
   - Endurance affects number of exercises
   - Strength influences weight/rep targets

2. **Your Goals**
   - Strength goals → More strength exercises
   - Weight goals → More cardio exercises
   - Height goals → Stretching and flexibility
   - Balanced approach if no specific goals

3. **Your History**
   - Personal records from previous workouts
   - Recent activity patterns
   - Exercise variety to prevent boredom

4. **Recovery Needs**
   - Automatic rest days after 6+ consecutive workouts
   - Reduced intensity after high-difficulty quests
   - Active recovery activities on rest days

### Quest Structure

Each quest includes:
- **Title**: Epic name based on difficulty and focus
- **Rank**: E to SS based on difficulty level
- **Exercises**: 3-8 exercises depending on your endurance
- **Sets & Reps**: Progressive targets that increase over time
- **Rest Times**: Calculated based on exercise intensity
- **EXP Reward**: Scales with difficulty
- **Bonus Tasks**: Optional challenges for extra EXP (higher levels)

### Quest Examples

**E-Rank (Beginner)**
```
⚔️ Daily Training: Strength [E Rank]
- Push-ups: 3 sets of 10 reps
- Squats: 3 sets of 15 reps
- Planks: 3 sets of 30 seconds
EXP Reward: 50
```

**A-Rank (Advanced)**
```
🔥 Hunter's Challenge: Power & Endurance [A Rank]
- Pull-ups: 4 sets of 12 reps
- Burpees: 4 sets of 20 reps
- Pistol Squats: 4 sets of 10 reps (each leg)
- Mountain Climbers: 4 sets of 30 seconds
- Russian Twists: 4 sets of 25 reps
Bonus: 🎯 Personal Record Challenge (+250 EXP)
EXP Reward: 500
```

**Rest Day**
```
🛌 Recovery Day: Active Rest
- Light Stretching: 15 minutes
- Walking: 20 minutes
- Meditation: 10 minutes
EXP Reward: 50
```

---

## 💪 TRAINING TIPS

### For Best Results

1. **Be Honest**: Input accurate current capabilities
2. **Stay Consistent**: Complete quests daily
3. **Listen to Your Body**: Take rest days seriously
4. **Progressive Overload**: AI handles this - trust the process
5. **Update Goals**: Adjust goals as you progress
6. **Track Everything**: Log all workouts for better AI predictions
7. **Compete Friendly**: Use leaderboards for motivation
8. **Celebrate Milestones**: Level ups are real achievements!

### Exercise Form Tips

- **Push-ups**: Keep body straight, full range of motion
- **Pull-ups**: Dead hang to chin over bar
- **Squats**: Thighs parallel to ground, knees behind toes
- **Planks**: Straight line from head to heels
- **Burpees**: Chest to ground, full extension on jump

### Recovery Guidelines

- **Sleep**: 7-9 hours nightly
- **Nutrition**: Adequate protein (1.6-2.2g per kg bodyweight)
- **Hydration**: 2-3 liters of water daily
- **Active Recovery**: Light movement on rest days
- **Stretching**: Daily, especially post-workout

---

## 🏆 RANK SYSTEM

Progress through the Hunter ranks:

| Rank | Level Range | Description |
|------|-------------|-------------|
| **E** | 1-4 | Beginner Hunter - Building Foundation |
| **D** | 5-9 | Novice Hunter - Gaining Strength |
| **C** | 10-19 | Intermediate Hunter - Consistent Progress |
| **B** | 20-34 | Advanced Hunter - Strong Capabilities |
| **A** | 35-49 | Elite Hunter - Peak Performance |
| **S** | 50-69 | Master Hunter - Exceptional Power |
| **SS** | 70+ | Legendary Hunter - Transcendent Strength |

---

## 📊 DATABASE SCHEMA

The system uses SQLite with these main tables:

- **users**: Authentication and account data
- **player_stats**: Level, EXP, stats, body measurements
- **exercise_records**: Personal records and exercise history
- **daily_quests**: Generated quests and completion status
- **quest_completions**: Detailed workout logs
- **goals**: User-defined fitness goals
- **friends**: Social connections
- **achievements**: Unlocked achievements

---

## 🔧 TECHNICAL DETAILS

### Backend (Python/Flask)
- **models.py**: Database models and ORM
- **quest_generator.py**: AI quest generation logic
- **app.py**: REST API endpoints and server

### Frontend (HTML/CSS/JavaScript)
- **index.html**: Single-page application structure
- **style.css**: Solo Leveling themed design
- **app.js**: Client-side logic and API calls

### Features
- Session-based authentication
- RESTful API architecture
- Responsive design (mobile-friendly)
- Real-time updates
- Persistent data storage

---

## 🎮 CUSTOMIZATION

### Adjusting Difficulty

Edit `quest_generator.py` to modify:

```python
# Line ~90: Change beginner targets
beginner_targets = {
    'push_ups': 10,  # Increase/decrease starting values
    'pull_ups': 3,
    'squats': 15
}

# Line ~120: Adjust EXP rewards
base_exp = 50  # Change base experience
return int(base_exp * (1 + difficulty * 0.15))  # Modify multiplier

# Line ~140: Change rest day frequency
return rest_scheduled > 0 or workout_days >= 6  # Change 6 to different value
```

### Adding New Exercises

Edit `quest_generator.py`:

```python
# Line ~20: Add to exercise_pool
'upper_body': [
    'push_ups', 'pull_ups', 'dips',
    'your_new_exercise'  # Add here
]
```

### Modifying Stat Growth

Edit `models.py`:

```python
# Line ~180: Change stat points per level
stat_points += 5  # Increase/decrease points gained

# Line ~182: Adjust EXP curve
exp_to_next = int(exp_to_next * 1.15)  # Change multiplier
```

---

## 🐛 TROUBLESHOOTING

### Common Issues

**Server won't start:**
```bash
# Check if port 5000 is in use
lsof -i :5000
# Use a different port
python app.py --port 5001
```

**Database errors:**
```bash
# Delete and recreate database
rm fitness_hunter.db
# Restart server to auto-create
python app.py
```

**Can't login:**
- Clear browser cookies/cache
- Check console for errors (F12)
- Verify username and password

**Quests not generating:**
- Ensure you've completed profile setup
- Check browser console for API errors
- Restart the server

---

## 🚀 FUTURE ENHANCEMENTS

Planned features:
- [ ] Workout video demonstrations
- [ ] Nutrition tracking integration
- [ ] Mobile app (iOS/Android)
- [ ] Wearable device sync (Fitbit, Apple Watch)
- [ ] AI form correction using computer vision
- [ ] Guild/Team features
- [ ] Monthly challenges and events
- [ ] Achievement badges and rewards
- [ ] Export workout data (CSV, PDF)
- [ ] Integration with fitness APIs

---

## 📄 LICENSE

This project is for educational and personal use. Solo Leveling is a trademark of its respective owners.

---

## 🙏 ACKNOWLEDGMENTS

- Inspired by **Solo Leveling** manhwa/anime
- Built with Flask, SQLite, and vanilla JavaScript
- Designed for fitness enthusiasts and gamers

---

## 📧 SUPPORT

For questions or issues:
1. Check this README thoroughly
2. Review the troubleshooting section
3. Check the browser console (F12) for errors
4. Ensure all dependencies are installed

---

## 🎯 START YOUR JOURNEY

**"Arise, Hunter. Your path to strength begins now."**

1. Install dependencies
2. Run the server
3. Create your account
4. Complete your first quest
5. Level up and grow stronger!

Remember: **Consistency beats intensity. Small daily progress compounds into extraordinary results.**

**You have been selected by the System. Will you answer the call?**

⚔️ **GOOD LUCK, HUNTER!** ⚔️
