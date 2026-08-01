"""
Solo Leveling Fitness - AI Physique Analyzer (Google Gemini version)
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
                         image_path: Optional[str]) -> list:
        """Build the multimodal contents list: optional image + text prompt"""
        if target_name:
            target_desc = target_name
        else:
            target_desc = "the person shown in the attached image"

        prompt_text = MASTER_PROMPT_TEMPLATE.format(target=target_desc)

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
                          image_path: Optional[str] = None) -> Dict:
        """
        Generate a Quest Log by analyzing a named character/person or an
        uploaded photo. Exactly one of target_name / image_path should be
        provided (an image takes priority if both are given).
        """
        if not target_name and not image_path:
            return {
                'success': False,
                'error': 'Provide either a character/person name or upload a photo.'
            }

        if not self.is_configured():
            return {
                'success': False,
                'error': (
                    'AI analysis is not configured. Set the GEMINI_API_KEY '
                    'environment variable and install the "google-genai" package '
                    '(pip install google-genai) to enable this feature.'
                ),
                'setup_required': True
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
