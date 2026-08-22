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


# Multi-tier candidate models in order of priority.
# gemini-3.6-flash and gemini-3-flash-preview provide lightning-fast, high-capacity generation,
# while gemini-flash-latest serves as alias fallback.
CANDIDATE_MODELS = [
    "gemini-3.6-flash",
    "gemini-3-flash-preview",
    "gemini-flash-latest"
]
MODEL_NAME = CANDIDATE_MODELS[0]


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
    """Generates physique-goal based Quest Logs via Google Gemini with resilient multi-model fallbacks"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
        self.client = None
        if genai and self.api_key:
            self.client = genai.Client(api_key=self.api_key)

    def is_configured(self) -> bool:
        """Check whether the API key / SDK is available"""
        return self.client is not None

    def _generate_content_resilient(self, contents, generation_config=None) -> tuple[Optional[str], Optional[str]]:
        """
        Attempt generation across candidate models with automatic retry & backoff
        for transient 503 UNAVAILABLE, 429 RESOURCE_EXHAUSTED, or network timeouts.
        
        Returns: (text_output, error_message)
        """
        if not self.is_configured():
            return None, "Gemini API key is not configured."

        import time
        last_error = None

        for model_name in CANDIDATE_MODELS:
            for attempt in range(2):
                try:
                    kwargs = {'model': model_name, 'contents': contents}
                    if generation_config:
                        kwargs['config'] = generation_config
                    
                    response = self.client.models.generate_content(**kwargs)
                    if response and response.text:
                        return response.text.strip(), None
                except Exception as e:
                    last_error = str(e)
                    err_lower = last_error.lower()
                    
                    # 404 Not Found -> Model name retired/unsupported, skip directly to next candidate model
                    if '404' in err_lower or 'not_found' in err_lower:
                        print(f"[WARN] Model {model_name} unavailable (404), trying next candidate...")
                        break
                    
                    # 503 / 429 / High demand / Quota -> Transient spike, retry with small backoff
                    if '503' in err_lower or 'unavailable' in err_lower or '429' in err_lower or 'high demand' in err_lower or 'exhausted' in err_lower:
                        print(f"[WARN] Model {model_name} busy (attempt {attempt+1}/2: {e}).")
                        if attempt == 0:
                            time.sleep(1.0)
                            continue
                    
                    # Second attempt failed or non-retriable error -> move to next candidate model
                    print(f"[WARN] Model {model_name} failed: {e}. Cascading to alternative candidate...")
                    break

        return None, last_error

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
        uploaded photo. Uses resilient Gemini AI model cascading with instant
        deterministic fallback to guarantee uninterrupted training splits.
        """
        if not target_name and not image_path:
            return {
                'success': False,
                'error': 'Provide either a target character/person name OR upload a reference image.'
            }

        quest_log_markdown = None
        generation_error = None

        if self.is_configured():
            try:
                contents = self._build_contents(
                    target_name=target_name,
                    image_path=image_path,
                    current_body_type=current_body_type,
                    injuries=injuries,
                    equipment=equipment
                )
                quest_log_markdown, generation_error = self._generate_content_resilient(contents)
            except Exception as e:
                generation_error = str(e)
                print(f"[WARN] AI content build/generation error: {e}")

        if quest_log_markdown:
            return {
                'success': True,
                'target_name': target_name or 'Uploaded Photo Subject',
                'source_type': 'image' if image_path else 'text',
                'quest_log_markdown': quest_log_markdown,
                'fallback_used': False
            }

        # Fallback handling:
        # If a target character/person name was provided, fall back smoothly to our authentic character generator
        if target_name:
            eq = equipment or "Full Commercial Gym"
            bt = current_body_type or "mesomorph"
            inj = injuries or "None"
            fallback_md, _ = generate_character_equipment_split(
                target_name=target_name,
                equipment=eq,
                body_type=bt,
                injuries=inj
            )
            notice = "[SYSTEM] AI service is experiencing temporary high demand. Generated your authentic build protocol via System Engine so your training isn't interrupted!"
            print(f"[INFO] Used deterministic character engine for '{target_name}' (AI notice: {generation_error})")
            return {
                'success': True,
                'target_name': target_name,
                'source_type': 'text',
                'quest_log_markdown': fallback_md,
                'fallback_used': True,
                'notice': notice
            }

        # If it was an image upload and AI failed completely:
        if not self.is_configured():
            return {
                'success': False,
                'error': 'Gemini API key is not configured. Go to Settings to add your key.',
                'setup_required': True
            }

        return {
            'success': False,
            'error': 'AI vision service is currently experiencing high demand. Please try again in a few moments or enter your character name directly.'
        }

    def extract_structured_weekly_plan(self, quest_log_markdown: str, target_name: Optional[str] = None, equipment: str = "Full Commercial Gym") -> Dict:
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
                raw_text, _ = self._generate_content_resilient([structuring_prompt])
                if raw_text:
                    clean_text = raw_text.strip()
                    if clean_text.startswith('```'):
                        clean_text = clean_text.split('```')[1]
                        if clean_text.startswith('json'):
                            clean_text = clean_text[4:]
                        clean_text = clean_text.strip()

                    import json
                    parsed = json.loads(clean_text)

                    days = parsed.get('days', [])
                    if len(days) == 7:
                        return {'success': True, 'days': days, 'fallback_used': False}
            except Exception as e:
                print(f"[WARN] Gemini JSON structuring failed ({e}), falling back to deterministic parser.")

        # Deterministic markdown parsing fallback (guarantees a 7-day split is always built)
        fallback_days = parse_weekly_plan_from_markdown(quest_log_markdown, target_name, equipment=equipment)
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
                print(f"[WARN] AI adaptation for {target_name} to {new_equipment} failed ({e}), using deterministic character adapter.")

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
            print(f"[WARN] Error saving adapted weekly plan: {ex_db}")

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
            raw_text, _ = self._generate_content_resilient([prompt])
            if raw_text:
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
            print(f"⚠️ Workout JSON generation exception: {e}")

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
            'notice': 'Generated optimized protocol via System Fallback Engine'
        }

    def _generate_fallback_json_routine(self, body_type: str, enriched_baseline: str, days_per_week: int, equipment: str, injuries: str) -> dict:
        """
        Generate deterministic fallback program adhering strictly to equipment access and body type.
        """
        eq = (equipment or '').lower()
        is_calisthenics = 'calisthenic' in eq
        is_db = not is_calisthenics and 'dumbbell' in eq
        is_home = not is_calisthenics and not is_db and ('home' in eq or 'bodyweight' in eq or 'none' in eq)
        
        if is_calisthenics:
            overview = f"Elite Calisthenics & Body Mastery Protocol tailored for {body_type.upper()} build with bar & ring gymnastics skills."
            schedule = [
                {
                    "day_number": 1,
                    "muscle_focus": "Upper Pull & Front Lever Mastery (Calisthenics)",
                    "routine": [
                        {"exercise_name": "Explosive Pull-Ups / Muscle-Up Progressions", "sets": 4, "reps": "6-8", "rest_seconds": 90, "form_cue": "Explosive pull to chest level, hollow body core."},
                        {"exercise_name": "Wide Grip Strict Pull-Ups", "sets": 3, "reps": "8-10", "rest_seconds": 75, "form_cue": "Full dead hang to chin over bar with zero kipping."},
                        {"exercise_name": "L-Sit Chin-Ups", "sets": 3, "reps": "6-8", "rest_seconds": 75, "form_cue": "Lock legs straight parallel to floor during entire pull."},
                        {"exercise_name": "Dragon Flags / Hollow Body Hold", "sets": 3, "reps": "8 reps / 45s", "rest_seconds": 60, "form_cue": "Pivot only on upper back, rigid core pillar."}
                    ]
                },
                {
                    "day_number": 2,
                    "muscle_focus": "Upper Push & Handstand / Planche Power (Calisthenics)",
                    "routine": [
                        {"exercise_name": "Handstand Push-Ups / Pike Push-Ups", "sets": 4, "reps": "6-8", "rest_seconds": 90, "form_cue": "Slow controlled descent, press back through shoulders."},
                        {"exercise_name": "Deep Parallel Bar Dips", "sets": 4, "reps": "12", "rest_seconds": 75, "form_cue": "Full depth below 90 degrees, lock triceps at top."},
                        {"exercise_name": "Archer Push-Ups", "sets": 3, "reps": "8 per side", "rest_seconds": 60, "form_cue": "Keep straight arm locked while other arm presses."},
                        {"exercise_name": "Pseudo Planche Push-Ups", "sets": 3, "reps": "10", "rest_seconds": 60, "form_cue": "Lean shoulders far forward past wrists, protract scapula."}
                    ]
                },
                {
                    "day_number": 3,
                    "muscle_focus": "Calisthenics Leg Explosiveness & Mobility",
                    "routine": [
                        {"exercise_name": "Strict Pistol Squats", "sets": 4, "reps": "8 per leg", "rest_seconds": 75, "form_cue": "Non-working leg straight forward, full rock-bottom depth."},
                        {"exercise_name": "Explosive Tuck Jump Squats", "sets": 4, "reps": "12", "rest_seconds": 60, "form_cue": "Maximum vertical height, soft quiet landing."},
                        {"exercise_name": "Shrimp Squats / Single-Leg Glute Bridges", "sets": 3, "reps": "8 per leg", "rest_seconds": 60, "form_cue": "Control descent to back knee gently touching floor."},
                        {"exercise_name": "Elevated Calf Raises & Ankle Mobility", "sets": 4, "reps": "25", "rest_seconds": 45, "form_cue": "Deep stretch at bottom, 2s peak hold at top."}
                    ]
                }
            ]
        elif is_home:
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
    Includes rich themed splits for legendary physiques (Goku, Jin-Woo, Baki, Toji,
    Saitama, Vegeta, Zoro, Levi, Batman, etc.) and a smart dynamic archetype builder for any custom target.
    """
    t_name = target_name or "Shadow Hunter"
    t_lower = t_name.lower()
    eq = (equipment or "Full Commercial Gym").lower()
    is_calisthenics = 'calisthenic' in eq
    is_db = not is_calisthenics and 'dumbbell' in eq
    is_home = not is_calisthenics and not is_db and ('home' in eq or 'bodyweight' in eq or 'none' in eq)
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

    # 1. GOKU / SAIYAN GOD PROTOCOL
    if 'goku' in t_lower or 'kakarot' in t_lower or 'saiyan' in t_lower or 'ultra instinct' in t_lower:
        if is_calisthenics:
            split_days = [
                {'focus': f"🔥 {t_name}: 100x Gravity Explosive Pull & Core", 'is_rest': False, 'exercises': [
                    {'name': 'Explosive Muscle-Ups / High Pull-ups', 'sets': 4, 'reps': '6-8', 'rest_seconds': 90, 'notes': 'Pull bar down to sternum with explosive Saiyan force'},
                    {'name': 'Wide-Grip Strict Pull-ups', 'sets': 4, 'reps': '10', 'rest_seconds': 75, 'notes': 'Deep lat spread and upper back thickness'},
                    {'name': 'L-Sit Chin-ups', 'sets': 3, 'reps': '8', 'rest_seconds': 75, 'notes': 'Bicep isometric compression'},
                    {'name': 'Dragon Flags', 'sets': 3, 'reps': '8', 'rest_seconds': 60, 'notes': 'Unbreakable gravity chamber core pillar'}
                ]},
                {'focus': f"⚡ {t_name}: Kamehameha Upper Push Power", 'is_rest': False, 'exercises': [
                    {'name': 'Handstand Push-ups / Elevated Pike Press', 'sets': 4, 'reps': '8', 'rest_seconds': 90, 'notes': 'Massive Saiyan boulder shoulder pressing'},
                    {'name': 'Deep Parallel Bar Dips', 'sets': 4, 'reps': '12-15', 'rest_seconds': 75, 'notes': 'Full lockout through triceps and lower chest'},
                    {'name': 'Explosive Clap Push-ups', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Fast-twitch martial arts striking speed'},
                    {'name': 'Pseudo Planche Push-ups', 'sets': 3, 'reps': '10', 'rest_seconds': 60, 'notes': 'Straight-arm scapular density'}
                ]},
                {'focus': f"🍃 {t_name}: Korin Tower Rest & Senzu Recovery", 'is_rest': True, 'exercises': []},
                {'focus': f"💥 {t_name}: Kaio-Ken Explosive Leg Power", 'is_rest': False, 'exercises': [
                    {'name': 'Strict Pistol Squats', 'sets': 4, 'reps': '8 per leg', 'rest_seconds': 75, 'notes': 'Heavy single-leg quad power and balance'},
                    {'name': 'Explosive Tuck Jump Squats', 'sets': 4, 'reps': '15', 'rest_seconds': 60, 'notes': 'Maximum vertical leap takeoff power'},
                    {'name': 'Shrimp Squats / Bulgarian Splits', 'sets': 3, 'reps': '10 per leg', 'rest_seconds': 60, 'notes': 'Glute and knee joint armor'},
                    {'name': 'Elevated Single-Leg Calf Raises', 'sets': 4, 'reps': '25', 'rest_seconds': 45, 'notes': 'Instant footwork sprint springiness'}
                ]},
                {'focus': f"⚔️ {t_name}: Hyperbolic Time Chamber Conditioning", 'is_rest': False, 'exercises': [
                    {'name': 'Burpees to Pull-up', 'sets': 4, 'reps': '10', 'rest_seconds': 60, 'notes': 'Combat conditioning capacity'},
                    {'name': 'Straight Bar Dips', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Bar transition power'},
                    {'name': 'Hanging Windshield Wipers', 'sets': 3, 'reps': '12', 'rest_seconds': 45, 'notes': 'Rotational core armor'},
                    {'name': 'Hollow Body Rocks', 'sets': 3, 'reps': '45 sec', 'rest_seconds': 45, 'notes': 'Complete Saiyan core brace'}
                ]},
                {'focus': f"🔥 {t_name}: Ultra Instinct Speed & Shadow Flow", 'is_rest': False, 'exercises': [
                    {'name': 'High-Knee Sprint Burpee Intervals', 'sets': 5, 'reps': '45s work', 'rest_seconds': 60, 'notes': 'High aerobic output and reflex speed'},
                    {'name': 'Diamond Push-ups', 'sets': 3, 'reps': '15', 'rest_seconds': 45, 'notes': 'Tricep fatigue burnout'},
                    {'name': 'Typewriter Pull-ups', 'sets': 3, 'reps': '6 per side', 'rest_seconds': 60, 'notes': 'Side-to-side lat agility'},
                    {'name': 'Full Body Mobility Yoga Flow', 'sets': 1, 'reps': '20 mins', 'rest_seconds': 0, 'notes': 'Joint decompression'}
                ]},
                {'focus': f"🍃 {t_name}: Full Zenkai Recovery Day", 'is_rest': True, 'exercises': []}
            ]
        elif is_home:
            split_days = [
                {'focus': f"🔥 {t_name}: Gravity Push & Torso Armor", 'is_rest': False, 'exercises': [
                    {'name': 'Standard & Diamond Push-ups', 'sets': 4, 'reps': '20', 'rest_seconds': 60, 'notes': 'Chest and tricep power foundation'},
                    {'name': 'Pike Push-ups (Elevated)', 'sets': 4, 'reps': '10', 'rest_seconds': 60, 'notes': 'Vertical shoulder strength'},
                    {'name': 'Bed / Chair Dips', 'sets': 4, 'reps': '15', 'rest_seconds': 60, 'notes': 'Tricep lockout power'},
                    {'name': 'Hollow Body Hold', 'sets': 3, 'reps': '45 sec', 'rest_seconds': 45, 'notes': 'Rigid martial core brace'}
                ]},
                {'focus': f"⚡ {t_name}: Back Density & Agility", 'is_rest': False, 'exercises': [
                    {'name': 'Doorframe / Towel Inverted Rows', 'sets': 4, 'reps': '15', 'rest_seconds': 60, 'notes': 'Back thickness without equipment'},
                    {'name': 'Superman Back Extensions', 'sets': 3, 'reps': '15', 'rest_seconds': 45, 'notes': 'Posterior chain reinforcement'},
                    {'name': 'Mountain Climbers', 'sets': 4, 'reps': '30 sec', 'rest_seconds': 45, 'notes': 'Combat conditioning tempo'},
                    {'name': 'Bicycle Crunches', 'sets': 3, 'reps': '25', 'rest_seconds': 45, 'notes': 'Rotational oblique power'}
                ]},
                {'focus': f"🍃 {t_name}: Senzu Bean Rest & Stretch", 'is_rest': True, 'exercises': []},
                {'focus': f"💥 {t_name}: Kaio-Ken Leg Explosiveness", 'is_rest': False, 'exercises': [
                    {'name': 'Jump Squats', 'sets': 4, 'reps': '15', 'rest_seconds': 60, 'notes': 'Fast-twitch vertical power'},
                    {'name': 'Bulgarian Split Squats (Chair)', 'sets': 3, 'reps': '12 per leg', 'rest_seconds': 60, 'notes': 'Single-leg quad drive'},
                    {'name': 'Single-Leg Glute Bridges', 'sets': 3, 'reps': '15 per leg', 'rest_seconds': 45, 'notes': 'Posterior chain stability'},
                    {'name': 'Elevated Calf Raises', 'sets': 4, 'reps': '25', 'rest_seconds': 45, 'notes': 'Sprint agility and bounce'}
                ]},
                {'focus': f"⚔️ {t_name}: Martial Arts Endurance Trial", 'is_rest': False, 'exercises': [
                    {'name': 'Burpees', 'sets': 4, 'reps': '12', 'rest_seconds': 60, 'notes': 'Full-body cardiovascular output'},
                    {'name': 'Decline Push-ups (Feet on Bed)', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Upper clavicular chest mass'},
                    {'name': 'Bodyweight Squats (Tempo 3s descent)', 'sets': 3, 'reps': '25', 'rest_seconds': 60, 'notes': 'Metabolic quad endurance'},
                    {'name': 'Plank to Push-up', 'sets': 3, 'reps': '12', 'rest_seconds': 45, 'notes': 'Shoulder and core integration'}
                ]},
                {'focus': f"🔥 {t_name}: Ultra Instinct Conditioning", 'is_rest': False, 'exercises': [
                    {'name': 'Shadow Boxing Intervals', 'sets': 4, 'reps': '60 sec', 'rest_seconds': 45, 'notes': 'Fast striking speed and footwork'},
                    {'name': 'Russian Twists', 'sets': 3, 'reps': '25', 'rest_seconds': 45, 'notes': 'Core rotation power'},
                    {'name': 'Wall Sits', 'sets': 3, 'reps': '60 sec', 'rest_seconds': 45, 'notes': 'Isometric leg stamina'},
                    {'name': 'Full Body Mobility Flow', 'sets': 1, 'reps': '20 mins', 'rest_seconds': 0, 'notes': 'Flexibility and joint longevity'}
                ]},
                {'focus': f"🍃 {t_name}: Full Zenkai Recovery Day", 'is_rest': True, 'exercises': []}
            ]
        elif is_db:
            split_days = [
                {'focus': f"🔥 {t_name}: Saiyan Dumbbell Heavy Push", 'is_rest': False, 'exercises': [
                    {'name': 'Dumbbell Flat / Floor Press', 'sets': 4, 'reps': '8-10', 'rest_seconds': 90, 'notes': 'Heavy compound chest drive'},
                    {'name': 'Standing Dumbbell Shoulder Press', 'sets': 4, 'reps': '8-10', 'rest_seconds': 75, 'notes': 'Saiyan shoulder armor'},
                    {'name': 'Incline Dumbbell Press', 'sets': 3, 'reps': '10-12', 'rest_seconds': 75, 'notes': 'Upper chest development'},
                    {'name': 'Dumbbell Lateral Raises', 'sets': 3, 'reps': '15', 'rest_seconds': 60, 'notes': '3D side delts'}
                ]},
                {'focus': f"⚡ {t_name}: Saiyan Heavy Pull & Lats", 'is_rest': False, 'exercises': [
                    {'name': 'Bent-over Dumbbell Rows', 'sets': 4, 'reps': '8-10', 'rest_seconds': 90, 'notes': 'Back thickness and lat width'},
                    {'name': 'Dumbbell Romanian Deadlifts', 'sets': 4, 'reps': '10', 'rest_seconds': 90, 'notes': 'Hamstring and glute hinge'},
                    {'name': 'Dumbbell Hammer Curls', 'sets': 3, 'reps': '10-12', 'rest_seconds': 60, 'notes': 'Forearm and bicep mass'},
                    {'name': 'Dumbbell Rear Delt Flyes', 'sets': 3, 'reps': '15', 'rest_seconds': 60, 'notes': 'Upper back posture'}
                ]},
                {'focus': f"🍃 {t_name}: Korin Tower Rest & Recovery", 'is_rest': True, 'exercises': []},
                {'focus': f"💥 {t_name}: Kaio-Ken Dumbbell Legs", 'is_rest': False, 'exercises': [
                    {'name': 'Dumbbell Goblet Squats', 'sets': 4, 'reps': '10-12', 'rest_seconds': 90, 'notes': 'Deep quad power'},
                    {'name': 'Dumbbell Walking Lunges', 'sets': 3, 'reps': '10 per leg', 'rest_seconds': 75, 'notes': 'Unilateral balance'},
                    {'name': 'Dumbbell Calf Raises', 'sets': 4, 'reps': '20', 'rest_seconds': 45, 'notes': 'Explosive ankle drive'},
                    {'name': 'Dumbbell Romanian Deadlifts', 'sets': 3, 'reps': '10', 'rest_seconds': 75, 'notes': 'Hamstring flexor strength'}
                ]},
                {'focus': f"⚔️ {t_name}: Saiyan Arms & Core Hypertrophy", 'is_rest': False, 'exercises': [
                    {'name': 'Overhead Dumbbell Tricep Extension', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Long head tricep mass'},
                    {'name': 'Dumbbell Incline Bicep Curls', 'sets': 3, 'reps': '10-12', 'rest_seconds': 60, 'notes': 'Bicep peak contraction'},
                    {'name': 'Plank with Dumbbell Pull-Through', 'sets': 3, 'reps': '12', 'rest_seconds': 45, 'notes': 'Anti-rotational core armor'},
                    {'name': 'Dumbbell Russian Twists', 'sets': 3, 'reps': '20', 'rest_seconds': 45, 'notes': 'Oblique definition'}
                ]},
                {'focus': f"🔥 {t_name}: Ultra Instinct Conditioning & Thrusters", 'is_rest': False, 'exercises': [
                    {'name': 'Dumbbell Thrusters (Squat to Press)', 'sets': 4, 'reps': '10', 'rest_seconds': 75, 'notes': 'Full body explosive output'},
                    {'name': 'Dumbbell Renegade Rows', 'sets': 3, 'reps': '8 per arm', 'rest_seconds': 60, 'notes': 'Core and back synergy'},
                    {'name': 'Push-ups to Floor', 'sets': 3, 'reps': '20', 'rest_seconds': 60, 'notes': 'Chest burnout'},
                    {'name': 'Dumbbell Farmer Carries', 'sets': 3, 'reps': '45 sec', 'rest_seconds': 60, 'notes': 'Grip and trap stamina'}
                ]},
                {'focus': f"🍃 {t_name}: Full Zenkai Recovery Day", 'is_rest': True, 'exercises': []}
            ]
        else:
            # Full Commercial Gym
            split_days = [
                {'focus': f"🔥 {t_name}: Heavy Saiyan Push (Chest & Shoulders)", 'is_rest': False, 'exercises': [
                    {'name': 'Barbell Bench Press', 'sets': 4, 'reps': '6-8', 'rest_seconds': 120, 'notes': 'Heavy compound chest pressing'},
                    {'name': 'Overhead Barbell Press', 'sets': 4, 'reps': '6-8', 'rest_seconds': 90, 'notes': 'Saiyan shoulder mass'},
                    {'name': 'Incline Dumbbell Press', 'sets': 3, 'reps': '10-12', 'rest_seconds': 75, 'notes': 'Upper chest development'},
                    {'name': 'Cable Lateral Raises', 'sets': 3, 'reps': '15', 'rest_seconds': 60, 'notes': '3D side delts'}
                ]},
                {'focus': f"⚡ {t_name}: Gravity Pull (Deadlifts & Lats)", 'is_rest': False, 'exercises': [
                    {'name': 'Barbell Deadlifts', 'sets': 4, 'reps': '5', 'rest_seconds': 150, 'notes': 'Total posterior chain Saiyan power'},
                    {'name': 'Lat Pulldowns / Weighted Pull-ups', 'sets': 4, 'reps': '8-10', 'rest_seconds': 90, 'notes': 'V-taper lat width'},
                    {'name': 'Seated Cable Rows', 'sets': 3, 'reps': '10', 'rest_seconds': 75, 'notes': 'Mid-back thickness'},
                    {'name': 'EZ-Bar Bicep Curls', 'sets': 3, 'reps': '10-12', 'rest_seconds': 60, 'notes': 'Bicep hypertrophy'}
                ]},
                {'focus': f"🍃 {t_name}: Korin Tower Rest & Recovery", 'is_rest': True, 'exercises': []},
                {'focus': f"💥 {t_name}: Kaio-Ken Leg Power (Squats)", 'is_rest': False, 'exercises': [
                    {'name': 'Barbell Back Squats', 'sets': 4, 'reps': '6-8', 'rest_seconds': 120, 'notes': 'Heavy quad and glute strength'},
                    {'name': 'Leg Press Machine', 'sets': 3, 'reps': '12', 'rest_seconds': 90, 'notes': 'Quad hypertrophy volume'},
                    {'name': 'Lying Leg Curls / RDLs', 'sets': 3, 'reps': '10-12', 'rest_seconds': 75, 'notes': 'Direct hamstring overload'},
                    {'name': 'Standing Calf Machine', 'sets': 4, 'reps': '15', 'rest_seconds': 45, 'notes': 'Calf endurance and definition'}
                ]},
                {'focus': f"⚔️ {t_name}: Super Saiyan Arms & Core", 'is_rest': False, 'exercises': [
                    {'name': 'Dips (Weighted or Bodyweight)', 'sets': 3, 'reps': '10-12', 'rest_seconds': 75, 'notes': 'Tricep and lower chest lockout'},
                    {'name': 'Tricep Rope Pushdowns', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Tricep lateral head isolation'},
                    {'name': 'Incline Dumbbell Curls', 'sets': 3, 'reps': '10-12', 'rest_seconds': 60, 'notes': 'Bicep peak'},
                    {'name': 'Hanging Leg Raises', 'sets': 4, 'reps': '12', 'rest_seconds': 60, 'notes': 'Lower abdominal compression'}
                ]},
                {'focus': f"🔥 {t_name}: Ultra Instinct Speed & Conditioning", 'is_rest': False, 'exercises': [
                    {'name': 'Incline Treadmill Sprints', 'sets': 5, 'reps': '30s sprint', 'rest_seconds': 60, 'notes': 'Fast-twitch speed recovery'},
                    {'name': 'Rowing Machine Intervals', 'sets': 3, 'reps': '500m', 'rest_seconds': 90, 'notes': 'Full body aerobic power'},
                    {'name': 'Kettlebell Swings', 'sets': 3, 'reps': '20', 'rest_seconds': 60, 'notes': 'Hip snap explosiveness'}
                ]},
                {'focus': f"🍃 {t_name}: Full Zenkai Recovery Day", 'is_rest': True, 'exercises': []}
            ]

    # 2. SUNG JIN-WOO / SHADOW MONARCH PROTOCOL
    elif 'jin-woo' in t_lower or 'jinwoo' in t_lower or 'sung' in t_lower or 'monarch' in t_lower:
        if is_calisthenics:
            split_days = [
                {'focus': f"⚔️ {t_name}: Bar Mastery & Explosive Pull", 'is_rest': False, 'exercises': [
                    {'name': 'Explosive Pull-ups / Muscle-ups', 'sets': 4, 'reps': '6-8', 'rest_seconds': 90, 'notes': 'Shadow Monarch explosive bar power'},
                    {'name': 'Wide-Grip Strict Pull-ups', 'sets': 4, 'reps': '10', 'rest_seconds': 75, 'notes': 'Lat V-taper development'},
                    {'name': 'L-Sit Chin-ups', 'sets': 3, 'reps': '8', 'rest_seconds': 75, 'notes': 'Bicep & core isometric synergy'},
                    {'name': 'Dragon Flags', 'sets': 3, 'reps': '8', 'rest_seconds': 60, 'notes': 'Ultimate hollow body abdominal strength'}
                ]},
                {'focus': f"⚔️ {t_name}: Handstand & Dips Power", 'is_rest': False, 'exercises': [
                    {'name': 'Handstand Push-ups', 'sets': 4, 'reps': '6-8', 'rest_seconds': 90, 'notes': 'Vertical shoulder & deltoid pressing power'},
                    {'name': 'Deep Parallel Bar Dips', 'sets': 4, 'reps': '12-15', 'rest_seconds': 75, 'notes': 'Heavy tricep & lower chest lockout'},
                    {'name': 'Archer Push-ups', 'sets': 3, 'reps': '8 per arm', 'rest_seconds': 60, 'notes': 'Unilateral pressing balance'},
                    {'name': 'Pseudo Planche Push-ups', 'sets': 3, 'reps': '10', 'rest_seconds': 60, 'notes': 'Straight-arm scapular protraction'}
                ]},
                {'focus': f"🛌 {t_name}: Shadow Realm Rest & Mobility", 'is_rest': True, 'exercises': []},
                {'focus': f"⚔️ {t_name}: Ruler's Calisthenics Legs", 'is_rest': False, 'exercises': [
                    {'name': 'Strict Pistol Squats', 'sets': 4, 'reps': '8 per leg', 'rest_seconds': 75, 'notes': 'Single-leg quad and balance mastery'},
                    {'name': 'Explosive Jump Squats', 'sets': 4, 'reps': '15', 'rest_seconds': 60, 'notes': 'Dungeon dash vertical leap'},
                    {'name': 'Shrimp Squats', 'sets': 3, 'reps': '8 per leg', 'rest_seconds': 60, 'notes': 'Deep knee and glute stabilization'},
                    {'name': 'Elevated Single-Leg Calf Raises', 'sets': 4, 'reps': '20', 'rest_seconds': 45, 'notes': 'Ankle stiffness & reflex power'}
                ]},
                {'focus': f"⚔️ {t_name}: 100x Daily Quest Trial", 'is_rest': False, 'exercises': [
                    {'name': 'Standard Push-ups', 'sets': 4, 'reps': '25', 'rest_seconds': 60, 'notes': 'System daily quest target (100 pushups)'},
                    {'name': 'Bodyweight Squats', 'sets': 4, 'reps': '25', 'rest_seconds': 60, 'notes': 'System daily quest target (100 squats)'},
                    {'name': 'Hanging Leg Raises', 'sets': 4, 'reps': '15', 'rest_seconds': 60, 'notes': 'System core advancement target'},
                    {'name': 'High-Knee Sprint in Place', 'sets': 4, 'reps': '60 sec', 'rest_seconds': 60, 'notes': '10km conditioning trial'}
                ]},
                {'focus': f"⚔️ {t_name}: Monarch Bar Flow & Core", 'is_rest': False, 'exercises': [
                    {'name': 'Straight Bar Dips', 'sets': 3, 'reps': '10', 'rest_seconds': 75, 'notes': 'Bar transition power'},
                    {'name': 'Typewriter Pull-ups', 'sets': 3, 'reps': '6 per side', 'rest_seconds': 75, 'notes': 'Side-to-side lat control'},
                    {'name': 'Hanging Windshield Wipers', 'sets': 3, 'reps': '10', 'rest_seconds': 60, 'notes': 'Oblique and abdominal rotational control'},
                    {'name': 'L-Sit Hold', 'sets': 3, 'reps': '30 sec', 'rest_seconds': 45, 'notes': 'Hip flexor & core compression'}
                ]},
                {'focus': f"🛌 {t_name}: System Full Recovery", 'is_rest': True, 'exercises': []}
            ]
        elif is_home:
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

    # 3. BAKI HANMA / DEMON BACK PROTOCOL
    elif 'baki' in t_lower or 'hanma' in t_lower or 'yujiro' in t_lower or 'demon back' in t_lower:
        if is_calisthenics:
            split_days = [
                {'focus': f"👹 {t_name}: Demon Back Pull & Scapular Armor", 'is_rest': False, 'exercises': [
                    {'name': 'Strict Wide-Grip Pull-ups', 'sets': 5, 'reps': '8-12', 'rest_seconds': 90, 'notes': 'Deep scapular retraction creating the Demon Face'},
                    {'name': 'Muscle-Ups / High Bar Pulls', 'sets': 4, 'reps': '6', 'rest_seconds': 90, 'notes': 'Explosive vertical pull power'},
                    {'name': 'L-Sit Chin-ups', 'sets': 3, 'reps': '8', 'rest_seconds': 75, 'notes': 'Bicep and abdominal tension'},
                    {'name': 'Dragon Flags', 'sets': 4, 'reps': '8', 'rest_seconds': 60, 'notes': 'Rigid spine and core pillar'}
                ]},
                {'focus': f"👹 {t_name}: Underground Arena Push & Striking", 'is_rest': False, 'exercises': [
                    {'name': 'Handstand Push-ups', 'sets': 4, 'reps': '8', 'rest_seconds': 90, 'notes': 'Deltoid shoulder armor'},
                    {'name': 'Deep Parallel Bar Dips', 'sets': 4, 'reps': '15', 'rest_seconds': 75, 'notes': 'Tricep horseshoe development'},
                    {'name': 'Knuckle Push-ups', 'sets': 4, 'reps': '20', 'rest_seconds': 60, 'notes': 'Wrist conditioning and chest drive'},
                    {'name': 'Neck Bridges / Holds', 'sets': 3, 'reps': '30 sec', 'rest_seconds': 45, 'notes': 'Combat neck thickness'}
                ]},
                {'focus': f"🥩 {t_name}: Feast & Rest Day", 'is_rest': True, 'exercises': []},
                {'focus': f"👹 {t_name}: Hanma Explosive Legs", 'is_rest': False, 'exercises': [
                    {'name': 'Strict Pistol Squats', 'sets': 4, 'reps': '10 per leg', 'rest_seconds': 75, 'notes': 'Unilateral single-leg dominance'},
                    {'name': 'Explosive Jump Squats (Maximum height)', 'sets': 4, 'reps': '15', 'rest_seconds': 60, 'notes': 'Fast-twitch leg spring'},
                    {'name': 'Shrimp Squats', 'sets': 3, 'reps': '8 per leg', 'rest_seconds': 60, 'notes': 'Deep knee stabilization'},
                    {'name': 'Calf Raises on Step', 'sets': 4, 'reps': '30', 'rest_seconds': 45, 'notes': 'Explosive footwork'}
                ]},
                {'focus': f"👹 {t_name}: Grip & Full Body Conditioning", 'is_rest': False, 'exercises': [
                    {'name': 'Towel Hanging Dead Hangs', 'sets': 4, 'reps': '45 sec', 'rest_seconds': 60, 'notes': 'Crushing Hanma grip strength'},
                    {'name': 'Straight Bar Dips', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Chest compression'},
                    {'name': 'Burpees to High Jump', 'sets': 4, 'reps': '12', 'rest_seconds': 60, 'notes': 'Combat stamina'},
                    {'name': 'Hanging Windshield Wipers', 'sets': 3, 'reps': '12', 'rest_seconds': 45, 'notes': 'Rotational core power'}
                ]},
                {'focus': f"👹 {t_name}: Shadow Boxing & Flexibility", 'is_rest': False, 'exercises': [
                    {'name': 'High-Speed Shadow Boxing', 'sets': 5, 'reps': '60 sec', 'rest_seconds': 45, 'notes': 'Fluid combinations and speed'},
                    {'name': 'Diamond Push-ups', 'sets': 3, 'reps': '15', 'rest_seconds': 45, 'notes': 'Tricep finisher'},
                    {'name': 'Full Hanma Splits & Mobility', 'sets': 1, 'reps': '25 mins', 'rest_seconds': 0, 'notes': 'Hip opening and recovery'}
                ]},
                {'focus': f"🥩 {t_name}: Full Recovery Rest Day", 'is_rest': True, 'exercises': []}
            ]
        else:
            split_days = [
                {'focus': f"👹 {t_name}: Demon Back Pull (Deadlifts & Rows)", 'is_rest': False, 'exercises': [
                    {'name': 'Heavy Barbell Deadlifts', 'sets': 4, 'reps': '5', 'rest_seconds': 150, 'notes': 'Spinal erector and posterior chain density'},
                    {'name': 'Weighted Wide-Grip Pull-ups', 'sets': 4, 'reps': '8-10', 'rest_seconds': 90, 'notes': 'Demon back lat flare'},
                    {'name': 'Bent-over Barbell Rows', 'sets': 4, 'reps': '8', 'rest_seconds': 90, 'notes': 'Mid-back thickness'},
                    {'name': 'Heavy Dumbbell Shrugs', 'sets': 4, 'reps': '15', 'rest_seconds': 60, 'notes': 'Ogre neck and upper traps'}
                ]},
                {'focus': f"👹 {t_name}: Heavy Chest & Shoulder Striking Mass", 'is_rest': False, 'exercises': [
                    {'name': 'Barbell Bench Press', 'sets': 4, 'reps': '6-8', 'rest_seconds': 120, 'notes': 'Heavy compound chest pressing'},
                    {'name': 'Overhead Barbell Press', 'sets': 4, 'reps': '6-8', 'rest_seconds': 90, 'notes': 'Deltoid shoulder mass'},
                    {'name': 'Incline Dumbbell Press', 'sets': 3, 'reps': '10', 'rest_seconds': 75, 'notes': 'Upper chest development'},
                    {'name': 'Dips (Weighted)', 'sets': 3, 'reps': '10', 'rest_seconds': 75, 'notes': 'Tricep and lower chest lockout'}
                ]},
                {'focus': f"🥩 {t_name}: Rest & Muscle Synthesis", 'is_rest': True, 'exercises': []},
                {'focus': f"👹 {t_name}: Hanma Quad & Glute Power", 'is_rest': False, 'exercises': [
                    {'name': 'Barbell Back Squats', 'sets': 4, 'reps': '6-8', 'rest_seconds': 120, 'notes': 'Deep rock-bottom depth'},
                    {'name': 'Leg Press Machine', 'sets': 3, 'reps': '12', 'rest_seconds': 90, 'notes': 'Quad hypertrophy burnout'},
                    {'name': 'Romanian Deadlifts', 'sets': 3, 'reps': '10', 'rest_seconds': 75, 'notes': 'Hamstring flexor control'},
                    {'name': 'Standing Calf Raises', 'sets': 4, 'reps': '20', 'rest_seconds': 45, 'notes': 'Ankle stiffness'}
                ]},
                {'focus': f"👹 {t_name}: Hanma Arms & Grip Domination", 'is_rest': False, 'exercises': [
                    {'name': 'EZ-Bar Bicep Curls', 'sets': 4, 'reps': '8-10', 'rest_seconds': 60, 'notes': 'Bicep peak'},
                    {'name': 'Close-Grip Bench Press / Dips', 'sets': 4, 'reps': '8-10', 'rest_seconds': 75, 'notes': 'Tricep power'},
                    {'name': 'Farmer Carries / Heavy Holds', 'sets': 4, 'reps': '45 sec', 'rest_seconds': 60, 'notes': 'Forearm and grip density'},
                    {'name': 'Hanging Leg Raises', 'sets': 4, 'reps': '12', 'rest_seconds': 45, 'notes': 'Abdominal wall compression'}
                ]},
                {'focus': f"👹 {t_name}: Combat Conditioning & Power Sprints", 'is_rest': False, 'exercises': [
                    {'name': 'Incline Treadmill Sprints', 'sets': 5, 'reps': '30s sprint', 'rest_seconds': 60, 'notes': 'High-intensity conditioning'},
                    {'name': 'Kettlebell Swings', 'sets': 3, 'reps': '20', 'rest_seconds': 60, 'notes': 'Explosive hip drive'},
                    {'name': 'Heavy Bag / Shadow Boxing', 'sets': 3, 'reps': '3 mins', 'rest_seconds': 60, 'notes': 'Combat stamina'}
                ]},
                {'focus': f"🥩 {t_name}: Full Recovery Rest Day", 'is_rest': True, 'exercises': []}
            ]

    # 4. TOJI FUSHIGURO / HEAVENLY RESTRICTION PROTOCOL
    elif 'toji' in t_lower or 'fushiguro' in t_lower or 'heavenly restriction' in t_lower:
        split_days = [
            {'focus': f"⚔️ {t_name}: Zero Cursed Energy Heavy Compounds", 'is_rest': False, 'exercises': [
                {'name': 'Barbell Deadlifts / Heavy Pull-ups', 'sets': 4, 'reps': '5-6', 'rest_seconds': 120, 'notes': 'Raw physical posterior chain strength'},
                {'name': 'Overhead Barbell / Dumbbell Press', 'sets': 4, 'reps': '8', 'rest_seconds': 90, 'notes': 'Boulder shoulder pressing power'},
                {'name': 'Weighted Dips / Push-ups', 'sets': 4, 'reps': '10-12', 'rest_seconds': 75, 'notes': 'Tricep & chest pushing force'},
                {'name': 'Dragon Flags / Hanging Leg Raises', 'sets': 3, 'reps': '10', 'rest_seconds': 60, 'notes': 'Midline athletic brace'}
            ]},
            {'focus': f"⚔️ {t_name}: Sorcerer Hunter Agility & Speed", 'is_rest': False, 'exercises': [
                {'name': 'Explosive Box Jumps / Jump Squats', 'sets': 4, 'reps': '8', 'rest_seconds': 75, 'notes': 'Instantaneous acceleration leap'},
                {'name': 'Barbell Power Cleans / DB Snatches', 'sets': 4, 'reps': '5', 'rest_seconds': 90, 'notes': 'Triple extension explosive speed'},
                {'name': 'Bulgarian Split Squats', 'sets': 3, 'reps': '10 per leg', 'rest_seconds': 60, 'notes': 'Single-leg balance and agility'},
                {'name': 'Single-Leg Calf Hops', 'sets': 4, 'reps': '20 per leg', 'rest_seconds': 45, 'notes': 'Reactive footwork'}
            ]},
            {'focus': f"🛌 {t_name}: Rest & Combat Recovery", 'is_rest': True, 'exercises': []},
            {'focus': f"⚔️ {t_name}: Heavy Upper Body Density", 'is_rest': False, 'exercises': [
                {'name': 'Barbell Bench Press / Floor Press', 'sets': 4, 'reps': '6-8', 'rest_seconds': 90, 'notes': 'Dense upper torso armour'},
                {'name': 'Heavy Barbell Rows / Towel Rows', 'sets': 4, 'reps': '8-10', 'rest_seconds': 75, 'notes': 'Upper back & lat thickness'},
                {'name': 'Lateral Deltoid Raises', 'sets': 3, 'reps': '15', 'rest_seconds': 60, 'notes': 'Shoulder width'},
                {'name': 'Farmer Carries', 'sets': 3, 'reps': '45 sec', 'rest_seconds': 60, 'notes': 'Weapon grip endurance'}
            ]},
            {'focus': f"⚔️ {t_name}: Raw Physical Power Legs", 'is_rest': False, 'exercises': [
                {'name': 'Barbell Back Squats / Pistol Squats', 'sets': 4, 'reps': '6-8', 'rest_seconds': 120, 'notes': 'Absolute lower body drive'},
                {'name': 'Romanian Deadlifts', 'sets': 3, 'reps': '10', 'rest_seconds': 75, 'notes': 'Hamstring flexor strength'},
                {'name': 'Walking Lunges', 'sets': 3, 'reps': '12 per leg', 'rest_seconds': 60, 'notes': 'Dynamic stability'},
                {'name': 'Hanging Windshield Wipers', 'sets': 3, 'reps': '10', 'rest_seconds': 45, 'notes': 'Rotational core'}
            ]},
            {'focus': f"⚔️ {t_name}: Tactical Conditioning & Sprints", 'is_rest': False, 'exercises': [
                {'name': 'High-Intensity Sprint Intervals', 'sets': 6, 'reps': '20s sprint / 40s rest', 'rest_seconds': 40, 'notes': 'Maximum acceleration'},
                {'name': 'Burpees to Pull-up', 'sets': 3, 'reps': '10', 'rest_seconds': 60, 'notes': 'Full-body work capacity'},
                {'name': 'Full Body Mobility Flow', 'sets': 1, 'reps': '20 mins', 'rest_seconds': 0, 'notes': 'Joint longevity'}
            ]},
            {'focus': f"🛌 {t_name}: Full Recovery Rest Day", 'is_rest': True, 'exercises': []}
        ]

    # 5. SAITAMA / ONE PUNCH MAN PROTOCOL
    elif 'saitama' in t_lower or 'one punch' in t_lower:
        split_days = [
            {'focus': f"👊 {t_name}: 100x Daily Foundation (Push)", 'is_rest': False, 'exercises': [
                {'name': 'Push-ups (Standard / Diamond / Incline)', 'sets': 4, 'reps': '25', 'rest_seconds': 60, 'notes': '100 total pushups target'},
                {'name': 'Pike Push-ups', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Shoulder pressing power'},
                {'name': 'Chair / Parallel Dips', 'sets': 3, 'reps': '15', 'rest_seconds': 60, 'notes': 'Tricep lockout'},
                {'name': 'Plank Hold', 'sets': 3, 'reps': '60 sec', 'rest_seconds': 45, 'notes': 'Solid core base'}
            ]},
            {'focus': f"👊 {t_name}: 100x Daily Core & Back", 'is_rest': False, 'exercises': [
                {'name': 'Abdominal Sit-ups / Crunches', 'sets': 4, 'reps': '25', 'rest_seconds': 45, 'notes': '100 total situps target'},
                {'name': 'Pull-ups / Inverted Towel Rows', 'sets': 4, 'reps': '10-12', 'rest_seconds': 75, 'notes': 'Back pulling foundation'},
                {'name': 'Superman Extensions', 'sets': 3, 'reps': '15', 'rest_seconds': 45, 'notes': 'Spinal erectors'},
                {'name': 'Bicycle Crunches', 'sets': 3, 'reps': '25', 'rest_seconds': 45, 'notes': 'Oblique endurance'}
            ]},
            {'focus': f"🍌 {t_name}: Banana Breakfast Rest Day", 'is_rest': True, 'exercises': []},
            {'focus': f"👊 {t_name}: 100x Daily Squats & Legs", 'is_rest': False, 'exercises': [
                {'name': 'Bodyweight Squats (Deep form)', 'sets': 4, 'reps': '25', 'rest_seconds': 60, 'notes': '100 total squats target'},
                {'name': 'Bulgarian Split Squats', 'sets': 3, 'reps': '12 per leg', 'rest_seconds': 60, 'notes': 'Single-leg strength'},
                {'name': 'Jump Squats', 'sets': 3, 'reps': '15', 'rest_seconds': 60, 'notes': 'Fast-twitch explosion'},
                {'name': 'Calf Raises', 'sets': 4, 'reps': '25', 'rest_seconds': 45, 'notes': 'Running endurance'}
            ]},
            {'focus': f"👊 {t_name}: 10KM Conditioning Run Trial", 'is_rest': False, 'exercises': [
                {'name': 'Continuous Distance Run / Interval Cardio', 'sets': 1, 'reps': '5-10 km (or 35-50 mins)', 'rest_seconds': 0, 'notes': '10km daily run target'},
                {'name': 'High-Knee Sprint Burpees', 'sets': 4, 'reps': '30 sec', 'rest_seconds': 45, 'notes': 'Aerobic power'},
                {'name': 'Hollow Body Hold', 'sets': 3, 'reps': '45 sec', 'rest_seconds': 45, 'notes': 'Core stabilization'}
            ]},
            {'focus': f"👊 {t_name}: Serious Series Full Body Mastery", 'is_rest': False, 'exercises': [
                {'name': 'Explosive Push-ups', 'sets': 4, 'reps': '15', 'rest_seconds': 60, 'notes': 'Serious punch velocity'},
                {'name': 'Pull-ups', 'sets': 4, 'reps': '10', 'rest_seconds': 60, 'notes': 'Back power'},
                {'name': 'Pistol Squats / Deep Squats', 'sets': 3, 'reps': '10 per leg', 'rest_seconds': 60, 'notes': 'Leg power'},
                {'name': 'Full Body Mobility Flow', 'sets': 1, 'reps': '20 mins', 'rest_seconds': 0, 'notes': 'Muscle relaxation'}
            ]},
            {'focus': f"🍌 {t_name}: Full Recovery Rest Day", 'is_rest': True, 'exercises': []}
        ]

    # 6. UNIVERSAL / CUSTOM / PHOTO BUILD SPLIT
    else:
        if is_calisthenics:
            split_days = [
                {'focus': f"⚔️ {t_name}: Bar Mastery & Explosive Pull", 'is_rest': False, 'exercises': [
                    {'name': 'Strict Pull-ups', 'sets': 4, 'reps': '8-10', 'rest_seconds': 75, 'notes': 'Upper body pulling strength'},
                    {'name': 'Chin-ups / L-Sit Chin-ups', 'sets': 3, 'reps': '8', 'rest_seconds': 75, 'notes': 'Bicep & lat pulling power'},
                    {'name': 'Dragon Flags / Hanging Leg Raises', 'sets': 3, 'reps': '10', 'rest_seconds': 60, 'notes': 'Advanced gymnastic core'},
                    {'name': 'Doorframe / Towel Inverted Rows', 'sets': 3, 'reps': '12', 'rest_seconds': 60, 'notes': 'Scapular retraction'}
                ]},
                {'focus': f"⚔️ {t_name}: Calisthenics Push & Dips", 'is_rest': False, 'exercises': [
                    {'name': 'Parallel Bar Dips', 'sets': 4, 'reps': '12', 'rest_seconds': 75, 'notes': 'Tricep and lower chest power'},
                    {'name': 'Handstand Push-ups / Pike Push-ups', 'sets': 4, 'reps': '8', 'rest_seconds': 75, 'notes': 'Vertical deltoid pressing'},
                    {'name': 'Archer Push-ups', 'sets': 3, 'reps': '8 per arm', 'rest_seconds': 60, 'notes': 'Unilateral chest strength'},
                    {'name': 'Pseudo Planche Push-ups', 'sets': 3, 'reps': '10', 'rest_seconds': 60, 'notes': 'Scapula protraction & shoulder mass'}
                ]},
                {'focus': f"🛌 {t_name}: Active Recovery & Mobility Flow", 'is_rest': True, 'exercises': []},
                {'focus': f"⚔️ {t_name}: Single-Leg Calisthenics & Explosiveness", 'is_rest': False, 'exercises': [
                    {'name': 'Strict Pistol Squats', 'sets': 4, 'reps': '8 per leg', 'rest_seconds': 75, 'notes': 'Single-leg quad and balance mastery'},
                    {'name': 'Explosive Jump Squats', 'sets': 4, 'reps': '12', 'rest_seconds': 60, 'notes': 'Explosive leg power'},
                    {'name': 'Shrimp Squats / Single-Leg Glute Bridges', 'sets': 3, 'reps': '10 per leg', 'rest_seconds': 60, 'notes': 'Posterior chain stability'},
                    {'name': 'Elevated Calf Raises', 'sets': 4, 'reps': '20', 'rest_seconds': 45, 'notes': 'Ankle reflex power'}
                ]},
                {'focus': f"⚔️ {t_name}: Full Body Bar Flow & Conditioning", 'is_rest': False, 'exercises': [
                    {'name': 'Straight Bar Dips', 'sets': 3, 'reps': '10', 'rest_seconds': 75, 'notes': 'Bar transition power'},
                    {'name': 'Typewriter Pull-ups', 'sets': 3, 'reps': '6 per side', 'rest_seconds': 75, 'notes': 'Lat symmetry & control'},
                    {'name': 'Burpees to Pull-up', 'sets': 3, 'reps': '10', 'rest_seconds': 60, 'notes': 'Combat conditioning'},
                    {'name': 'Hollow Body Hold', 'sets': 3, 'reps': '45 sec', 'rest_seconds': 45, 'notes': 'Solid gymnastics midline'}
                ]},
                {'focus': f"⚔️ {t_name}: Core Mastery & Stretch", 'is_rest': False, 'exercises': [
                    {'name': 'Hanging Windshield Wipers', 'sets': 3, 'reps': '10', 'rest_seconds': 60, 'notes': 'Oblique and abdominal rotational control'},
                    {'name': 'L-Sit Hold', 'sets': 3, 'reps': '30 sec', 'rest_seconds': 45, 'notes': 'Hip flexor & core compression'},
                    {'name': 'Full Body Mobility & Bridge Flow', 'sets': 1, 'reps': '20 mins', 'rest_seconds': 0, 'notes': 'Flexibility and joint longevity'}
                ]},
                {'focus': f"🛌 {t_name}: Rest & Growth Day", 'is_rest': True, 'exercises': []}
            ]
        elif is_home:
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
