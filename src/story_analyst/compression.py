import json
from typing import Dict, List, Any

try:
    from .tree import StoryNode
    from .utils import call_llm, parse_json_response
except ImportError:
    from tree import StoryNode
    from utils import call_llm, parse_json_response

class CompressionEngine:
    """
    Stage 5: Narrative Compression.
    Groups scenes and beats into importance tiers, defines pruning rules
    based on causal dependencies, and runs two-stage tension & energy scoring.
    """
    def __init__(self):
        pass

    def _collect_all_scene_ids(self, node: StoryNode) -> List[str]:
        """Helper to recursively collect all scene IDs from the tree."""
        scene_ids = []
        if node.type == "scene":
            scene_ids.append(node.id)
        else:
            for child in node.children:
                scene_ids.extend(self._collect_all_scene_ids(child))
        return scene_ids

    def _collect_scenes(self, node: StoryNode) -> List[StoryNode]:
        """Helper to recursively collect all scene nodes from the tree."""
        scenes = []
        if node.type == "scene":
            scenes.append(node)
        else:
            for child in node.children:
                scenes.extend(self._collect_scenes(child))
        return scenes

    def _apply_heuristic_scoring(self, beats: List[Dict[str, Any]]) -> None:
        """Stage 1: Apply rough heuristic tension/energy scoring at the beat level."""
        intensity_keywords = [
            "gào", "hét", "quát", "chém", "giết", "chết", "ngã", "bắn", "phá", "nổ",
            "chấn động", "đột nhiên", "run", "giật", "thất kinh", "ngơ ngác", "lạnh",
            "bất ngờ", "run", "kill", "explosion", "suddenly", "fight", "attack",
            "die", "dead", "scream", "shout", "clash"
        ]
        
        for beat in beats:
            desc = beat.get("description", "").lower()
            btype = beat.get("type", "action")
            
            # Base values by beat type
            if btype == "action":
                base_energy, base_tension = 0.3, 0.2
            elif btype == "dialogue":
                base_energy, base_tension = 0.2, 0.1
            else:  # transition
                base_energy, base_tension = 0.1, 0.1
                
            # Add value for punctuation
            punc_energy = desc.count("!") * 0.2 + desc.count("?") * 0.05
            punc_tension = desc.count("!") * 0.15 + desc.count("?") * 0.1
            
            # Add value for intensity keywords
            kw_hits = sum(1 for kw in intensity_keywords if kw in desc)
            kw_energy = kw_hits * 0.15
            kw_tension = kw_hits * 0.15
            
            # Update values, capped at 1.0
            beat["energy"] = min(1.0, base_energy + punc_energy + kw_energy)
            beat["tension"] = min(1.0, base_tension + punc_tension + kw_tension)

    def _apply_llm_enhancement(self, scenes: List[StoryNode]) -> None:
        """Stage 2: Ask LLM to evaluate and score tension peak and energy multipliers at higher Scene level."""
        if not scenes:
            return

        scenes_info = []
        for s in scenes:
            scenes_info.append({
                "id": s.id,
                "title": s.title,
                "summary": s.summary or " ".join([b["description"] for b in s.beats])
            })

        system_instruction = (
            "You are a script editor scoring the dramatic structure of scenes. "
            "Return ONLY a valid JSON object matching the requested schema."
        )
        
        prompt = f"""
        Analyze the following scenes and determine for each:
        1. "tension_peak" (float between 0.0 and 1.0): representing the highest narrative drama, conflict, or suspense peak.
        2. "energy_multiplier" (float between 0.5 and 2.0): representing the pace, action level, or physical intensity of the scene.
        
        Scenes:
        {json.dumps(scenes_info, ensure_ascii=False, indent=2)}
        
        Return a JSON object with this structure:
        {{
          "scene_scores": [
            {{ "id": "scene_id", "tension_peak": 0.8, "energy_multiplier": 1.2 }}
          ]
        }}
        """
        
        response_json = call_llm(prompt, system_instruction=system_instruction, json_mode=True)
        
        scores_by_id = {}
        try:
            data = parse_json_response(response_json)
            for item in data.get("scene_scores", []):
                sid = item.get("id")
                if sid:
                    scores_by_id[sid] = item
        except Exception as e:
            print(f"[Tension Scoring Fallback] Error parsing LLM response: {e}", flush=True)

        for scene in scenes:
            score = scores_by_id.get(scene.id, {})
            tension_peak = score.get("tension_peak", 0.5)
            energy_multiplier = score.get("energy_multiplier", 1.0)
            
            scene.tension_peak = tension_peak
            
            if scene.beats:
                # Find maximum heuristic tension
                max_h_tension = max(b["tension"] for b in scene.beats)
                
                for beat in scene.beats:
                    # Scale tension relative to the peak tension of the scene
                    if max_h_tension > 0:
                        beat["tension"] = min(1.0, (beat["tension"] / max_h_tension) * tension_peak)
                    else:
                        beat["tension"] = tension_peak
                        
                    # Scale energy using the multiplier
                    beat["energy"] = min(1.0, beat["energy"] * energy_multiplier)

    def compile_compression_model(self, tree: StoryNode, causality: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates importance tiers, sets causal pruning rules, and scores tension/energy.
        
        Args:
            tree (StoryNode): Root of the Story Tree.
            causality (dict): The synthesized Causality Graph.
            
        Returns:
            dict: Narrative compression model containing tiers and pruning rules.
        """
        # Step 1: Heuristic Scoring at the beat level
        scenes = self._collect_scenes(tree)
        for scene in scenes:
            self._apply_heuristic_scoring(scene.beats)
            
        # Step 2: LLM Enhancement at the Scene level
        self._apply_llm_enhancement(scenes)
        
        scene_ids = [s.id for s in scenes]
        
        # Categorize scenes into tiers (mock classification based on list order or peak tension)
        tier_1 = []
        tier_2 = []
        tier_3 = []
        
        # Let's categorize dynamically based on tension peak
        for scene in scenes:
            if scene.tension_peak >= 0.7:
                tier_1.append(scene.id)
            elif scene.tension_peak >= 0.4:
                tier_2.append(scene.id)
            else:
                tier_3.append(scene.id)
                
        # If all scenes fell into one tier, fallback to index-based distribution
        if not tier_1 and not tier_2:
            for idx, scene_id in enumerate(scene_ids):
                if idx % 3 == 0:
                    tier_1.append(scene_id)
                elif idx % 3 == 1:
                    tier_2.append(scene_id)
                else:
                    tier_3.append(scene_id)
                    
        # Generate pruning rules based on causality edges
        pruning_rules = []
        for edge in causality.get("edges", []):
            if edge.get("type") == "causal_necessity":
                # If the source (cause) is pruned, the target (effect) must be pruned
                pruning_rules.append({
                    "if_pruned": edge["source"],
                    "must_prune": [edge["target"]]
                })

        return {
            "importance_tiers": {
                "tier_1_core_path": tier_1,
                "tier_2_subplots": tier_2,
                "tier_3_atmospheric": tier_3
            },
            "pruning_rules": pruning_rules
        }
