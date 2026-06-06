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
        Splits the extraction into two phases:
        1. Extract character nodes
        2. Infer relationship evolution edges between the nodes
        """
        beats = self._collect_all_beats(tree)
        beat_data = [{"id": b["id"], "description": b["description"]} for b in beats]
        
        # Phase 1: Extract Character Nodes
        nodes = self._extract_characters(beat_data)
        
        # Phase 2: Infer Relationships Edges
        edges = self._infer_relationships(beat_data, nodes)
        
        return {
            "nodes": nodes,
            "edges": edges
        }

    def _extract_characters(self, beat_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Phase 1: Extract character entities, archetypes, and traits from story beats."""
        system_instruction = (
            "You are a script analysis engine. Identify all characters mentioned in the story beats. "
            "Return ONLY a valid JSON object matching the requested schema."
        )
        
        prompt = f"""
        Extract all characters mentioned in these story beats.
        For each character, identify:
        1. A unique short lowercase ID starting with 'char_' (e.g. 'char_ly_van_tieu').
        2. Their full proper name.
        3. Their archetype in the story (e.g., Protagonist, Antagonist, Mentor, Supporting).
        4. A list of key traits (personality or role-based) shown in these beats.
        
        Story Beats:
        {json.dumps(beat_data, ensure_ascii=False, indent=2)}
        
        Return a JSON object with this structure:
        {{
          "nodes": [
            {{ "id": "char_lowercase_id", "name": "Character Name", "archetype": "archetype description", "traits": ["trait1", "trait2"] }}
          ]
        }}
        """
        
        response_json = call_llm(prompt, system_instruction=system_instruction, json_mode=True)
        try:
            data = parse_json_response(response_json)
            return data.get("nodes", [])
        except Exception as e:
            print(f"[Extract Characters Fallback] Error: {e}", flush=True)
            return []

    def _infer_relationships(
        self, beat_data: List[Dict[str, Any]], nodes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Phase 2: Infer dynamic relationship changes and evolution between the characters."""
        if not nodes:
            return []
            
        system_instruction = (
            "You are a script analysis engine. Analyze relationship evolution between characters. "
            "Return ONLY a valid JSON object matching the requested schema."
        )
        
        char_list = [{"id": n["id"], "name": n["name"]} for n in nodes]
        
        prompt = f"""
        Analyze dynamic relationship changes (alliances, stance, power balance) between the identified characters over the timeline of beats.
        For each active relationship pair:
        - Track changes in alliances, stance type (e.g. adversary, master_student, ally), emotional valence (-1.0 to 1.0), and power balance (-1.0 to 1.0).
        - Only add evolution entries for beat IDs where a relationship change actually occurs.
        
        Characters:
        {json.dumps(char_list, ensure_ascii=False, indent=2)}
        
        Story Beats:
        {json.dumps(beat_data, ensure_ascii=False, indent=2)}
        
        Return a JSON object with this structure:
        {{
          "edges": [
            {{
              "source": "char_lowercase_id",
              "target": "char_lowercase_id",
              "evolution": [
                {{
                  "beat_id": "beat_id",
                  "type": "relationship type description",
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
            return data.get("edges", [])
        except Exception as e:
            print(f"[Infer Relationships Fallback] Error: {e}", flush=True)
            return []
