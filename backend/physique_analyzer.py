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
                         current_body_type: Optional[str] = None) -> list:
        """Build the multimodal contents list: optional image + text prompt"""
        if target_name:
            target_desc = target_name
        else:
            target_desc = "the person shown in the attached image"

        prompt_text = MASTER_PROMPT_TEMPLATE.format(target=target_desc)

        if current_body_type:
            enriched_baseline = enrich_body_type(current_body_type)
            prompt_text += f"\n\nCRITICAL ADAPTIVE CONTEXT: The client's current physical baseline is: **{enriched_baseline}** ({current_body_type.upper()}). Please tailor the exercise selection, volume, and cardio recommendations to optimize results for this specific baseline as they transform into {target_desc}."

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
                          current_body_type: Optional[str] = None) -> Dict:
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
            contents = self._build_contents(target_name, image_path)

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

    def generate_weekly_workout_json(self, 
                                     body_type: str, 
                                     days_per_week: int = 5, 
                                     equipment: str = "Full Commercial Gym", 
                                     injuries: str = "None") -> Dict:
        """
        Generate a weekly workout plan strictly following the Backend Fitness Programming Engine schema.
        
        STRICT OUTPUT FORMATTING:
        Valid JSON payload matching:
        {
          "program_overview": "A 1-sentence summary of the program focus based on the body type",
          "weekly_schedule": [
            {
              "day_number": 1,
              "muscle_focus": "e.g., Push / Pull / Legs / Full Body / Rest",
              "routine": [
                {
                  "exercise_name": "Exact name of movement",
                  "sets": 3,
                  "reps": "8-12",
                  "rest_seconds": 90,
                  "form_cue": "1 short sentence on form or alternative modification"
                }
              ]
            }
          ]
        }
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
1. Baseline Alignment: You must tailor the exercise selection strictly to the user's physical baseline. If the profile dictates low joint tolerance (e.g., overweight), do not prescribe high-impact plyometrics or heavy spinal loading. If the profile indicates low muscle mass and fast metabolism, prioritize heavy compound lifts with adequate recovery.
2. Volume and Intensity: Modulate the set/rep schemes to match the user's implied recovery capacity. Do not prescribe advanced split routines to absolute beginners.
3. Realistic Progression: Every exercise must include actionable rest periods and rep ranges.

STRICT OUTPUT FORMATTING:
You are a data API. You must output the requested workout plan STRICTLY as a valid JSON object. Do not output any conversational text, introductory greetings, markdown formatting outside of the JSON block, or medical disclaimers. Any output other than raw JSON will break the application architecture.

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
        Generate deterministic fallback program adhering strictly to the JSON schema:
        {
          "program_overview": "...",
          "weekly_schedule": [...]
        }
        """
        bt = str(body_type).lower()
        if 'overweight' in enriched_baseline.lower() or 'joint' in enriched_baseline.lower() or 'endo' in bt:
            overview = "Joint-friendly low-impact program focused on fat loss, metabolic conditioning, and knee protection."
            schedule = [
                {
                    "day_number": 1,
                    "muscle_focus": "Lower Body (Joint-Friendly)",
                    "routine": [
                        {"exercise_name": "Box Squats", "sets": 4, "reps": "12-15", "rest_seconds": 60, "form_cue": "Sit back onto box to reduce patellar knee stress."},
                        {"exercise_name": "Glute Bridges", "sets": 3, "reps": "15", "rest_seconds": 60, "form_cue": "Squeeze glutes at top without hyperextending lower back."}
                    ]
                },
                {
                    "day_number": 2,
                    "muscle_focus": "Upper Body Push & Pull",
                    "routine": [
                        {"exercise_name": "Incline Push-Ups", "sets": 3, "reps": "12-15", "rest_seconds": 60, "form_cue": "Maintain rigid core alignment throughout set."},
                        {"exercise_name": "Seated Lat Pulldowns", "sets": 4, "reps": "12", "rest_seconds": 60, "form_cue": "Pull with elbows down towards chest."}
                    ]
                },
                {
                    "day_number": 3,
                    "muscle_focus": "Active Recovery / Low-Impact Cardio",
                    "routine": [
                        {"exercise_name": "Stationary Cycling / Incline Walking", "sets": 1, "reps": "30 mins", "rest_seconds": 0, "form_cue": "Keep steady conversational pace to maximize fat oxidation."}
                    ]
                },
                {
                    "day_number": 4,
                    "muscle_focus": "Full Body Conditioning",
                    "routine": [
                        {"exercise_name": "Step-ups on Low Box", "sets": 3, "reps": "10 per leg", "rest_seconds": 60, "form_cue": "Drive through front heel, avoid pushing off back toe."},
                        {"exercise_name": "Standing Overhead Cable / Band Press", "sets": 3, "reps": "12", "rest_seconds": 60, "form_cue": "Press vertically while bracing abdominal wall."}
                    ]
                },
                {
                    "day_number": 5,
                    "muscle_focus": "Rest & Mobility",
                    "routine": [
                        {"exercise_name": "Dynamic Hip & Hamstring Mobility Stretch", "sets": 1, "reps": "20 mins", "rest_seconds": 0, "form_cue": "Breathe deeply into stretches without bouncing."}
                    ]
                }
            ]
        elif 'fast metabolism' in enriched_baseline.lower() or 'ecto' in bt or 'skinny' in bt or 'lean' in bt:
            overview = "High-yield compound hypertrophy program designed to maximize muscle mass and preserve energy."
            schedule = [
                {
                    "day_number": 1,
                    "muscle_focus": "Lower Body Power",
                    "routine": [
                        {"exercise_name": "Barbell / Heavy Goblet Squats", "sets": 4, "reps": "6-8", "rest_seconds": 120, "form_cue": "Break parallel with chest high and knees tracking toes."},
                        {"exercise_name": "Romanian Deadlifts", "sets": 4, "reps": "8-10", "rest_seconds": 90, "form_cue": "Hinge at hips with flat back until stretch in hamstrings."}
                    ]
                },
                {
                    "day_number": 2,
                    "muscle_focus": "Upper Body Heavy Compounds",
                    "routine": [
                        {"exercise_name": "Flat Bench Press", "sets": 4, "reps": "6-8", "rest_seconds": 120, "form_cue": "Tuck elbows slightly and touch lower sternum."},
                        {"exercise_name": "Weighted Pull-ups", "sets": 4, "reps": "6-8", "rest_seconds": 120, "form_cue": "Full extension at bottom, pull chin over bar."}
                    ]
                },
                {
                    "day_number": 3,
                    "muscle_focus": "Rest & Hypertrophy Recovery",
                    "routine": [
                        {"exercise_name": "Caloric Surplus Rest & Recovery", "sets": 0, "reps": "Rest", "rest_seconds": 0, "form_cue": "Prioritize sleep and protein intake."}
                    ]
                },
                {
                    "day_number": 4,
                    "muscle_focus": "Shoulders & Back Hypertrophy",
                    "routine": [
                        {"exercise_name": "Overhead Barbell Press", "sets": 4, "reps": "6-8", "rest_seconds": 120, "form_cue": "Squeeze glutes and press overhead without leaning back."},
                        {"exercise_name": "Bent-over Dumbbell Rows", "sets": 4, "reps": "8", "rest_seconds": 90, "form_cue": "Pull dumbbell to hip, squeezing lats."}
                    ]
                },
                {
                    "day_number": 5,
                    "muscle_focus": "Arms & Core Accessory",
                    "routine": [
                        {"exercise_name": "Incline Dumbbell Bicep Curls", "sets": 3, "reps": "10-12", "rest_seconds": 90, "form_cue": "Keep upper arms stationary and isolate bicep peak."},
                        {"exercise_name": "Triceps Skullcrushers", "sets": 3, "reps": "10-12", "rest_seconds": 90, "form_cue": "Lower bar towards forehead keeping elbows elbowed."}
                    ]
                }
            ]
        elif 'moderate body fat, low underlying' in enriched_baseline.lower() or 'skinnyfat' in bt or 'skinny_fat' in bt:
            overview = "Body recomposition protocol balancing strength overload with progressive metabolic conditioning."
            schedule = [
                {
                    "day_number": 1,
                    "muscle_focus": "Push / Strength Recomp",
                    "routine": [
                        {"exercise_name": "Barbell Bench Press", "sets": 4, "reps": "8-10", "rest_seconds": 90, "form_cue": "Drive feet into floor and maintain arched upper back."},
                        {"exercise_name": "Standing Overhead Dumbbell Press", "sets": 3, "reps": "10", "rest_seconds": 90, "form_cue": "Lock out shoulders overhead on every rep."}
                    ]
                },
                {
                    "day_number": 2,
                    "muscle_focus": "Pull / Back & Core",
                    "routine": [
                        {"exercise_name": "Barbell Rows", "sets": 4, "reps": "10", "rest_seconds": 90, "form_cue": "Keep torso at 45 degree angle and pull to belly button."},
                        {"exercise_name": "Hanging Leg Raises", "sets": 3, "reps": "12", "rest_seconds": 60, "form_cue": "Raise legs using lower abs without momentum."}
                    ]
                },
                {
                    "day_number": 3,
                    "muscle_focus": "Legs & Recomp Cardio",
                    "routine": [
                        {"exercise_name": "Barbell Back Squats", "sets": 4, "reps": "8-10", "rest_seconds": 90, "form_cue": "Push through middle of foot and keep chest tall."},
                        {"exercise_name": "Kettlebell Swing Finisher", "sets": 3, "reps": "15", "rest_seconds": 60, "form_cue": "Snap hips forward forcefully."}
                    ]
                },
                {
                    "day_number": 4,
                    "muscle_focus": "Rest & Active Walk",
                    "routine": [
                        {"exercise_name": "Brisk Outdoor Walk", "sets": 1, "reps": "40 mins", "rest_seconds": 0, "form_cue": "Promote blood flow and non-exercise physical activity."}
                    ]
                }
            ]
        else:
            overview = "Advanced Push/Pull/Legs volume accumulation program for athletic conditioning and muscle density."
            schedule = [
                {
                    "day_number": 1,
                    "muscle_focus": "Push Split",
                    "routine": [
                        {"exercise_name": "Barbell Bench Press", "sets": 4, "reps": "8-10", "rest_seconds": 90, "form_cue": "Control 2-second eccentric phase."},
                        {"exercise_name": "Incline Dumbbell Press", "sets": 3, "reps": "10-12", "rest_seconds": 75, "form_cue": "Focus on upper chest stretch."}
                    ]
                },
                {
                    "day_number": 2,
                    "muscle_focus": "Pull Split",
                    "routine": [
                        {"exercise_name": "Barbell Deadlifts", "sets": 4, "reps": "6-8", "rest_seconds": 120, "form_cue": "Pull slack out of bar before lifting."},
                        {"exercise_name": "Weighted Pull-ups", "sets": 4, "reps": "8", "rest_seconds": 90, "form_cue": "Drive elbows down to side ribs."}
                    ]
                },
                {
                    "day_number": 3,
                    "muscle_focus": "Legs Split",
                    "routine": [
                        {"exercise_name": "Barbell Back Squats", "sets": 4, "reps": "8-10", "rest_seconds": 90, "form_cue": "Spread floor with feet to engage glutes."},
                        {"exercise_name": "Bulgarian Split Squats", "sets": 3, "reps": "10 per leg", "rest_seconds": 75, "form_cue": "Keep front shin vertical."}
                    ]
                },
                {
                    "day_number": 4,
                    "muscle_focus": "Conditioning & Rest",
                    "routine": [
                        {"exercise_name": "Sprint Intervals", "sets": 5, "reps": "30 sec sprint", "rest_seconds": 60, "form_cue": "Maximum effort output on bike or track."}
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


def parse_weekly_plan_from_markdown(quest_log_markdown: str, target_name: Optional[str] = None) -> list:
    """
    Fallback parser that converts markdown text into a structured 7-day plan
    (Monday through Sunday) when AI JSON extraction is unavailable or fails.
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
        
    t_name = target_name or "Character"
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
        default_splits = [
            {'focus': f'{t_name} Upper Body Power', 'is_rest': False, 'exercises': [{'name': f'{t_name} Push-ups', 'sets': 4, 'reps': '15', 'notes': 'Chest & shoulders'}, {'name': f'{t_name} Pull-ups', 'sets': 3, 'reps': '8', 'notes': 'Back & arms'}, {'name': 'Dips', 'sets': 3, 'reps': '12', 'notes': 'Triceps & chest'}]},
            {'focus': f'{t_name} Lower Body & Legs', 'is_rest': False, 'exercises': [{'name': f'{t_name} Squats', 'sets': 4, 'reps': '20', 'notes': 'Leg power'}, {'name': 'Lunges', 'sets': 3, 'reps': '12', 'notes': 'Quads & glutes'}, {'name': 'Calf Raises', 'sets': 4, 'reps': '20', 'notes': 'Calf endurance'}]},
            {'focus': f'{t_name} Active Recovery', 'is_rest': True, 'exercises': []},
            {'focus': f'{t_name} Core & Agility', 'is_rest': False, 'exercises': [{'name': f'{t_name} Planks', 'sets': 3, 'reps': '60 sec', 'notes': 'Core stability'}, {'name': 'Russian Twists', 'sets': 3, 'reps': '20', 'notes': 'Obliques'}, {'name': 'Mountain Climbers', 'sets': 3, 'reps': '30 sec', 'notes': 'Agility'}]},
            {'focus': f'{t_name} Full Body Conditioning', 'is_rest': False, 'exercises': [{'name': f'{t_name} Burpees', 'sets': 4, 'reps': '10', 'notes': 'Stamina'}, {'name': 'Jumping Jacks', 'sets': 3, 'reps': '30', 'notes': 'Cardio'}, {'name': 'Pike Push-ups', 'sets': 3, 'reps': '10', 'notes': 'Shoulders'}]},
            {'focus': f'{t_name} Master Trial Workout', 'is_rest': False, 'exercises': [{'name': f'{t_name} Diamond Push-ups', 'sets': 3, 'reps': '12', 'notes': 'Tricep focus'}, {'name': 'Jump Squats', 'sets': 3, 'reps': '15', 'notes': 'Explosive legs'}, {'name': 'V-Ups', 'sets': 3, 'reps': '12', 'notes': 'Abs'}]},
            {'focus': f'{t_name} Rest & Reset Day', 'is_rest': True, 'exercises': []}
        ]
        
        for idx in range(7):
            split = default_splits[idx]
            days.append({
                'day_of_week': idx,
                'day_label': day_names[idx],
                'focus': split['focus'],
                'is_rest': split['is_rest'],
                'exercises': split['exercises']
            })
            
    return days


    def generate_weekly_workout_json(self, body_type: str) -> Dict:
        """
        Generate a weekly workout plan strictly as a JSON array tailored to enriched body type.
        
        Strict System Prompt:
        Act as an elite strength and conditioning coach. Generate a weekly workout plan for a new client.
        The client's current physical baseline is: [Insert Enriched Body Type Variable].
        You must tailor the exercise selection, volume, and cardio recommendations to optimize results for this specific baseline.
        Output the routine strictly as a JSON array containing day of the week, exercise name, sets, reps, and rest periods. Do not include introductory text or disclaimers.
        """
        import json
        enriched_baseline = enrich_body_type(body_type)
        
        prompt = f"""Act as an elite strength and conditioning coach. Generate a weekly workout plan for a new client.
The client's current physical baseline is: {enriched_baseline}
You must tailor the exercise selection, volume, and cardio recommendations to optimize results for this specific baseline.
Output the routine strictly as a JSON array containing day of the week, exercise name, sets, reps, and rest periods. Do not include introductory text or disclaimers."""

        if not self.is_configured():
            fallback_routine = self._generate_fallback_json_routine(body_type, enriched_baseline)
            return {
                'success': True,
                'body_type': body_type,
                'enriched_baseline': enriched_baseline,
                'routine': fallback_routine,
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
            
            routine_json = json.loads(clean_text)
            return {
                'success': True,
                'body_type': body_type,
                'enriched_baseline': enriched_baseline,
                'routine': routine_json,
                'is_fallback': False
            }
        except Exception as e:
            fallback_routine = self._generate_fallback_json_routine(body_type, enriched_baseline)
            return {
                'success': True,
                'body_type': body_type,
                'enriched_baseline': enriched_baseline,
                'routine': fallback_routine,
                'is_fallback': True,
                'notice': f'AI generation notice: {str(e)}'
            }

    def _generate_fallback_json_routine(self, body_type: str, enriched_baseline: str) -> list:
        """
        Generate deterministic JSON array fallback routine adhering to enriched body type rules:
        - Lean/Skinny: Hypertrophy, heavy compound lifts, minimal cardio, longer rest periods (90-120s)
        - Skinny-Fat: Body recomposition, progressive overload, moderate metabolic conditioning (60-90s)
        - Overweight: Fat loss, joint-friendly variations (box squats, incline pushups), higher cardio, 60s rest
        - Athletic: Advanced Push/Pull/Legs split, volume accumulation, specialized accessory work
        """
        bt = str(body_type).lower()
        if 'overweight' in enriched_baseline.lower() or 'joint' in enriched_baseline.lower() or 'endo' in bt:
            return [
                {"day_of_week": "Monday", "exercise_name": "Box Squats (Joint-Friendly)", "sets": 4, "reps": "12-15", "rest_period": "60s"},
                {"day_of_week": "Monday", "exercise_name": "Incline Push-Ups", "sets": 3, "reps": "12-15", "rest_period": "60s"},
                {"day_of_week": "Monday", "exercise_name": "Stationary Bike / Incline Walking Cardio", "sets": 1, "reps": "25 mins", "rest_period": "60s"},
                {"day_of_week": "Tuesday", "exercise_name": "Seated Resistance Cable / Band Rows", "sets": 4, "reps": "15", "rest_period": "60s"},
                {"day_of_week": "Tuesday", "exercise_name": "Step-ups on Low Box", "sets": 3, "reps": "12 per leg", "rest_period": "60s"},
                {"day_of_week": "Tuesday", "exercise_name": "Rowing Machine / Low-Impact Cardio", "sets": 1, "reps": "20 mins", "rest_period": "60s"},
                {"day_of_week": "Wednesday", "exercise_name": "Active Recovery Stretch & Mobility", "sets": 1, "reps": "30 mins", "rest_period": "None"},
                {"day_of_week": "Thursday", "exercise_name": "Glute Bridges & Hamstring Curls", "sets": 4, "reps": "15", "rest_period": "60s"},
                {"day_of_week": "Thursday", "exercise_name": "Dumbbell Overhead Press (Seated)", "sets": 3, "reps": "12", "rest_period": "60s"},
                {"day_of_week": "Thursday", "exercise_name": "Water Aerobics / Elliptical Cardio", "sets": 1, "reps": "25 mins", "rest_period": "60s"},
                {"day_of_week": "Friday", "exercise_name": "Wall Sits & Standing Calf Raises", "sets": 3, "reps": "45 sec hold / 20 reps", "rest_period": "60s"},
                {"day_of_week": "Friday", "exercise_name": "Lat Pulldowns / Assisted Pulls", "sets": 4, "reps": "12", "rest_period": "60s"},
                {"day_of_week": "Saturday", "exercise_name": "Brisk Walking & Core Stabilization", "sets": 1, "reps": "35 mins", "rest_period": "60s"},
                {"day_of_week": "Sunday", "exercise_name": "Full Rest & Recovery Day", "sets": 0, "reps": "Rest", "rest_period": "None"}
            ]
        elif 'fast metabolism' in enriched_baseline.lower() or 'ecto' in bt or 'skinny' in bt or 'lean' in bt:
            return [
                {"day_of_week": "Monday", "exercise_name": "Barbell / Heavy Goblet Squats", "sets": 4, "reps": "6-8", "rest_period": "120s"},
                {"day_of_week": "Monday", "exercise_name": "Flat Bench Press", "sets": 4, "reps": "6-8", "rest_period": "120s"},
                {"day_of_week": "Monday", "exercise_name": "Weighted Dips", "sets": 3, "reps": "8-10", "rest_period": "90s"},
                {"day_of_week": "Tuesday", "exercise_name": "Barbell / Heavy Dumbbell Deadlifts", "sets": 4, "reps": "5", "rest_period": "120s"},
                {"day_of_week": "Tuesday", "exercise_name": "Weighted Pull-ups", "sets": 4, "reps": "6-8", "rest_period": "120s"},
                {"day_of_week": "Wednesday", "exercise_name": "Hypertrophy Caloric Rest & Recovery", "sets": 0, "reps": "Rest", "rest_period": "None"},
                {"day_of_week": "Thursday", "exercise_name": "Overhead Shoulder Press", "sets": 4, "reps": "6-8", "rest_period": "120s"},
                {"day_of_week": "Thursday", "exercise_name": "Incline Dumbbell Press", "sets": 3, "reps": "8-10", "rest_period": "90s"},
                {"day_of_week": "Friday", "exercise_name": "Romanian Deadlifts & Hamstring Curls", "sets": 4, "reps": "8-10", "rest_period": "90s"},
                {"day_of_week": "Friday", "exercise_name": "Heavy Dumbbell Rows", "sets": 4, "reps": "8", "rest_period": "90s"},
                {"day_of_week": "Saturday", "exercise_name": "Barbell Bicep Curls & Skullcrushers", "sets": 3, "reps": "10-12", "rest_period": "90s"},
                {"day_of_week": "Sunday", "exercise_name": "Full Muscle Growth Rest Day", "sets": 0, "reps": "Rest", "rest_period": "None"}
            ]
        elif 'moderate body fat, low underlying' in enriched_baseline.lower() or 'skinnyfat' in bt or 'skinny_fat' in bt:
            return [
                {"day_of_week": "Monday", "exercise_name": "Barbell Squats", "sets": 4, "reps": "8-10", "rest_period": "90s"},
                {"day_of_week": "Monday", "exercise_name": "Push-Ups / Bench Press", "sets": 4, "reps": "10-12", "rest_period": "90s"},
                {"day_of_week": "Monday", "exercise_name": "Kettlebell Swing Conditioning", "sets": 3, "reps": "15", "rest_period": "60s"},
                {"day_of_week": "Tuesday", "exercise_name": "Bent-over Barbell Rows", "sets": 4, "reps": "10", "rest_period": "90s"},
                {"day_of_week": "Tuesday", "exercise_name": "Bulgarian Split Squats", "sets": 3, "reps": "10 per leg", "rest_period": "60s"},
                {"day_of_week": "Wednesday", "exercise_name": "Active Recovery Walk & Stretching", "sets": 1, "reps": "30 mins", "rest_period": "None"},
                {"day_of_week": "Thursday", "exercise_name": "Dumbbell Shoulder Press", "sets": 4, "reps": "10", "rest_period": "90s"},
                {"day_of_week": "Thursday", "exercise_name": "Bodyweight Dips & Chin-ups", "sets": 3, "reps": "10", "rest_period": "60s"},
                {"day_of_week": "Friday", "exercise_name": "Romanian Deadlifts", "sets": 4, "reps": "10", "rest_period": "90s"},
                {"day_of_week": "Friday", "exercise_name": "HIIT Bodyweight Circuit", "sets": 4, "reps": "45 sec work", "rest_period": "45s"},
                {"day_of_week": "Saturday", "exercise_name": "Core Recomp (Planks & Russian Twists)", "sets": 4, "reps": "60s hold / 20 reps", "rest_period": "60s"},
                {"day_of_week": "Sunday", "exercise_name": "Recomposition Rest & Recovery Day", "sets": 0, "reps": "Rest", "rest_period": "None"}
            ]
        else:
            return [
                {"day_of_week": "Monday", "exercise_name": "Push: Barbell Bench Press", "sets": 4, "reps": "8-10", "rest_period": "90s"},
                {"day_of_week": "Monday", "exercise_name": "Push: Overhead Dumbbell Press", "sets": 4, "reps": "10", "rest_period": "90s"},
                {"day_of_week": "Monday", "exercise_name": "Push: Incline Chest Flyes & Dips", "sets": 3, "reps": "12", "rest_period": "60s"},
                {"day_of_week": "Tuesday", "exercise_name": "Pull: Barbell Deadlifts", "sets": 4, "reps": "6-8", "rest_period": "120s"},
                {"day_of_week": "Tuesday", "exercise_name": "Pull: Weighted Pull-ups & Cable Rows", "sets": 4, "reps": "8-10", "rest_period": "90s"},
                {"day_of_week": "Wednesday", "exercise_name": "Legs: Barbell Back Squats", "sets": 4, "reps": "8-10", "rest_period": "90s"},
                {"day_of_week": "Wednesday", "exercise_name": "Legs: Romanian Deadlifts & Walking Lunges", "sets": 4, "reps": "10", "rest_period": "90s"},
                {"day_of_week": "Thursday", "exercise_name": "Active Recovery & Mobility Work", "sets": 1, "reps": "30 mins", "rest_period": "None"},
                {"day_of_week": "Friday", "exercise_name": "Hypertrophy Upper Body Accessories", "sets": 4, "reps": "12-15", "rest_period": "60s"},
                {"day_of_week": "Saturday", "exercise_name": "Athletic Conditioning & Sprint Intervals", "sets": 5, "reps": "30s sprint", "rest_period": "60s"},
                {"day_of_week": "Sunday", "exercise_name": "Advanced Athlete Rest & Reset Day", "sets": 0, "reps": "Rest", "rest_period": "None"}
            ]
