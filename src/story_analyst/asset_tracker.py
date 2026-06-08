from typing import Dict, List, Any
import json

try:
    from .tree import StoryNode
    from .utils import generate_id, call_llm, parse_json_response
    from .merge_engine import MergeEngine
except ImportError:
    from tree import StoryNode
    from utils import generate_id, call_llm, parse_json_response
    from merge_engine import MergeEngine

class AssetPresenceEngine:
    """
    Stage 3: Asset & Presence tracking.
    Builds the Asset & Prop Graph (split histories: ownership, location, state)
    and compiles the presence matrix (with IDs mapped to the Entity Registry).
    """
    def __init__(self):
        pass

    def _collect_all_beats(self, node: StoryNode) -> List[Dict[str, Any]]:
        """Helper to collect all beats from the Story Tree recursively."""
        beats = []
        if node.type == "scene":
            beats.extend(node.beats)
        else:
            for child in node.children:
                beats.extend(self._collect_all_beats(child))
        return beats

    def _collect_scenes(self, node: StoryNode) -> List[StoryNode]:
        """Helper to collect all scene nodes from the tree."""
        scenes = []
        if node.type == "scene":
            scenes.append(node)
        else:
            for child in node.children:
                scenes.extend(self._collect_scenes(child))
        return scenes

    def build_asset_graph(
        self, tree: StoryNode, entity_registry: Dict[str, Any], alias_map: Dict[str, str], blueprint_mode: str = "NORMAL"
    ) -> Dict[str, Any]:
        """
        Extracts prop mutations from LLM using registry catalog, and propagates
        ownership, location, and state timelines chronologically in Python.
        """
        beats = self._collect_all_beats(tree)
        beat_data = [{"id": b["id"], "description": b["description"]} for b in beats]
        
        props_list = list(entity_registry.get("props", {}).values())
        prop_ids_names = [f"- ID: {p['id']}, Name: {p['name']}" for p in props_list]
        prop_context = "\n".join(prop_ids_names) if prop_ids_names else "None."

        # Map each beat to its parent scene's primary location
        beat_locations = {}
        me = MergeEngine()
        def map_beat_locations(node: StoryNode):
            if node.type == "scene":
                raw_loc = node.primary_location or "loc_unknown"
                if raw_loc.startswith("loc_"):
                    raw_loc = raw_loc[4:]
                clean_loc = me.resolve_entity(alias_map, raw_loc, "loc")
                for b in node.beats:
                    beat_locations[b["id"]] = clean_loc
            else:
                for child in node.children:
                    map_beat_locations(child)
        map_beat_locations(tree)

        system_instruction = (
            "You are a script analysis engine. Extract prop state mutations (ownership, location, condition state). "
            "Return ONLY a valid JSON object matching the requested schema."
        )
        
        prompt = f"""
        Identify state mutations for these registered props across the beats.
        Return a mutation entry ONLY when a prop moves, changes owner, changes location, or is destroyed.
        Do not repeat state entries for beats where the prop does not change.
        
        CRITICAL SAVING RULES:
        1. Minify mutations keys: 'm' (mutations), 'b' (beat_id), 'p' (prop_id), 'o' (owner), 'l' (location), 's' (state).
        2. Do NOT output owner 'o' if it is 'none' or unchanged.
        3. Do NOT output state 's' if it is 'active' or unchanged.
        4. Do NOT output location 'l' if it is the primary scene location of the beat.
        
        Prop Catalog Reference (You MUST use these exact IDs):
        {prop_context}
        
        Beats:
        {json.dumps(beat_data, ensure_ascii=False, indent=2)}
        
        Return a JSON object with this EXACT structure (using minified mutation keys):
        {{
          "m": [
            {{
              "b": "beat_id",
              "p": "prop_id",
              "o": "char_id_or_none",
              "l": "location_id_or_none",
              "s": "active|destroyed|hidden"
            }}
          ]
        }}
        """
        
        response_json = call_llm(prompt, system_instruction=system_instruction, json_mode=True)
        
        try:
            data = parse_json_response(response_json)
            mutations = data.get("m", data.get("mutations", []))
        except Exception as e:
            print(f"[Asset Graph Fallback] Error: {e}", flush=True)
            mutations = []
            
        # Build mutation map
        mutation_map = {}
        for mut in mutations:
            bid = mut.get("b", mut.get("beat_id"))
            pid = mut.get("p", mut.get("prop_id"))
            if bid and pid:
                mutation_map[(bid, pid)] = mut
                
        # Propagate states chronologically and split histories
        beat_desc_map = {b["id"]: b["description"] for b in beats}
        for prop in props_list:
            pid = prop["id"]
            
            own_history = []
            loc_history = []
            st_history = []
            
            last_owner = None
            last_loc = None
            last_state = None
            
            for beat in beats:
                bid = beat["id"]
                mut = mutation_map.get((bid, pid))
                
                if mut:
                    new_owner = mut.get("o", mut.get("owner", last_owner or "none"))
                    new_loc = mut.get("l", mut.get("location", last_loc or beat_locations.get(bid, "loc_unknown")))
                    new_state = mut.get("s", mut.get("state", last_state or "active"))
                else:
                    new_owner = last_owner or "none"
                    new_loc = last_loc or beat_locations.get(bid, "loc_unknown")
                    new_state = last_state or "active"
                
                # Resolve IDs using registry alias map
                if new_owner and new_owner != "none" and not new_owner.startswith("char_"):
                    new_owner = me.resolve_entity(alias_map, new_owner, "char")
                if new_loc and new_loc != "loc_unknown" and not new_loc.startswith("loc_") and not new_loc.startswith("char_"):
                    # Could resolve to location or character
                    if new_loc in alias_map:
                        new_loc = alias_map[new_loc]
                    else:
                        new_loc = me.resolve_entity(alias_map, new_loc, "loc")

                # Record split history changes with verbatim evidence quotes (FULL mode only)
                if new_owner != last_owner:
                    entry = {"beat_id": bid, "owner": new_owner}
                    if blueprint_mode == "FULL":
                        quote = beat_desc_map.get(bid, "No description found.")
                        entry["evidence"] = [{"beat_id": bid, "quote": quote}]
                    own_history.append(entry)
                    last_owner = new_owner
                if new_loc != last_loc:
                    entry = {"beat_id": bid, "location": new_loc}
                    if blueprint_mode == "FULL":
                        quote = beat_desc_map.get(bid, "No description found.")
                        entry["evidence"] = [{"beat_id": bid, "quote": quote}]
                    loc_history.append(entry)
                    last_loc = new_loc
                if new_state != last_state:
                    entry = {"beat_id": bid, "state": new_state}
                    if blueprint_mode == "FULL":
                        quote = beat_desc_map.get(bid, "No description found.")
                        entry["evidence"] = [{"beat_id": bid, "quote": quote}]
                    st_history.append(entry)
                    last_state = new_state
                    
            prop["ownership_history"] = own_history
            prop["location_history"] = loc_history
            prop["state_history"] = st_history
            
        return {
            "nodes": props_list,
            "states": [] # For schema compatibility, output empty states list
        }

    def compile_presence_matrix(
        self, tree: StoryNode, entity_registry: Dict[str, Any], alias_map: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Calculates character and prop presence per scene/beat, resolving IDs to Registry.
        """
        scenes = self._collect_scenes(tree)
        scenes_data = []
        for s in scenes:
            scenes_data.append({
                "id": s.id,
                "title": s.title,
                "text": " ".join([b["description"] for b in s.beats])
            })
            
        system_instruction = (
            "You are a script analysis engine. Map character and prop presence to scene IDs. "
            "Return ONLY a valid JSON array matching the requested schema."
        )
        
        prompt = f"""
        For each scene, identify which of the registered characters and props are physically present.
        Only identify characters/props that are actually mentioned or actively involved in the text.
        
        Scenes:
        {json.dumps(scenes_data, ensure_ascii=False, indent=2)}
        
        Return a JSON array with this structure:
        [
          {{
            "scene_id": "scene_id",
            "characters_present": ["char_lowercase_id"],
            "props_present": ["prop_lowercase_id"]
          }}
        ]
        """
        
        response_json = call_llm(prompt, system_instruction=system_instruction, json_mode=True)
        
        try:
            data = parse_json_response(response_json)
            if not isinstance(data, list):
                data = []
        except Exception as e:
            print(f"[Presence Matrix Fallback] Error: {e}", flush=True)
            data = []
            
        cleaned_presence = []
        me = MergeEngine()
        for entry in data:
            sid = entry.get("scene_id")
            if not sid:
                continue
            chars = entry.get("characters_present", [])
            props = entry.get("props_present", [])
            
            clean_chars = sorted(list(set(me.resolve_entity(alias_map, c, "char") for c in chars if c)))
            clean_props = sorted(list(set(me.resolve_entity(alias_map, p, "prop") for p in props if p)))
            
            # Filter to ensure only registered characters/props are included
            valid_chars = [c for c in clean_chars if c in entity_registry.get("characters", {})]
            valid_props = [p for p in clean_props if p in entity_registry.get("props", {})]
            
            cleaned_presence.append({
                "scene_id": sid,
                "characters_present": valid_chars,
                "props_present": valid_props
            })
            
        return cleaned_presence
