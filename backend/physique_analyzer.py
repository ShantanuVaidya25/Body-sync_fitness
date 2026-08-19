"""
Body Sync Fitness - AI Physique Analyzer (Google Gemini version)
Analyzes a named character/person OR an uploaded photo and generates a
gamified Quest Log (Dailies, Main Story Quests, Side Quests, Level Up
Milestones) using Google's Gemini API.

Gemini was chosen here because, as of mid-2026, it consistently leads
pure vision-understanding benchmarks (MMMU Pro) among frontier models,
while being notably cheaper and faster than comparable alternatives for
image analysis tasks like this one.

Requires a Gemini API key set as the GEMINI_API_KEY environment
variable. Get one free at: https://aistudio.google.com/apikey

Uses the current "google-genai" SDK (NOT the older, deprecated
"google-generativeai" package).
"""

import os
import mimetypes
from typing import Optional, Dict

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


# Model choice: gemini-2.5-pro is the current stable, GA (non-preview)
# reasoning + vision model as of mid-2026. If you want to try the newer
# Gemini 3 family for stronger vision benchmarks, swap this for
# "gemini-3-pro-preview" -- just be aware preview models can change or
# be deprecated with as little as 2 weeks' notice.
MODEL_NAME = "gemini-flash-latest"


# The exact Game Master prompt template, parameterized by target.
MASTER_PROMPT_TEMPLATE = """Act as a Master Fitness RPG Game Master. I want to achieve the physique of {target}.

First, analyze their physique. Break down their dominant muscle groups, estimated body fat percentage style (lean, bulky, athletic), and the type of training required to look like them.

Second, generate a gamified 'Quest Log' for me to achieve this build. Break this down into:
- Daily Dailies (Habits): Nutrition and lifestyle tasks.
- Main Story Quests (Workout Plan): A weekly training split designed specifically for this physique.
- Side Quests (Optional Challenges): Fun, thematic fitness challenges related to the character/person.
- Level Up Milestones: How I will know I am making progress.

Please ensure the plan is realistic, safe, and progressively overloads over time. Format your response in clean Markdown with clear headers ("## Physique Breakdown", "## Daily Dailies", "## Main Story Quests", "## Side Quests", "## Level Up Milestones") so it can be rendered directly in a fitness app. Keep training advice safe, evidence-based, and appropriate for a general audience (no extreme calorie restriction, no PED references, no unsafe training advice)."""


def enrich_body_type(body_type: str) -> str:
    """
    Enrich raw front-end body type selection into detailed physical baseline for AI.
    
    Mapping Rules:
    - Lean / Skinny / Ectomorph: Low muscle mass, fast metabolism, beginner recovery capacity.
    - Skinny-Fat: Moderate body fat, low underlying muscle mass.
    - Overweight / Endomorph / Heavy: High body fat, low joint tolerance for high-impact movements.
    - Athletic / Mesomorph / Muscular: Existing muscle base, moderate body fat, conditioned.
    """
    if not body_type:
        return "Existing muscle base, moderate body fat, conditioned."
        
    bt = str(body_type).lower().strip().replace(' ', '').replace('-', '_').replace('/', '_')
    
    if 'skinnyfat' in bt or 'skinny_fat' in bt:
        return "Moderate body fat, low underlying muscle mass."
    elif 'ecto' in bt or 'skinny' in bt or 'lean' in bt:
        return "Low muscle mass, fast metabolism, beginner recovery capacity."
    elif 'endo' in bt or 'overweight' in bt or 'heavy' in bt or 'fat' in bt:
        return "High body fat, low joint tolerance for high-impact movements."
    elif 'meso' in bt or 'athletic' in bt or 'muscular' in bt:
        return "Existing muscle base, moderate body fat, conditioned."
    
    return "Existing muscle base, moderate body fat, conditioned."


class PhysiqueAnalyzer:
    """Generates physique-goal based Quest Logs via Google Gemini"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        self.client = None
        if genai and self.api_key:
            self.client = genai.Client(api_key=self.api_key)

    def is_configured(self) -> bool:
        """Check whether the API key / SDK is available"""
        return self.client is not None

    def _build_contents(self, target_name: Optional[str],
                         image_path: Optional[str],
                         current_body_type: Optional[str] = None,
                         injuries: Optional[str] = None,
                         equipment: Optional[str] = None) -> list:
        """Build the multimodal contents list: optional image + text prompt"""
        if target_name:
            target_desc = target_name
        else:
            target_desc = "the person shown in the attached image"

        prompt_text = MASTER_PROMPT_TEMPLATE.format(target=target_desc)

        if current_body_type:
            enriched_baseline = enrich_body_type(current_body_type)
            prompt_text += f"\n\nCRITICAL ADAPTIVE CONTEXT: The client's current physical baseline is: **{enriched_baseline}** ({current_body_type.upper()}). Please tailor the exercise selection, volume, and cardio recommendations to optimize results for this specific baseline as they transform into {target_desc}."

        if injuries and str(injuries).lower() != 'none':
            prompt_text += f"\n\nINJURIES / MEDICAL LIMITATIONS: **{injuries}**. You MUST avoid any exercises that aggravate these conditions (e.g. no heavy spinal loading for back pain, no heavy knee-bending for knee pain). Prescribe 100% safe, joint-friendly alternative movements."

        if equipment:
            prompt_text += f"\n\nAVAILABLE EQUIPMENT ACCESS: **{equipment}**. Restrict all prescribed exercises strictly to what can be performed with this equipment access."

        contents = []

        if image_path and os.path.exists(image_path):
            mime_type, _ = mimetypes.guess_type(image_path)
            if not mime_type or not mime_type.startswith('image/'):
                mime_type = 'image/jpeg'

            with open(image_path, 'rb') as f:
                image_bytes = f.read()

            contents.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))

        contents.append(prompt_text)
        return contents

    def generate_quest_log(self, target_name: Optional[str] = None,
                          image_path: Optional[str] = None,
                          current_body_type: Optional[str] = None,
                          injuries: Optional[str] = None,
                          equipment: Optional[str] = None) -> Dict:
        """
        Generate a Quest Log by analyzing a named character/person or an
        uploaded photo. Exactly one of target_name / image_path should be
        provided (an image takes priority if both are given).
        """
        if not target_name and not image_path:
            return {
                'success': False,
                'error': 'Provide either a target character/person name OR upload a reference image.'
            }

        if not self.is_configured():
            return {
                'success': False,
                'error': 'Gemini API key is not configured. Go to Settings to add your key.'
            }

        try:
            contents = self._build_contents(
                target_name=target_name,
                image_path=image_path,
                current_body_type=current_body_type,
                injuries=injuries,
                equipment=equipment
            )

            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=contents
            )

            quest_log_markdown = response.text

            return {
                'success': True,
                'target_name': target_name or 'Uploaded Photo Subject',
                'source_type': 'image' if image_path else 'text',
                'quest_log_markdown': quest_log_markdown
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'AI generation failed: {str(e)}'
            }

    def extract_structured_weekly_plan(self, quest_log_markdown: str, target_name: Optional[str] = None) -> Dict:
        """
        Take the freeform Quest Log markdown and convert the "Main Story Quests"
        weekly training split specifically into structured JSON data. Uses Gemini AI
        when configured, and falls back to a deterministic markdown parser to guarantee
        a 7-day plan is always available.
        """
        if self.is_configured():
            main_quests_section = extract_section(quest_log_markdown, 'Main Story Quests')
            if not main_quests_section:
                main_quests_section = quest_log_markdown

            structuring_prompt = f"""Convert the following weekly workout split into STRICT JSON only -- no markdown fences, no commentary, no explanation, just the raw JSON object.

Weekly split to convert:
---
{main_quests_section}
---

Return JSON matching EXACTLY this schema (all 7 days, Monday through Sunday, day_of_week 0=Monday through 6=Sunday):

{{
  "days": [
    {{
      "day_of_week": 0,
      "day_label": "Monday",
      "focus": "short label like 'Push - Chest, Shoulders, Triceps' or 'Rest Day'",
      "is_rest": false,
      "exercises": [
        {{
          "name": "Exercise Name",
          "sets": 4,
          "reps": "8-10",
          "rest_seconds": 90,
          "notes": "brief form or intensity cue"
        }}
      ]
    }}
  ]
}}

If the source plan doesn't specify all 7 days explicitly, infer reasonable rest/active days consistent with a realistic weekly structure. Rest days should have "is_rest": true and an empty exercises array. Output ONLY the JSON object, nothing else."""

            try:
                response = self.client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[structuring_prompt]
                )

                raw_text = response.text.strip()

                if raw_text.startswith('```'):
                    raw_text = raw_text.split('```')[1]
                    if raw_text.startswith('json'):
                        raw_text = raw_text[4:]
                    raw_text = raw_text.strip()

                import json
                parsed = json.loads(raw_text)

                days = parsed.get('days', [])
                if len(days) == 7:
                    return {'success': True, 'days': days}
            except Exception as e:
                print(f"⚠️  Gemini JSON structuring failed ({e}), falling back to deterministic parser.")

        # Deterministic markdown parsing fallback (guarantees a 7-day split is always built)
        fallback_days = parse_weekly_plan_from_markdown(quest_log_markdown, target_name)
        return {'success': True, 'days': fallback_days, 'fallback_used': True}

    def adapt_physique_quest_to_equipment(self, user_id: int, active_quest: Dict,
                                          new_equipment: str, user_stats: Dict, db) -> Dict:
        """
        Adapts the active character build goal (physique quest) and its structured 7-day
        training split on the spot to match the newly selected equipment / location access.
        """
        from models import WeeklyPlanManager
        target_name = active_quest.get('target_name') or 'Custom Build'
        quest_id = active_quest['id']
        current_body_type = user_stats.get('body_type', 'mesomorph')
        injuries = user_stats.get('injuries', 'None')
        
        adapted_markdown = None
        structured_days = None
        
        # 1. Try AI Generation if configured
        if self.is_configured():
            try:
                res = self.generate_quest_log(
                    target_name=target_name,
                    image_path=None,
                    current_body_type=current_body_type,
                    injuries=injuries,
                    equipment=new_equipment
                )
                if res.get('success'):
                    adapted_markdown = res['quest_log_markdown']
                    weekly_res = self.extract_structured_weekly_plan(adapted_markdown, target_name=target_name)
                    if weekly_res.get('success'):
                        structured_days = weekly_res.get('days')
            except Exception as e:
                print(f"⚠️  AI adaptation for {target_name} to {new_equipment} failed ({e}), using deterministic character adapter.")

        # 2. Deterministic character adapter fallback
        if not structured_days:
            adapted_markdown, structured_days = generate_character_equipment_split(
                target_name, new_equipment, current_body_type, injuries
            )

        # 3. Save to database
        try:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE physique_quests SET quest_log_markdown = ? WHERE id = ? AND user_id = ?',
                           (adapted_markdown, quest_id, user_id))
            conn.commit()
            conn.close()

            weekly_plan_mgr = WeeklyPlanManager(db)
            weekly_plan_mgr.save_weekly_plan(user_id, quest_id, structured_days)
        except Exception as ex_db:
            print(f"⚠️  Error saving adapted weekly plan: {ex_db}")

        return {
            'success': True,
            'target_name': target_name,
            'equipment': new_equipment,
            'days': structured_days,
            'quest_log_markdown': adapted_markdown
        }

    def generate_weekly_workout_json(self, 
                                     body_type: str, 
                                     days_per_week: int = 5, 
                                     equipment: str = "Full Commercial Gym", 
                                     injuries: str = "None") -> Dict:
        """
        Generate a weekly workout plan strictly following the Backend Fitness Programming Engine schema.
        """
        import json
        enriched_baseline = enrich_body_type(body_type)
        
        prompt = f"""You are a backend fitness programming engine acting as an elite strength and conditioning coach. Your objective is to generate a highly optimized, physiologically safe, and effective weekly workout plan for a user based on their specific physical baseline and training constraints.

USER PROFILE AND INPUT VARIABLES:
- Physical Baseline Profile: {enriched_baseline}
- Training Frequency: {days_per_week} days per week
- Available Equipment: {equipment}
- Known Injuries/Limitations: {injuries}

PROGRAMMING RULES:
1. Baseline Alignment: You must tailor the exercise selection strictly to the user's physical baseline and equipment access. If the equipment is Home / Bodyweight, only prescribe bodyweight calisthenics. If Dumbbells, prescribe dumbbell movements. If Full Gym, prescribe gym equipment.
2. Volume and Intensity: Modulate the set/rep schemes to match the user's implied recovery capacity.
3. Realistic Progression: Every exercise must include actionable rest periods and rep ranges.

STRICT OUTPUT FORMATTING:
You are a data API. You must output the requested workout plan STRICTLY as a valid JSON object. Do not output any conversational text, markdown outside of JSON, or disclaimers.

The JSON payload must follow this exact structure:
{{
  "program_overview": "A 1-sentence summary of the program focus based on the body type",
  "weekly_schedule": [
    {{
      "day_number": 1,
      "muscle_focus": "e.g., Push / Pull / Legs / Full Body / Rest",
      "routine": [
        {{
          "exercise_name": "Exact name of movement",
          "sets": 3,
          "reps": "8-12",
          "rest_seconds": 90,
          "form_cue": "1 short sentence on form or alternative modification"
        }}
      ]
    }}
  ]
}}"""

        if not self.is_configured():
            fallback_program = self._generate_fallback_json_routine(body_type, enriched_baseline, days_per_week, equipment, injuries)
            return {
                'success': True,
                'body_type': body_type,
                'enriched_baseline': enriched_baseline,
                'days_per_week': days_per_week,
                'equipment': equipment,
                'injuries': injuries,
                'program': fallback_program,
                'is_fallback': True
            }

        try:
            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=[prompt]
            )
            raw_text = response.text or ""
            clean_text = raw_text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            clean_text = clean_text.strip()
            
            program_json = json.loads(clean_text)
            return {
                'success': True,
                'body_type': body_type,
                'enriched_baseline': enriched_baseline,
                'days_per_week': days_per_week,
                'equipment': equipment,
                'injuries': injuries,
                'program': program_json,
                'is_fallback': False
            }
        except Exception as e:
            fallback_program = self._generate_fallback_json_routine(body_type, enriched_baseline, days_per_week, equipment, injuries)
            return {
                'success': True,
                'body_type': body_type,
                'enriched_baseline': enriched_baseline,
                'days_per_week': days_per_week,
                'equipment': equipment,
                'injuries': injuries,
                'program': fallback_program,
                'is_fallback': True,
                'notice': f'AI generation notice: {str(e)}'
            }

    def _generate_fallback_json_routine(self, body_type: str, enriched_baseline: str, days_per_week: int, equipment: str, injuries: str) -> dict:
        """
        Generate deterministic fallback program adhering strictly to equipment access and body type.
        """
        eq = (equipment or '').lower()
        is_db = 'dumbbell' in eq
        is_home = not is_db and ('home' in eq or 'bodyweight' in eq or 'calisthenics' in eq or 'none' in eq)
        
        if is_home:
            overview = f"Home Calisthenics Routine tailored for {body_type.upper()} build with zero equipment requirements."
            schedule = [
                {
                    "day_number": 1,
                    "muscle_focus": "Upper Body Push & Core (Home)",
                    "routine": [
                        {"exercise_name": "Standard / Diamond Push-Ups", "sets": 4, "reps": "12-15", "rest_seconds": 60, "form_cue": "Keep core tight and elbow tucked at 45 degrees."},
                        {"exercise_name": "Pike Push-Ups (Shoulders)", "sets": 3, "reps": "8-10", "rest_seconds": 60, "form_cue": "Elevate hips high in V-shape and lower crown of head forward."},
                        {"exercise_name": "Chair / Bed Edge Dips", "sets": 3, "reps": "12-15", "rest_seconds": 60, "form_cue": "Lower until 90 degree elbow bend, press up locking triceps."},
                        {"exercise_name": "Plank with Shoulder Taps", "sets": 3, "reps": "20 taps", "rest_seconds": 45, "form_cue": "Brace core to prevent hip rotation."}
                    ]
                },
                {
                    "day_number": 2,
                    "muscle_focus": "Lower Body Power & Legs (Home)",
                    "routine": [
                        {"exercise_name": "Tempo Bodyweight Squats", "sets": 4, "reps": "20", "rest_seconds": 60, "form_cue": "3 seconds eccentric descent with full depth below parallel."},
                        {"exercise_name": "Bulgarian Split Squats (Couch/Chair)", "sets": 3, "reps": "12 per leg", "rest_seconds": 60, "form_cue": "Drive through front heel, keep front knee stacked."},
                        {"exercise_name": "Single-Leg Glute Bridges", "sets": 3, "reps": "15 per leg", "rest_seconds": 45, "form_cue": "Squeeze glute at top for 2 seconds without lumbar arch."},
                        {"exercise_name": "Calf Raises on Step Edge", "sets": 4, "reps": "25", "rest_seconds": 45, "form_cue": "Full ankle stretch at bottom, explosive rise onto toes."}
                    ]
                },
                {
                    "day_number": 3,
                    "muscle_focus": "Back Pull & Conditioning (Home)",
                    "routine": [
                        {"exercise_name": "Doorframe / Towel Inverted Rows", "sets": 4, "reps": "12-15", "rest_seconds": 60, "form_cue": "Squeeze shoulder blades together at chest peak."},
                        {"exercise_name": "Superman Back Holds", "sets": 3, "reps": "12 (3s hold)", "rest_seconds": 45, "form_cue": "Lift chest and thighs engaging spinal erectors."},
                        {"exercise_name": "Mountain Climbers & Burpees Finisher", "sets": 3, "reps": "30 sec work", "rest_seconds": 60, "form_cue": "High intensity aerobic output."}
                    ]
                },
                {
                    "day_number": 4,
                    "muscle_focus": "Active Recovery & Mobility",
                    "routine": [
                        {"exercise_name": "Full Body Mobility & Yoga Flow", "sets": 1, "reps": "25 mins", "rest_seconds": 0, "form_cue": "Breathe deeply into tight hamstrings and hips."}
                    ]
                },
                {
                    "day_number": 5,
                    "muscle_focus": "Full Body Calisthenics Mastery",
                    "routine": [
                        {"exercise_name": "Decline Push-Ups (Feet Elevated)", "sets": 3, "reps": "12", "rest_seconds": 60, "form_cue": "Target upper clavicular chest fibres."},
                        {"exercise_name": "Jump Squats (Explosive)", "sets": 4, "reps": "12", "rest_seconds": 60, "form_cue": "Land softly absorbing impact with bent knees."},
                        {"exercise_name": "Hollow Body Holds & Russian Twists", "sets": 3, "reps": "45s / 20 reps", "rest_seconds": 45, "form_cue": "Keep lower back pressed flat into floor."}
                    ]
                }
            ]
        elif is_db:
            overview = f"Dumbbell & Home Gym Routine focused on progressive overload for {body_type.upper()} build."
            schedule = [
                {
                    "day_number": 1,
                    "muscle_focus": "Dumbbell Push (Chest, Shoulders, Triceps)",
                    "routine": [
                        {"exercise_name": "Flat / Floor Dumbbell Press", "sets": 4, "reps": "10-12", "rest_seconds": 75, "form_cue": "Control descent and push weights together over sternum."},
                        {"exercise_name": "Standing Dumbbell Shoulder Press", "sets": 3, "reps": "10", "rest_seconds": 75, "form_cue": "Press overhead without arching lower spine."},
                        {"exercise_name": "Dumbbell Lateral Raises", "sets": 3, "reps": "12-15", "rest_seconds": 60, "form_cue": "Lead with elbows for optimal medial delt activation."},
                        {"exercise_name": "Overhead Dumbbell Tricep Extension", "sets": 3, "reps": "12", "rest_seconds": 60, "form_cue": "Keep elbows tucked forward near ears."}
                    ]
                },
                {
                    "day_number": 2,
                    "muscle_focus": "Dumbbell Pull (Back, Biceps, Rear Delts)",
                    "routine": [
                        {"exercise_name": "Bent-over Dumbbell Rows", "sets": 4, "reps": "10-12", "rest_seconds": 75, "form_cue": "Pull dumbbells back toward hips squeezing lats."},
                        {"exercise_name": "Dumbbell Bicep Curls", "sets": 3, "reps": "10-12", "rest_seconds": 60, "form_cue": "Full supination at top of curl."},
                        {"exercise_name": "Dumbbell Hammer Curls", "sets": 3, "reps": "12", "rest_seconds": 60, "form_cue": "Neutral grip to build brachialis and forearm thickness."},
                        {"exercise_name": "Dumbbell Shrugs & Rear Delt Flyes", "sets": 3, "reps": "15", "rest_seconds": 60, "form_cue": "Squeeze upper traps and upper back at top."}
                    ]
                },
                {
                    "day_number": 3,
                    "muscle_focus": "Dumbbell Legs & Core",
                    "routine": [
                        {"exercise_name": "Dumbbell Goblet Squats", "sets": 4, "reps": "10-12", "rest_seconds": 90, "form_cue": "Hold dumbbell vertically at chest, break parallel."},
                        {"exercise_name": "Dumbbell Romanian Deadlifts", "sets": 4, "reps": "10", "rest_seconds": 90, "form_cue": "Hinge at hips feeling deep hamstring stretch."},
                        {"exercise_name": "Dumbbell Walking Lunges", "sets": 3, "reps": "10 per leg", "rest_seconds": 75, "form_cue": "Step forward with tall chest, drive through heel."},
                        {"exercise_name": "Dumbbell Russian Twists", "sets": 3, "reps": "20", "rest_seconds": 45, "form_cue": "Rotate torso holding light dumbbell."}
                    ]
                },
                {
                    "day_number": 4,
                    "muscle_focus": "Active Recovery & Mobility",
                    "routine": [
                        {"exercise_name": "Active Walk & Full Body Stretching", "sets": 1, "reps": "30 mins", "rest_seconds": 0, "form_cue": "Enhance blood flow and muscle repair."}
                    ]
                },
                {
                    "day_number": 5,
                    "muscle_focus": "Dumbbell Conditioning & Thrusters",
                    "routine": [
                        {"exercise_name": "Dumbbell Thrusters (Squat to Press)", "sets": 4, "reps": "10", "rest_seconds": 75, "form_cue": "Explode upward out of squat into overhead press."},
                        {"exercise_name": "Dumbbell Renegade Rows", "sets": 3, "reps": "8 per arm", "rest_seconds": 60, "form_cue": "Maintain rigid plank while rowing dumbbell to ribcage."},
                        {"exercise_name": "Dumbbell Farmer's Carries", "sets": 3, "reps": "45 sec carry", "rest_seconds": 60, "form_cue": "Brace core and walk with perfect upright posture."}
                    ]
                }
            ]
        else:
            # Full Commercial Gym
            overview = f"Commercial Gym Compound Program maximizing hypertrophy and strength for {body_type.upper()} build."
            schedule = [
                {
                    "day_number": 1,
                    "muscle_focus": "Push (Chest, Shoulders, Triceps)",
                    "routine": [
                        {"exercise_name": "Barbell Bench Press", "sets": 4, "reps": "8-10", "rest_seconds": 90, "form_cue": "Retract scapulae and press bar with controlled tempo."},
                        {"exercise_name": "Incline Dumbbell Press", "sets": 3, "reps": "10-12", "rest_seconds": 75, "form_cue": "Stretch upper chest at bottom."},
                        {"exercise_name": "Cable Lateral Raises", "sets": 3, "reps": "12-15", "rest_seconds": 60, "form_cue": "Continuous tension throughout movement."},
                        {"exercise_name": "Tricep Rope Pushdowns", "sets": 3, "reps": "12", "rest_seconds": 60, "form_cue": "Flare rope apart at bottom lockout."}
                    ]
                },
                {
                    "day_number": 2,
                    "muscle_focus": "Pull (Back, Biceps, Rear Delts)",
                    "routine": [
                        {"exercise_name": "Barbell Deadlifts / Lat Pulldowns", "sets": 4, "reps": "6-8", "rest_seconds": 120, "form_cue": "Drive floor away, lock out hips at top."},
                        {"exercise_name": "Seated Cable Rows", "sets": 4, "reps": "10", "rest_seconds": 75, "form_cue": "Pull to lower abdomen squeezing rhomboids."},
                        {"exercise_name": "EZ-Bar / Cable Bicep Curls", "sets": 3, "reps": "10-12", "rest_seconds": 60, "form_cue": "Pin elbows to ribs and isolate biceps."},
                        {"exercise_name": "Face Pulls", "sets": 3, "reps": "15", "rest_seconds": 60, "form_cue": "Pull rope to forehead for rear delt health."}
                    ]
                },
                {
                    "day_number": 3,
                    "muscle_focus": "Legs & Core Power",
                    "routine": [
                        {"exercise_name": "Barbell Back Squats", "sets": 4, "reps": "8-10", "rest_seconds": 90, "form_cue": "Chest up, break parallel with knee tracking."},
                        {"exercise_name": "Leg Press Machine", "sets": 3, "reps": "12", "rest_seconds": 75, "form_cue": "Control eccentric phase without bouncing."},
                        {"exercise_name": "Lying Leg Curls / RDLs", "sets": 3, "reps": "10-12", "rest_seconds": 75, "form_cue": "Direct hamstring overload."},
                        {"exercise_name": "Hanging Leg Raises", "sets": 3, "reps": "12", "rest_seconds": 60, "form_cue": "Curl pelvis upward to engage lower abdominals."}
                    ]
                },
                {
                    "day_number": 4,
                    "muscle_focus": "Active Recovery & Cardio",
                    "routine": [
                        {"exercise_name": "Incline Treadmill Walk / Rowing", "sets": 1, "reps": "30 mins", "rest_seconds": 0, "form_cue": "Steady-state aerobic recovery."}
                    ]
                },
                {
                    "day_number": 5,
                    "muscle_focus": "Upper Body Hypertrophy & Arms",
                    "routine": [
                        {"exercise_name": "Overhead Barbell Press", "sets": 4, "reps": "8", "rest_seconds": 90, "form_cue": "Tight glutes and core throughout press."},
                        {"exercise_name": "Chest Fly Machine (Pec Deck)", "sets": 3, "reps": "12-15", "rest_seconds": 60, "form_cue": "Squeeze pectorals for 1 second peak hold."},
                        {"exercise_name": "Dips (Bodyweight or Weighted)", "sets": 3, "reps": "10-12", "rest_seconds": 75, "form_cue": "Lean forward slightly for chest focus."}
                    ]
                }
            ]

        return {
            "program_overview": overview,
            "weekly_schedule": schedule
        }


def extract_section(markdown_text: str, header: str) -> str:
    """Utility to pull one '## Header' section out of the generated markdown"""
    lines = markdown_text.split('\n')
    capturing = False
    section_lines = []

    for line in lines:
        if line.strip().startswith('##'):
            if header.lower() in line.lower():
                capturing = True
                continue
            elif capturing:
                break
        if capturing:
            section_lines.append(line)

    return '\n'.join(section_lines).strip()


def parse_weekly_plan_from_markdown(quest_log_markdown: str, target_name: Optional[str] = None, equipment: str = "Full Commercial Gym") -> list:
    """
    Fallback parser that converts markdown text into a structured 7-day plan
    (Monday through Sunday) respecting the player's equipment access.
    """
    import re
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    main_section = extract_section(quest_log_markdown, 'Main Story Quests')
    if not main_section:
        main_section = quest_log_markdown
        
    lines = [line.strip() for line in main_section.split('\n') if line.strip()]
    
    day_blocks = []
    current_day = None
    
    for line in lines:
        day_match = re.search(r'(?:Day\s*(\d)|(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday))', line, re.IGNORECASE)
        if (line.startswith('#') or line.startswith('-') or line.startswith('*') or line.startswith('**')) and day_match:
            if current_day:
                day_blocks.append(current_day)
            current_day = {'header': line, 'lines': []}
        elif current_day:
            current_day['lines'].append(line)
            
    if current_day:
        day_blocks.append(current_day)
        
    t_name = target_name or "Hunter"
    days = []
    
    if day_blocks:
        for idx in range(7):
            day_name = day_names[idx]
            if idx < len(day_blocks):
                block = day_blocks[idx]
                header = block['header']
                focus_clean = re.sub(r'^[#\-\*\s\d\:\(\)\*]+', '', header).strip()
                if not focus_clean:
                    focus_clean = f"{t_name} Training Day {idx+1}"
                
                is_rest = 'rest' in focus_clean.lower() or 'recovery' in focus_clean.lower()
                
                exercises = []
                if not is_rest:
                    for ex_line in block['lines']:
                        cleaned_ex = re.sub(r'^[\-\*\d\.\s]+', '', ex_line).strip()
                        if cleaned_ex and len(cleaned_ex) > 3 and not cleaned_ex.startswith('#'):
                            sets_match = re.search(r'(\d+)\s*sets', cleaned_ex, re.IGNORECASE)
                            reps_match = re.search(r'(\d+(?:-\d+)?)\s*(?:reps|seconds|sec|min)?', cleaned_ex, re.IGNORECASE)
                            
                            ex_name = cleaned_ex.split(':')[0].split('-')[0].strip()
                            sets_val = int(sets_match.group(1)) if sets_match else 3
                            reps_val = reps_match.group(1) if reps_match else "10-12"
                            
                            exercises.append({
                                'name': ex_name,
                                'sets': sets_val,
                                'reps': reps_val,
                                'rest_seconds': 60,
                                'notes': f"Part of {t_name}'s Main Story Quest"
                            })
                    
                    if not exercises:
                        exercises = [
                            {'name': f'{t_name} Power Protocol', 'sets': 4, 'reps': '12-15', 'rest_seconds': 60, 'notes': 'Focus on explosive execution'},
                            {'name': f'{t_name} Core Mastery', 'sets': 3, 'reps': '15-20', 'rest_seconds': 45, 'notes': 'Core stabilization'},
                            {'name': f'{t_name} Conditioning Circuit', 'sets': 3, 'reps': '10', 'rest_seconds': 60, 'notes': 'Form and control'}
                        ]
                
                days.append({
                    'day_of_week': idx,
                    'day_label': day_name,
                    'focus': focus_clean,
                    'is_rest': is_rest,
                    'exercises': exercises if not is_rest else []
                })
            else:
                is_rest = (idx == 6)
                days.append({
                    'day_of_week': idx,
                    'day_label': day_name,
                    'focus': 'Rest & Recovery' if is_rest else f'{t_name} Workout Day {idx+1}',
                    'is_rest': is_rest,
                    'exercises': [] if is_rest else [
                        {'name': f'{t_name} Training Circuit', 'sets': 4, 'reps': '12', 'rest_seconds': 60, 'notes': 'Build strength and stamina'}
                    ]
                })
    else:
        # Generate default split directly matching target character and equipment
        _, days = generate_character_equipment_split(t_name, equipment)
            
    return days


def generate_character_equipment_split(target_name: str, equipment: str, body_type: str = "mesomorph", injuries: str = "None") -> tuple:
    """
    Generates an authentic character training split and gamified Quest Log markdown
    adapted strictly to the specified equipment access (Home, Dumbbells, Gym).
    """
    t_name = target_name or "Shadow Hunter"
    t_lower = t_name.lower()
    eq = (equipment or "Full Commercial Gym").lower()
    is_db = 'dumbbell' in eq
    is_home = not is_db and ('home' in eq or 'bodyweight' in eq or 'calisthenics' in eq or 'none' in eq)
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    if 'jin-woo' in t_lower or 'jinwoo' in t_lower or 'sung' in t_lower:
        if is_home:
            split_days = [
                {'focus': f"⚔️ {t_name}: Shadow Daily Trial (Push & Core)", 'is_rest': False, 'exercises': [
                    {'name': 'Diamond Push-ups', 'sets': 4, 'reps': '15', 'rest_seconds': 60, 'notes': 'Tricep and chest power for dagger thrusts'},
                    {'name': 'Decline Push-ups', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Upper chest development'},
                    {'name': 'Chair / Bench Dips', 'sets': 4, 'reps': '15', 'rest_seconds': 60, 'notes': 'Tricep power lockout'},
                    {'name': 'Hollow Body Hold', 'sets': 3, 'reps': '45 sec', 'rest_seconds': 45, 'notes': 'Shadow Monarch core brace'}
                ]},
                {'focus': f"⚔️ {t_name}: Monarch Agility & Back", 'is_rest': False, 'exercises': [
                    {'name': 'Doorframe / Towel Inverted Rows', 'sets': 4, 'reps': '15', 'rest_seconds': 60, 'notes': 'Lat development with zero gear'},
                    {'name': 'Superman Back Extensions', 'sets': 3, 'reps': '15', 'rest_seconds': 45, 'notes': 'Spinal erector and posterior chain'},
                    {'name': 'Mountain Climber Sprints', 'sets': 4, 'reps': '30 sec', 'rest_seconds': 45, 'notes': 'Speed and quick reflexes'},
                    {'name': 'Bicycle Crunches', 'sets': 3, 'reps': '25', 'rest_seconds': 45, 'notes': 'Rotational core power'}
                ]},
                {'focus': f"🛌 {t_name}: Shadow Realm Rest & Recovery", 'is_rest': True, 'exercises': []},
                {'focus': f"⚔️ {t_name}: Ruler's Hand Leg Power", 'is_rest': False, 'exercises': [
                    {'name': 'Explosive Jump Squats', 'sets': 4, 'reps': '15', 'rest_seconds': 60, 'notes': 'Explosive leap and landing deceleration'},
                    {'name': 'Bulgarian Split Squats (Chair)', 'sets': 3, 'reps': '12 per leg', 'rest_seconds': 60, 'notes': 'Unilateral quad balance'},
                    {'name': 'Single-Leg Calf Raises', 'sets': 4, 'reps': '20', 'rest_seconds': 45, 'notes': 'Sprint springiness'},
                    {'name': 'Wall Sits', 'sets': 3, 'reps': '60 sec', 'notes': 'Isometric leg endurance'}
                ]},
                {'focus': f"⚔️ {t_name}: 100x Daily Quest Trial", 'is_rest': False, 'exercises': [
                    {'name': 'Standard Push-ups', 'sets': 4, 'reps': '25', 'rest_seconds': 60, 'notes': 'System daily quest target (100 pushups)'},
                    {'name': 'Bodyweight Squats', 'sets': 4, 'reps': '25', 'rest_seconds': 60, 'notes': 'System daily quest target (100 squats)'},
                    {'name': 'Abdominal Crunches', 'sets': 4, 'reps': '25', 'rest_seconds': 45, 'notes': 'System daily quest target (100 situps)'},
                    {'name': 'High-Knee Sprint in Place', 'sets': 4, 'reps': '60 sec', 'rest_seconds': 60, 'notes': '10km run conditioning equivalent'}
                ]},
                {'focus': f"⚔️ {t_name}: Dungeon Boss Trial", 'is_rest': False, 'exercises': [
                    {'name': 'Archer Push-ups', 'sets': 3, 'reps': '8 per arm', 'rest_seconds': 75, 'notes': 'Single-arm strength balance'},
                    {'name': 'Pike Push-ups', 'sets': 3, 'reps': '10', 'rest_seconds': 60, 'notes': 'Vertical pressing deltoid power'},
                    {'name': 'Burpees', 'sets': 4, 'reps': '12', 'rest_seconds': 60, 'notes': 'Full-body combat endurance'},
                    {'name': 'Plank Hold', 'sets': 3, 'reps': '60 sec', 'rest_seconds': 45, 'notes': 'Unbreakable core shield'}
                ]},
                {'focus': f"🛌 {t_name}: System Full Recovery", 'is_rest': True, 'exercises': []}
            ]
        elif is_db:
            split_days = [
                {'focus': f"⚔️ {t_name}: Dumbbell Chest & Delts", 'is_rest': False, 'exercises': [
                    {'name': 'Dumbbell Floor Press', 'sets': 4, 'reps': '10-12', 'rest_seconds': 75, 'notes': 'Heavy dagger push strength'},
                    {'name': 'Standing Dumbbell Shoulder Press', 'sets': 3, 'reps': '10', 'rest_seconds': 75, 'notes': 'Shoulder deltoid mass'},
                    {'name': 'Dumbbell Lateral Raises', 'sets': 3, 'reps': '15', 'rest_seconds': 60, 'notes': '3D hunter shoulder width'},
                    {'name': 'Dumbbell Russian Twists', 'sets': 3, 'reps': '20', 'rest_seconds': 45, 'notes': 'Core rotation stability'}
                ]},
                {'focus': f"⚔️ {t_name}: Shadow Extract Back Pull", 'is_rest': False, 'exercises': [
                    {'name': 'Bent-over Dumbbell Rows', 'sets': 4, 'reps': '10', 'rest_seconds': 75, 'notes': 'Lats and upper back thickness'},
                    {'name': 'Dumbbell Romanian Deadlifts', 'sets': 4, 'reps': '10', 'rest_seconds': 90, 'notes': 'Hamstring and glute hinge'},
                    {'name': 'Dumbbell Hammer Curls', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Forearm and bicep grip power'},
                    {'name': 'Plank with Dumbbell Pull-Through', 'sets': 3, 'reps': '12', 'rest_seconds': 45, 'notes': 'Anti-rotational core'}
                ]},
                {'focus': f"🛌 {t_name}: Rest & Stat Point Allocation", 'is_rest': True, 'exercises': []},
                {'focus': f"⚔️ {t_name}: Dumbbell Leg Domination", 'is_rest': False, 'exercises': [
                    {'name': 'Dumbbell Goblet Squats', 'sets': 4, 'reps': '12', 'rest_seconds': 90, 'notes': 'Deep quad power'},
                    {'name': 'Dumbbell Walking Lunges', 'sets': 3, 'reps': '10 per leg', 'rest_seconds': 75, 'notes': 'Single-leg balance and speed'},
                    {'name': 'Dumbbell Calf Raises', 'sets': 4, 'reps': '20', 'rest_seconds': 45, 'notes': 'Explosive ankle drive'},
                    {'name': 'Dumbbell Romanian Deadlifts', 'sets': 3, 'reps': '10', 'rest_seconds': 75, 'notes': 'Posterior chain reinforcement'}
                ]},
                {'focus': f"⚔️ {t_name}: Monarch Conditioning", 'is_rest': False, 'exercises': [
                    {'name': 'Dumbbell Thrusters', 'sets': 4, 'reps': '10', 'rest_seconds': 75, 'notes': 'Full body explosive power'},
                    {'name': 'Dumbbell Renegade Rows', 'sets': 3, 'reps': '8 per arm', 'rest_seconds': 60, 'notes': 'Core and back synergy'},
                    {'name': 'Push-ups to Floor', 'sets': 3, 'reps': '20', 'rest_seconds': 60, 'notes': 'Chest burnout'},
                    {'name': 'Dumbbell Swings', 'sets': 3, 'reps': '15', 'rest_seconds': 60, 'notes': 'Hip snap stamina'}
                ]},
                {'focus': f"⚔️ {t_name}: Dungeon Boss Finisher", 'is_rest': False, 'exercises': [
                    {'name': 'Dumbbell Incline/Floor Press', 'sets': 3, 'reps': '12', 'rest_seconds': 75, 'notes': 'Upper chest focus'},
                    {'name': 'Dumbbell Bicep Curls', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Arm hypertrophy'},
                    {'name': 'Jump Squats', 'sets': 3, 'reps': '15', 'rest_seconds': 60, 'notes': 'Fast-twitch power'},
                    {'name': 'Hollow Body Hold', 'sets': 3, 'reps': '45 sec', 'rest_seconds': 45, 'notes': 'Core endurance'}
                ]},
                {'focus': f"🛌 {t_name}: Full Recovery Rest Day", 'is_rest': True, 'exercises': []}
            ]
        else:
            # Full Commercial Gym
            split_days = [
                {'focus': f"⚔️ {t_name}: Monarch Heavy Push (Chest & Shoulders)", 'is_rest': False, 'exercises': [
                    {'name': 'Barbell Bench Press', 'sets': 4, 'reps': '8-10', 'rest_seconds': 90, 'notes': 'Heavy compound chest drive'},
                    {'name': 'Overhead Barbell Press', 'sets': 4, 'reps': '8', 'rest_seconds': 90, 'notes': 'Deltoid shoulder mass'},
                    {'name': 'Incline Dumbbell Press', 'sets': 3, 'reps': '10-12', 'rest_seconds': 75, 'notes': 'Clavicular chest definition'},
                    {'name': 'Cable Lateral Raises', 'sets': 3, 'reps': '15', 'rest_seconds': 60, 'notes': '3D side delts'}
                ]},
                {'focus': f"⚔️ {t_name}: Shadow Pull (Lats & Deadlifts)", 'is_rest': False, 'exercises': [
                    {'name': 'Barbell Deadlifts', 'sets': 4, 'reps': '6', 'rest_seconds': 120, 'notes': 'Total posterior chain power'},
                    {'name': 'Lat Pulldowns', 'sets': 4, 'reps': '10', 'rest_seconds': 75, 'notes': 'Latissimus dorsi V-taper'},
                    {'name': 'Seated Cable Rows', 'sets': 3, 'reps': '10-12', 'rest_seconds': 75, 'notes': 'Rhomboid and mid-back density'},
                    {'name': 'Cable Bicep Curls', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Bicep peak contraction'}
                ]},
                {'focus': f"🛌 {t_name}: Shadow Realm Rest", 'is_rest': True, 'exercises': []},
                {'focus': f"⚔️ {t_name}: Monarch Leg Power (Squats)", 'is_rest': False, 'exercises': [
                    {'name': 'Barbell Back Squats', 'sets': 4, 'reps': '8', 'rest_seconds': 120, 'notes': 'Heavy quad and glute strength'},
                    {'name': 'Leg Press', 'sets': 3, 'reps': '12', 'rest_seconds': 90, 'notes': 'Quad hypertrophy volume'},
                    {'name': 'Lying Hamstring Curls', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Hamstring flexor isolation'},
                    {'name': 'Standing Calf Machine', 'sets': 4, 'reps': '15', 'rest_seconds': 45, 'notes': 'Calf endurance and definition'}
                ]},
                {'focus': f"⚔️ {t_name}: S-Rank Arms & Core", 'is_rest': False, 'exercises': [
                    {'name': 'Dips (Weighted)', 'sets': 3, 'reps': '10', 'rest_seconds': 75, 'notes': 'Tricep and lower chest power'},
                    {'name': 'Tricep Rope Pushdowns', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Tricep lateral head isolation'},
                    {'name': 'EZ-Bar Bicep Curls', 'sets': 3, 'reps': '10-12', 'rest_seconds': 60, 'notes': 'Bicep thickness'},
                    {'name': 'Hanging Leg Raises', 'sets': 4, 'reps': '12', 'rest_seconds': 60, 'notes': 'Lower abdominal compression'}
                ]},
                {'focus': f"⚔️ {t_name}: Dungeon Speed & Conditioning", 'is_rest': False, 'exercises': [
                    {'name': 'Incline Treadmill Sprints', 'sets': 5, 'reps': '30s sprint', 'rest_seconds': 60, 'notes': 'Fast-twitch speed recovery'},
                    {'name': 'Rowing Machine Intervals', 'sets': 3, 'reps': '500m', 'rest_seconds': 90, 'notes': 'Cardiovascular endurance'},
                    {'name': 'Kettlebell Swings', 'sets': 3, 'reps': '20', 'rest_seconds': 60, 'notes': 'Hip snap explosiveness'}
                ]},
                {'focus': f"🛌 {t_name}: Full Recovery Rest Day", 'is_rest': True, 'exercises': []}
            ]
    else:
        # General character / Custom / Photo build split adapted to equipment
        if is_home:
            split_days = [
                {'focus': f"⚔️ {t_name}: Upper Body Calisthenics", 'is_rest': False, 'exercises': [
                    {'name': 'Standard Push-ups', 'sets': 4, 'reps': '15', 'rest_seconds': 60, 'notes': 'Upper body pushing foundation'},
                    {'name': 'Pike Push-ups', 'sets': 3, 'reps': '10', 'rest_seconds': 60, 'notes': 'Shoulder deltoid strength'},
                    {'name': 'Chair / Bench Dips', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Tricep lockout power'},
                    {'name': 'Plank Hold', 'sets': 3, 'reps': '60 sec', 'rest_seconds': 45, 'notes': 'Core stability'}
                ]},
                {'focus': f"⚔️ {t_name}: Back Pull & Agility", 'is_rest': False, 'exercises': [
                    {'name': 'Doorframe / Towel Inverted Rows', 'sets': 4, 'reps': '12', 'rest_seconds': 60, 'notes': 'Back pulling without equipment'},
                    {'name': 'Superman Extensions', 'sets': 3, 'reps': '15', 'rest_seconds': 45, 'notes': 'Posterior chain stabilizer'},
                    {'name': 'Mountain Climbers', 'sets': 3, 'reps': '30 sec', 'rest_seconds': 45, 'notes': 'Agility conditioning'}
                ]},
                {'focus': f"🛌 {t_name}: Active Recovery & Mobility", 'is_rest': True, 'exercises': []},
                {'focus': f"⚔️ {t_name}: Lower Body Calisthenics", 'is_rest': False, 'exercises': [
                    {'name': 'Bodyweight Squats', 'sets': 4, 'reps': '20', 'rest_seconds': 60, 'notes': 'Leg power foundation'},
                    {'name': 'Bulgarian Split Squats', 'sets': 3, 'reps': '12 per leg', 'rest_seconds': 60, 'notes': 'Unilateral quad balance'},
                    {'name': 'Glute Bridges', 'sets': 3, 'reps': '15', 'rest_seconds': 45, 'notes': 'Glute and hamstring activation'},
                    {'name': 'Calf Raises', 'sets': 4, 'reps': '20', 'rest_seconds': 45, 'notes': 'Calf endurance'}
                ]},
                {'focus': f"⚔️ {t_name}: Full Body Conditioning", 'is_rest': False, 'exercises': [
                    {'name': 'Burpees', 'sets': 4, 'reps': '10', 'rest_seconds': 60, 'notes': 'Metabolic conditioning'},
                    {'name': 'Diamond Push-ups', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Tricep and chest focus'},
                    {'name': 'Jump Squats', 'sets': 3, 'reps': '15', 'rest_seconds': 60, 'notes': 'Explosive power'},
                    {'name': 'Russian Twists', 'sets': 3, 'reps': '20', 'rest_seconds': 45, 'notes': 'Rotational core'}
                ]},
                {'focus': f"⚔️ {t_name}: Core Mastery & Stretch", 'is_rest': False, 'exercises': [
                    {'name': 'Bicycle Crunches', 'sets': 3, 'reps': '20', 'rest_seconds': 45, 'notes': 'Abdominal conditioning'},
                    {'name': 'Side Planks', 'sets': 3, 'reps': '30s per side', 'rest_seconds': 45, 'notes': 'Oblique strength'},
                    {'name': 'Full Body Mobility Flow', 'sets': 1, 'reps': '20 mins', 'rest_seconds': 0, 'notes': 'Flexibility and recovery'}
                ]},
                {'focus': f"🛌 {t_name}: Rest & Growth Day", 'is_rest': True, 'exercises': []}
            ]
        elif is_db:
            split_days = [
                {'focus': f"⚔️ {t_name}: Dumbbell Push (Chest & Shoulders)", 'is_rest': False, 'exercises': [
                    {'name': 'Dumbbell Floor / Bench Press', 'sets': 4, 'reps': '10', 'rest_seconds': 75, 'notes': 'Chest strength builder'},
                    {'name': 'Dumbbell Shoulder Press', 'sets': 3, 'reps': '10', 'rest_seconds': 75, 'notes': 'Overhead shoulder power'},
                    {'name': 'Dumbbell Lateral Raises', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Deltoid isolation'}
                ]},
                {'focus': f"⚔️ {t_name}: Dumbbell Pull (Back & Biceps)", 'is_rest': False, 'exercises': [
                    {'name': 'Bent-over Dumbbell Rows', 'sets': 4, 'reps': '10', 'rest_seconds': 75, 'notes': 'Back thickness and lat power'},
                    {'name': 'Dumbbell Bicep Curls', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Arm hypertrophy'},
                    {'name': 'Dumbbell Romanian Deadlifts', 'sets': 3, 'reps': '10', 'rest_seconds': 90, 'notes': 'Hamstring hinge'}
                ]},
                {'focus': f"🛌 {t_name}: Rest & Recovery", 'is_rest': True, 'exercises': []},
                {'focus': f"⚔️ {t_name}: Dumbbell Legs & Core", 'is_rest': False, 'exercises': [
                    {'name': 'Dumbbell Goblet Squats', 'sets': 4, 'reps': '12', 'rest_seconds': 90, 'notes': 'Leg power and depth'},
                    {'name': 'Dumbbell Walking Lunges', 'sets': 3, 'reps': '10 per leg', 'rest_seconds': 75, 'notes': 'Unilateral balance'},
                    {'name': 'Dumbbell Russian Twists', 'sets': 3, 'reps': '20', 'rest_seconds': 45, 'notes': 'Core stability'}
                ]},
                {'focus': f"⚔️ {t_name}: Dumbbell Full Body Thrusters", 'is_rest': False, 'exercises': [
                    {'name': 'Dumbbell Thrusters', 'sets': 4, 'reps': '10', 'rest_seconds': 75, 'notes': 'Full body explosive output'},
                    {'name': 'Push-ups', 'sets': 3, 'reps': '15', 'rest_seconds': 60, 'notes': 'Chest volume'},
                    {'name': 'Dumbbell Hammer Curls', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Forearm strength'}
                ]},
                {'focus': f"⚔️ {t_name}: Core & Conditioning", 'is_rest': False, 'exercises': [
                    {'name': 'Plank with Dumbbell Pull-Through', 'sets': 3, 'reps': '12', 'rest_seconds': 45, 'notes': 'Anti-rotational core'},
                    {'name': 'Jump Squats', 'sets': 3, 'reps': '15', 'rest_seconds': 60, 'notes': 'Fast-twitch power'}
                ]},
                {'focus': f"🛌 {t_name}: Rest & Growth Day", 'is_rest': True, 'exercises': []}
            ]
        else:
            # Full Commercial Gym
            split_days = [
                {'focus': f"⚔️ {t_name}: Gym Push (Chest & Delts)", 'is_rest': False, 'exercises': [
                    {'name': 'Barbell Bench Press', 'sets': 4, 'reps': '8-10', 'rest_seconds': 90, 'notes': 'Chest compound mass'},
                    {'name': 'Overhead Barbell Press', 'sets': 3, 'reps': '8', 'rest_seconds': 90, 'notes': 'Shoulder strength'},
                    {'name': 'Incline Dumbbell Press', 'sets': 3, 'reps': '10', 'rest_seconds': 75, 'notes': 'Upper chest'}
                ]},
                {'focus': f"⚔️ {t_name}: Gym Pull (Back & Biceps)", 'is_rest': False, 'exercises': [
                    {'name': 'Lat Pulldowns', 'sets': 4, 'reps': '10', 'rest_seconds': 75, 'notes': 'Lat width and V-taper'},
                    {'name': 'Seated Cable Rows', 'sets': 3, 'reps': '10', 'rest_seconds': 75, 'notes': 'Mid-back density'},
                    {'name': 'Cable Bicep Curls', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Bicep hypertrophy'}
                ]},
                {'focus': f"🛌 {t_name}: Rest & Recovery", 'is_rest': True, 'exercises': []},
                {'focus': f"⚔️ {t_name}: Gym Legs (Squats & Machines)", 'is_rest': False, 'exercises': [
                    {'name': 'Barbell Back Squats', 'sets': 4, 'reps': '8-10', 'rest_seconds': 90, 'notes': 'Quad and glute power'},
                    {'name': 'Leg Press Machine', 'sets': 3, 'reps': '12', 'rest_seconds': 75, 'notes': 'Leg volume'},
                    {'name': 'Lying Hamstring Curls', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Hamstring flexor isolation'}
                ]},
                {'focus': f"⚔️ {t_name}: Arms & Core Hypertrophy", 'is_rest': False, 'exercises': [
                    {'name': 'Dips (Weighted)', 'sets': 3, 'reps': '10', 'rest_seconds': 75, 'notes': 'Tricep power'},
                    {'name': 'Tricep Rope Pushdowns', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Tricep isolation'},
                    {'name': 'Hanging Leg Raises', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Lower ab compression'}
                ]},
                {'focus': f"⚔️ {t_name}: Speed & Conditioning", 'is_rest': False, 'exercises': [
                    {'name': 'Incline Treadmill Sprints', 'sets': 5, 'reps': '30s sprint', 'rest_seconds': 60, 'notes': 'High-intensity conditioning'},
                    {'name': 'Rowing Machine Intervals', 'sets': 3, 'reps': '500m', 'rest_seconds': 90, 'notes': 'Cardio stamina'}
                ]},
                {'focus': f"🛌 {t_name}: Full Recovery Rest Day", 'is_rest': True, 'exercises': []}
            ]

    # Structure all 7 days with day_of_week indices
    structured_days = []
    for idx, day_info in enumerate(split_days[:7]):
        structured_days.append({
            'day_of_week': idx,
            'day_label': day_names[idx],
            'focus': day_info['focus'],
            'is_rest': day_info['is_rest'],
            'exercises': day_info.get('exercises', [])
        })

    # Build formatted markdown
    markdown_lines = [
        f"# 🎭 Quest Log: Becoming {t_name} ({equipment})",
        "",
        "## Physique Breakdown",
        f"- **Archetype**: {t_name} Physical Standard",
        f"- **Training Location**: {equipment}",
        f"- **Physical Baseline**: {body_type.upper()}",
        "- **Focus**: Aesthetic muscle definition, explosive power, and functional conditioning adapted specifically to your available equipment.",
        "",
        "## Daily Dailies",
        "- 💧 Drink at least 3-4 liters of water daily.",
        "- 🥩 Prioritize high-protein nutrition (1.6 - 2.2g per kg bodyweight).",
        "- 😴 Target 7.5 - 9 hours of restorative sleep.",
        "",
        "## Main Story Quests",
        f"Your 7-day training split tailored to {equipment}:",
        ""
    ]

    for d in structured_days:
        markdown_lines.append(f"### {d['day_label']}: {d['focus']}")
        if d['is_rest']:
            markdown_lines.append("- *Scheduled Rest & Muscle Recovery Day*")
        else:
            for ex in d['exercises']:
                markdown_lines.append(f"- **{ex['name']}**: {ex['sets']} sets x {ex['reps']} reps ({ex.get('notes', 'Part of daily routine')})")
        markdown_lines.append("")

    markdown_lines.extend([
        "## Side Quests",
        f"- ⚡ **Level 1 Challenge**: Complete all 7 days of the {equipment} split with 100% adherence.",
        f"- 🏆 **Monarch's Trial**: Beat at least one exercise repetition PR each week.",
        "",
        "## Level Up Milestones",
        "- 🌟 **Milestone 1**: 7-Day Consistency Streak unlocked.",
        "- 🌟 **Milestone 2**: +5 to all Core Attributes (Strength, Endurance, Agility, Vitality).",
        "- 🌟 **Milestone 3**: Visible muscle density and V-taper aesthetic transformation."
    ])

    markdown_text = "\n".join(markdown_lines)
    return markdown_text, structured_days
