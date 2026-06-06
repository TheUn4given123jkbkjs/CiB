from typing import Dict, List, Any
import json

try:
    from .tree import StoryNode
    from .utils import generate_id, call_llm, parse_json_response
except ImportError:
    from tree import StoryNode
    from utils import generate_id, call_llm, parse_json_response

class VisualSemanticCompiler:
    """
    Stage 6: Visual Semantic compilation.
    Compiles stable visual invariant profiles for characters and locations
    and generates segment mood/theme mappings.
    """
    def __init__(self):
        pass

    def _collect_segment_ids(self, node: StoryNode) -> List[str]:
        """Helper to collect structural segment IDs (acts, sequences, scenes)."""
        ids = [node.id]
        for child in node.children:
            ids.extend(self._collect_segment_ids(child))
        return ids

    def _collect_all_text(self, node: StoryNode) -> str:
        """Helper to recursively collect all text from the tree."""
        text = ""
        if node.type == "scene":
            text += " " + " ".join([b["description"] for b in node.beats])
        else:
            for child in node.children:
                text += " " + self._collect_all_text(child)
        return text

    def compile_visual_layer(self, tree: StoryNode, relationship_graph: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gathers stable physical description invariants and maps moods across tree nodes.
        Reuses character IDs from the relationship graph to maintain consistency.
        """
        all_text = self._collect_all_text(tree)
        
        # Format character list from relationship_graph to align IDs
        char_ids_names = []
        for char in relationship_graph.get("nodes", []):
            char_ids_names.append(f"- ID: {char['id']}, Name: {char['name']}")
        char_context = "\n".join(char_ids_names) if char_ids_names else "None identified."

        system_instruction = (
            "You are a visual design consultant for films. Extract stable visual invariant profiles for characters "
            "and locations. "
            "CRITICAL: Do NOT suggest camera angles, shot composition, shot framing, lenses, cinematic lighting setups, or edit/transition decisions. Only compile factual appearance invariants from the text. "
            "Return ONLY a valid JSON object matching the requested schema."
        )
        
        prompt = f"""
        Analyze the story text and identify setting locations and character visual descriptions.
        Compile a stable, invariant visual profile for each location and character.
        
        Character Reference Catalog (You MUST use these exact IDs for character profiles):
        {char_context}
        
        Story text:
        ---
        {all_text}
        ---
        
        Return a JSON object with this structure:
        {{
          "stable_character_profiles": [
            {{
              "id": "char_id_from_catalog",
              "name": "Character Name",
              "visual_invariants": {{
                "gender_age_ethnicity": "gender, age, ethnicity (e.g. young man)",
                "face_features": "facial descriptions like eyes, hair style/color, scars",
                "body_build": "physical stature, build, height",
                "clothing_style": "explicit description of outfit, clothing styles mentioned"
              }}
            }}
          ],
          "stable_location_profiles": [
            {{
              "id": "loc_id",
              "name": "Location Name",
              "visual_invariants": "stable setting description details"
            }}
          ]
        }}
        """
        
        response_json = call_llm(prompt, system_instruction=system_instruction, json_mode=True)
        
        try:
            data = parse_json_response(response_json)
        except Exception as e:
            print(f"[Visual Profiles Fallback] Error: {e}", flush=True)
            data = {
                "stable_character_profiles": [],
                "stable_location_profiles": []
            }

        # Map themes and moods to tree segments
        segment_ids = self._collect_segment_ids(tree)
        mood_theme_map = []
        for seg_id in segment_ids:
            mood_theme_map.append({
                "segment_id": seg_id,
                "primary_mood": "mysterious",
                "primary_theme": "discovery"
            })

        return {
            "stable_character_profiles": data.get("stable_character_profiles", []),
            "stable_location_profiles": data.get("stable_location_profiles", []),
            "mood_theme_map": mood_theme_map
        }
