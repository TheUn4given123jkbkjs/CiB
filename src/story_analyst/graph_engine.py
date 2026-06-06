from typing import Dict, List, Any
import json

try:
    from .tree import StoryNode
    from .utils import generate_id, call_llm, parse_json_response
except ImportError:
    from tree import StoryNode
    from utils import generate_id, call_llm, parse_json_response

class GraphSynthesisEngine:
    """
    Stage 2: Graph Synthesis.
    Constructs the Causality Graph (event dependency DAG) and 
    the Character Relationship Graph (valence, power balances) from the Story Tree.
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

    def synthesize_causality_graph(self, tree: StoryNode) -> Dict[str, Any]:
        """
        Traverses the StoryTree and maps cause-and-effect / setup-payoff dependencies.
        Uses actual node IDs collected from the tree and queries the LLM.
        """
        beats = self._collect_all_beats(tree)
        nodes = [{"id": b["id"], "description": b["description"]} for b in beats]
        
        system_instruction = (
            "You are a script analysis engine. Analyze story beat sequences and build a "
            "causality dependency graph. Return ONLY a valid JSON object matching the requested schema."
        )
        
        prompt = f"""
        Identify causal dependencies and setup-payoff connections between these story beats.
        For each causal relationship, output an edge representing which beat MUST happen (source) for another beat to occur (target).
        
        CRITICAL EVALUATION RULE:
        Analyze if Beat B remains logically coherent if Beat A is deleted. Only link A to B as a causal_necessity if B cannot exist/make sense without A.
        Do not create simple chronological chains (e.g. Beat 1 -> Beat 2 -> Beat 3) unless a genuine, direct causal relationship exists.
        
        Beats:
        {json.dumps(nodes, ensure_ascii=False, indent=2)}
        
        Return a JSON object with this structure:
        {{
          "edges": [
            {{ "source": "beat_id", "target": "beat_id", "type": "causal_necessity|information_dependency" }}
          ]
        }}
        """
        
        response_json = call_llm(prompt, system_instruction=system_instruction, json_mode=True)
        
        try:
            data = parse_json_response(response_json)
            edges = data.get("edges", [])
        except Exception as e:
            print(f"[Causality Fallback] Error: {e}", flush=True)
            edges = []
            for i in range(len(beats) - 1):
                edges.append({
                    "source": beats[i]["id"],
                    "target": beats[i + 1]["id"],
                    "type": "causal_necessity"
                })
                
        return {
            "nodes": nodes,
            "edges": edges
        }

    def synthesize_relationship_graph(self, tree: StoryNode) -> Dict[str, Any]:
        """
        Tracks dynamic changes in character relationships (alliances, power levels) over time.
        """
        beats = self._collect_all_beats(tree)
        beat_data = [{"id": b["id"], "description": b["description"]} for b in beats]
        
        system_instruction = (
            "You are a script analysis engine. Identify characters and extract their relationship networks "
            "and relationship evolution over time from the beats. Return ONLY a valid JSON object matching the requested schema."
        )
        
        prompt = f"""
        Extract all characters mentioned in these story beats.
        For each character, identify a short lowercase ID (e.g. 'char_john_doe'), their name, archetype, and key traits.
        
        Track relationship evolution (changes in alliances, stance type, emotional valence (-1.0 to 1.0), and power balance (-1.0 to 1.0) over the timeline.
        Only add evolution entries for beats where a change actually occurs.
        
        Story Beats:
        {json.dumps(beat_data, ensure_ascii=False, indent=2)}
        
        Return a JSON object with this structure:
        {{
          "nodes": [
            {{ "id": "char_lowercase_id", "name": "Character Name", "archetype": "archetype description", "traits": ["trait1", "trait2"] }}
          ],
          "edges": [
            {{
              "source": "char_lowercase_id",
              "target": "char_lowercase_id",
              "evolution": [
                {{
                  "beat_id": "beat_id",
                  "type": "relationship type description (e.g. adversary, master_student)",
                  "valence": 0.0,
                  "power_balance": 0.0
                }}
              ]
            }}
          ]
        }}
        """
        
        response_json = call_llm(prompt, system_instruction=system_instruction, json_mode=True)
        
        try:
            data = parse_json_response(response_json)
        except Exception as e:
            print(f"[Relationships Fallback] Error: {e}", flush=True)
            data = {"nodes": [], "edges": []}
            
        return data
