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
    Compiles stable visual invariant profiles for characters and locations,
    and generates dynamic, batched mood and theme maps across segments.
    """
    def __init__(self):
        pass

    def _collect_all_text(self, node: StoryNode) -> str:
        """Helper to recursively collect all text from the tree."""
        text = ""
        if node.type == "scene":
            text += " " + " ".join([b["description"] for b in node.beats])
        else:
            for child in node.children:
                text += " " + self._collect_all_text(child)
        return text

    def _collect_scenes_info(self, node: StoryNode) -> List[Dict[str, str]]:
        """Helper to collect scene titles and summaries for batched analysis."""
        scenes = []
        def traverse(n):
            if n.type == "scene":
                scenes.append({"id": n.id, "title": n.title, "summary": n.summary or "No summary."})
            for child in n.children:
                traverse(child)
        traverse(node)
        return scenes

    def _collect_all_segment_ids(self, node: StoryNode) -> List[str]:
        """Helper to collect all segment IDs from the tree recursively."""
        ids = [node.id]
        for child in node.children:
            ids.extend(self._collect_all_segment_ids(child))
        return ids

    def compile_visual_layer(self, tree: StoryNode, entity_registry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gathers stable physical description invariants and maps moods across tree nodes.
        Reuses character and location IDs from the Entity Registry to maintain consistency.
        """
        all_text = self._collect_all_text(tree)
        
        # Format character list from registry to align IDs
        characters = list(entity_registry.get("characters", {}).values())
        char_ids_names = [f"- ID: {char['id']}, Name: {char['name']}" for char in characters]
        char_context = "\n".join(char_ids_names) if char_ids_names else "None."

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
                "gender_age_ethnicity": "gender, age, ethnicity",
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

        # Filter visual profiles to ensure canonical IDs are used
        cleaned_chars = []
        for c in data.get("stable_character_profiles", []):
            cid = c.get("id")
            if cid in entity_registry.get("characters", {}):
                cleaned_chars.append(c)

        cleaned_locs = []
        for l in data.get("stable_location_profiles", []):
            lid = l.get("id")
            # Enforce loc_ prefix prefixing
            if lid and not lid.startswith("loc_"):
                lid = "loc_" + lid
            if lid in entity_registry.get("locations", {}):
                l["id"] = lid
                cleaned_locs.append(l)

        # Batch analyze segment mood and theme dynamically
        scenes_info = self._collect_scenes_info(tree)
        mood_theme_map = []
        
        if scenes_info:
            system_instruction_mood = (
                "You are an atmosphere and thematic consultant for films. Analyze scene summaries and determine their primary mood and theme. "
                "Return ONLY a valid JSON object matching the requested schema."
            )
            
            prompt_mood = f"""
            Identify the primary mood (e.g. tense, action-packed, quiet, mysterious) and primary theme (e.g. conflict, discovery, power, survival) for each scene.
            
            CRITICAL SAVING RULE:
            1. Minify keys: 'mt' (mood_theme_map), 'id' (segment_id), 'm' (primary_mood), 't' (primary_theme).
            
            Scenes:
            {json.dumps(scenes_info, ensure_ascii=False, indent=2)}
            
            Return a JSON object with this EXACT structure (using minified keys):
            {{
              "mt": [
                {{
                  "id": "scene_id",
                  "m": "mood description",
                  "t": "theme description"
                }}
              ]
            }}
            """
            
            response_json_mood = call_llm(prompt_mood, system_instruction=system_instruction_mood, json_mode=True)
            try:
                data_mood = parse_json_response(response_json_mood)
                raw_map = data_mood.get("mt", data_mood.get("mood_theme_map", []))
                mood_theme_map = []
                for item in raw_map:
                    mood_theme_map.append({
                        "segment_id": item.get("id", item.get("segment_id")),
                        "primary_mood": item.get("m", item.get("primary_mood", "mysterious")),
                        "primary_theme": item.get("t", item.get("primary_theme", "discovery"))
                    })
            except Exception as e:
                print(f"[Mood Theme Extraction Failed] Error: {e}", flush=True)
                mood_theme_map = []
                for s in scenes_info:
                    mood_theme_map.append({
                        "segment_id": s["id"],
                        "primary_mood": "mysterious",
                        "primary_theme": "discovery"
                    })

        # Propagate scene mood/theme to parent segments (acts and sequences) for tree coverage
        scene_moods = {item["segment_id"]: item for item in mood_theme_map}
        all_segment_ids = self._collect_all_segment_ids(tree)
        
        final_mood_theme_map = []
        for seg_id in all_segment_ids:
            if seg_id in scene_moods:
                final_mood_theme_map.append(scene_moods[seg_id])
            else:
                # Find the first child scene's mood/theme as fallback for acts/sequences
                fallback_mood = "mysterious"
                fallback_theme = "discovery"
                
                # Check scenes in tree descendant path
                descendants = []
                def collect_descendants(node_id, current_node):
                    if current_node.id == node_id:
                        # Collect all child scene ids
                        def harvest_scenes(n):
                            if n.type == "scene":
                                descendants.append(n.id)
                            for c in n.children:
                                harvest_scenes(c)
                        harvest_scenes(current_node)
                        return True
                    for c in current_node.children:
                        if collect_descendants(node_id, c):
                            return True
                    return False
                
                collect_descendants(seg_id, tree)
                for d_id in descendants:
                    if d_id in scene_moods:
                        fallback_mood = scene_moods[d_id]["primary_mood"]
                        fallback_theme = scene_moods[d_id]["primary_theme"]
                        break
                        
                final_mood_theme_map.append({
                    "segment_id": seg_id,
                    "primary_mood": fallback_mood,
                    "primary_theme": fallback_theme
                })

        return {
            "stable_character_profiles": cleaned_chars,
            "stable_location_profiles": cleaned_locs,
            "mood_theme_map": final_mood_theme_map
        }
