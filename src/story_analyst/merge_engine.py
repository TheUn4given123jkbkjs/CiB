from typing import Dict, List, Any, Set
import json
import re

try:
    from .tree import StoryNode
    from .utils import generate_id, call_llm, parse_json_response
except ImportError:
    from tree import StoryNode
    from utils import generate_id, call_llm, parse_json_response

class MergeEngine:
    """
    Stage 1.5: Entity Discovery & Registry Engine.
    Discovers characters, locations, and props directly after parsing,
    de-duplicates them, maps alias lineage, and acts as the Single Source of Truth (SSOT).
    """
    def __init__(self):
        pass

    def build_registry(self, tree: StoryNode) -> Dict[str, Any]:
        """
        Gathers all text from story tree beats and calls LLM to compile
        a de-duplicated Entity Registry with canonical IDs and alias lineages.
        """
        beats = self._collect_all_beats(tree)
        scenes = self._collect_scenes(tree)
        
        # Combine beat descriptions and scene info for extraction context
        text_content = []
        for s in scenes:
            scene_text = f"Scene: {s.title} (Location: {s.primary_location or 'unknown'})\n"
            scene_text += "\n".join([f"- {b['description']}" for b in s.beats])
            text_content.append(scene_text)
            
        full_text = "\n\n".join(text_content)
        
        system_instruction = (
            "You are a script analysis engine. Identify all characters, locations, and props mentioned in the text. "
            "For each entity, determine its canonical name (n), a unique lowercase ID, and a list of all names/nicknames as aliases (a). "
            "Return ONLY a valid JSON object matching the requested schema."
        )
        
        prompt = f"""
        Analyze the following story text and compile a comprehensive, de-duplicated Entity Registry.
        For each entity, extract its canonical name (n), archetype/type (arc/t), and all its name variants as aliases (a).
        
        Story Text:
        ---
        {full_text}
        ---
        
        Return a JSON object with this EXACT structure (using these minified keys):
        {{
          "c": [
            {{
              "id": "char_lowercase_id",
              "n": "Canonical Character Name",
              "a": ["Alias 1", "Alias 2"],
              "arc": "Protagonist|Antagonist|Supporting",
              "t": ["trait 1", "trait 2"]
            }}
          ],
          "l": [
            {{
              "id": "loc_lowercase_id",
              "n": "Canonical Location Name",
              "a": ["Alias 1", "Alias 2"]
            }}
          ],
          "p": [
            {{
              "id": "prop_lowercase_id",
              "n": "Canonical Prop Name",
              "a": ["Alias 1", "Alias 2"],
              "t": "weapon|document|key_item|other",
              "v": "description"
            }}
          ]
        }}
        """
        
        response_json = call_llm(prompt, system_instruction=system_instruction, json_mode=True)
        try:
            data = parse_json_response(response_json)
        except Exception as e:
            print(f"[Entity Registry Discovery Failed] Error: {e}", flush=True)
            data = {"c": [], "l": [], "p": []}

        # Build de-duplicated dicts and alias mapping
        de_duplicated_chars = {}
        de_duplicated_locs = {}
        de_duplicated_props = {}
        alias_map = {} # Maps alias (normalized string) -> canonical ID

        # Process characters
        for char in data.get("c", []):
            cid = char.get("id", "")
            if not cid:
                continue
            if not cid.startswith("char_"):
                cid = "char_" + cid
            de_duplicated_chars[cid] = {
                "id": cid,
                "name": char.get("n", cid),
                "aliases": char.get("a", []),
                "archetype": char.get("arc", "Supporting"),
                "traits": char.get("t", [])
            }
            # Map canonical name and aliases
            alias_map[self._normalize_name(char.get("n", ""))] = cid
            for alias in char.get("a", []):
                alias_map[self._normalize_name(alias)] = cid

        # Process locations
        for loc in data.get("l", []):
            lid = loc.get("id", "")
            if not lid:
                continue
            if not lid.startswith("loc_"):
                lid = "loc_" + lid
            de_duplicated_locs[lid] = {
                "id": lid,
                "name": loc.get("n", lid),
                "aliases": loc.get("a", [])
            }
            alias_map[self._normalize_name(loc.get("n", ""))] = lid
            for alias in loc.get("a", []):
                alias_map[self._normalize_name(alias)] = lid

        # Process props
        for prop in data.get("p", []):
            pid = prop.get("id", "")
            if not prop:
                continue
            if not pid.startswith("prop_"):
                pid = "prop_" + pid
            de_duplicated_props[pid] = {
                "id": pid,
                "name": prop.get("n", pid),
                "aliases": prop.get("a", []),
                "type": prop.get("t", "other"),
                "visual_descriptor": prop.get("v", "")
            }
            alias_map[self._normalize_name(prop.get("n", ""))] = pid
            for alias in prop.get("a", []):
                alias_map[self._normalize_name(alias)] = pid

        return {
            "registry": {
                "characters": de_duplicated_chars,
                "locations": de_duplicated_locs,
                "props": de_duplicated_props
            },
            "alias_map": alias_map
        }

    def extract_story_facts(self, tree: StoryNode) -> List[Dict[str, Any]]:
        """
        Extracts key narrative facts (occupations, positions, alliances, key events/milestones)
        along with their valid_from and valid_to scene/beat ID boundaries from the narrative tree.
        Runs on Local/Standard model route (Registry/Extraction is Local).
        """
        scenes = self._collect_scenes(tree)
        if not scenes:
            return []
            
        scenes_data = []
        for s in scenes:
            scenes_data.append({
                "id": s.id,
                "title": s.title,
                "summary": s.summary or " ".join([b["description"] for b in s.beats])
            })
            
        system_instruction = (
            "You are a script analysis engine. Extract a Story Fact Registry of key narrative facts. "
            "A fact is a concrete statement about characters (status, roles, relationships, occupations), locations (state, accessibility), or props. "
            "For each fact, identify the scene ID or beat ID where it becomes true (valid_from) "
            "and the scene ID or beat ID where it is no longer true (valid_to). "
            "If it remains true throughout the narrative, set valid_to to 'present'. "
            "Return ONLY a valid JSON object matching the requested schema."
        )
        
        prompt = f"""
        Analyze these scene summaries and extract the key facts about characters, locations, or props:
        
        Scenes:
        {json.dumps(scenes_data, ensure_ascii=False, indent=2)}
        
        Return a JSON object with this EXACT structure:
        {{
          "facts": [
            {{
              "fact": "Factual statement (e.g. 'Lý Vân Tiêu là học sinh')",
              "valid_from": "scene_id_where_fact_starts_being_true",
              "valid_to": "scene_id_where_fact_ends_or_present"
            }}
          ]
        }}
        """
        
        response_json = call_llm(prompt, system_instruction=system_instruction, json_mode=True)
        try:
            data = parse_json_response(response_json)
            facts = data.get("facts", [])
            # Validate structure
            cleaned_facts = []
            for item in facts:
                fact_str = item.get("fact", "").strip()
                valid_from = item.get("valid_from", "").strip()
                valid_to = item.get("valid_to", "").strip()
                
                if fact_str and valid_from:
                    cleaned_facts.append({
                        "fact": fact_str,
                        "valid_from": valid_from,
                        "valid_to": valid_to or "present"
                    })
            return cleaned_facts
        except Exception as e:
            print(f"[Story Fact Registry Failed] Error: {e}", flush=True)
            return []

    def resolve_entity(self, alias_map: Dict[str, str], raw_name: str, prefix_default: str) -> str:
        """Resolves a raw name or string to its canonical registry ID using the alias_map."""
        if not raw_name:
            return f"{prefix_default}_unknown"
            
        norm_name = self._normalize_name(raw_name)
        if norm_name in alias_map:
            return alias_map[norm_name]
        
        # Fuzzy match prefix or substring
        for alias, cid in alias_map.items():
            if alias and norm_name and (alias in norm_name or norm_name in alias):
                return cid
                
        # Generate fallback ID if not resolved
        fallback_clean = norm_name.replace("char", "").replace("loc", "").replace("prop", "").strip("_")
        return f"{prefix_default}_{fallback_clean}" if fallback_clean else f"{prefix_default}_unknown"

    def update_tree_with_registry(self, tree: StoryNode, alias_map: Dict[str, str]) -> None:
        """Updates location IDs, source_chunks, and confidences on all Story Tree nodes."""
        scenes = self._collect_scenes(tree)
        for scene in scenes:
            # Resolve primary location using Entity Registry alias_map
            raw_loc = scene.primary_location
            # Strip loc_ prefix if it exists in raw_loc
            if raw_loc and raw_loc.startswith("loc_"):
                raw_loc = raw_loc[4:]
            scene.primary_location = self.resolve_entity(alias_map, raw_loc or "unknown", "loc")
            
            # Setup metadata for v3.1.0 and debug
            scene.source_chunk = getattr(scene, "source_chunk", "chunk_0")
            scene.confidence = getattr(scene, "confidence", 1.0)

    def _normalize_name(self, name: str) -> str:
        """Helper to lowercase and clean name for mapping heuristics."""
        name = name.lower()
        name = re.sub(r'^(char_|loc_|prop_)', '', name)
        name = name.replace("_", " ")
        name = re.sub(r'\b(the|a|an|of|and)\b', '', name)
        return "".join(name.split())

    def _collect_all_beats(self, node: StoryNode) -> List[Dict[str, Any]]:
        """Helper to collect all beats recursively."""
        beats = []
        if node.type == "scene":
            beats.extend(node.beats)
        else:
            for child in node.children:
                beats.extend(self._collect_all_beats(child))
        return beats

    def _collect_scenes(self, node: StoryNode) -> List[StoryNode]:
        """Helper to collect all scene nodes."""
        scenes = []
        if node.type == "scene":
            scenes.append(node)
        else:
            for child in node.children:
                scenes.extend(self._collect_scenes(child))
        return scenes
