from typing import Dict, List, Any
import json

try:
    from .tree import StoryNode
    from .utils import generate_id, call_llm, parse_json_response
except ImportError:
    from tree import StoryNode
    from utils import generate_id, call_llm, parse_json_response

class AssetPresenceEngine:
    """
    Stage 3: Asset & Presence tracking.
    Builds the Asset & Prop Graph (location, ownership, condition state)
    and compiles a presence matrix (who/what is in which scenes/beats).
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

    def build_asset_graph(self, tree: StoryNode) -> Dict[str, Any]:
        """
        Extracts prop mutations from LLM and propagates prop states and locations across the story beats.
        """
        beats = self._collect_all_beats(tree)
        beat_data = [{"id": b["id"], "description": b["description"]} for b in beats]
        
        # Map each beat to its parent scene's primary location
        beat_locations = {}
        def map_beat_locations(node: StoryNode):
            if node.type == "scene":
                for b in node.beats:
                    beat_locations[b["id"]] = node.primary_location or "loc_unknown"
            else:
                for child in node.children:
                    map_beat_locations(child)
        map_beat_locations(tree)

        system_instruction = (
            "You are a script analysis engine. Extract and track key props (items, weapons, documents) "
            "and their state mutations. Return ONLY a valid JSON object matching the requested schema."
        )
        
        prompt = f"""
        Identify key physical items (weapons, documents, relics, etc.) mentioned in the beats.
        Extract only State Mutations: return an entry ONLY when a prop is introduced, moves, changes owner/location, or is destroyed.
        Do not repeat state entries for beats where the prop does not change.
        
        Beats:
        {json.dumps(beat_data, ensure_ascii=False, indent=2)}
        
        Return a JSON object with this structure:
        {{
          "nodes": [
            {{ "id": "prop_id", "name": "Item Name", "type": "weapon|document|key_item|other", "visual_descriptor": "description" }}
          ],
          "mutations": [
            {{ "beat_id": "beat_id", "prop_id": "prop_id", "location": "char_id_or_location_id_or_unknown", "state": "active|destroyed|hidden" }}
          ]
        }}
        """
        
        response_json = call_llm(prompt, system_instruction=system_instruction, json_mode=True)
        
        try:
            data = parse_json_response(response_json)
        except Exception as e:
            print(f"[Asset Graph Fallback] Error: {e}", flush=True)
            data = {"nodes": [], "mutations": []}
            
        nodes = data.get("nodes", [])
        mutations = data.get("mutations", [])
        
        # Propagate states chronologically
        mutation_map = {}
        for mut in mutations:
            bid = mut.get("beat_id")
            pid = mut.get("prop_id")
            if bid and pid:
                mutation_map[(bid, pid)] = mut
                
        states = []
        for prop in nodes:
            pid = prop["id"]
            curr_state = "active"
            curr_loc = "unknown"
            
            for beat in beats:
                bid = beat["id"]
                mut = mutation_map.get((bid, pid))
                if mut:
                    curr_state = mut.get("state", curr_state)
                    curr_loc = mut.get("location", curr_loc)
                
                # If location is unknown, default to the scene's primary location
                final_loc = curr_loc
                if final_loc == "unknown":
                    final_loc = beat_locations.get(bid, "loc_unknown")
                    
                states.append({
                    "beat_id": bid,
                    "prop_id": pid,
                    "location": final_loc,
                    "state": curr_state
                })
                
        return {
            "nodes": nodes,
            "states": states
        }

    def compile_presence_matrix(self, tree: StoryNode) -> List[Dict[str, Any]]:
        """
        Calculates character and prop presence per scene/beat using actual scene IDs.
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
        For each scene, identify the characters and props physically present in the text.
        Use short, descriptive lowercase string IDs for characters (e.g., 'char_id') and props (e.g., 'prop_id').
        
        Scenes:
        {json.dumps(scenes_data, ensure_ascii=False, indent=2)}
        
        Return a JSON array with this structure:
        [
          {{
            "scene_id": "scene_id",
            "characters_present": ["char_id"],
            "props_present": ["prop_id"]
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
            
        return data
