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

class GraphSynthesisEngine:
    """
    Stage 2: Graph Synthesis.
    Constructs the Causality Graph (hybrid event dependency DAG) and 
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

    def _collect_scenes(self, node: StoryNode) -> List[StoryNode]:
        """Helper to collect all scene nodes from the tree."""
        scenes = []
        if node.type == "scene":
            scenes.append(node)
        else:
            for child in node.children:
                scenes.extend(self._collect_scenes(child))
        return scenes

    def synthesize_causality_graph(self, tree: StoryNode) -> Dict[str, Any]:
        """
        Builds a Hybrid Causality Graph:
        Stage 1: Local causality inside each scene (Beat-to-Beat).
        Stage 2: Global causality using scene summaries (Scene-to-Scene).
        """
        scenes = self._collect_scenes(tree)
        beats = self._collect_all_beats(tree)
        
        nodes = []
        for b in beats:
            nodes.append({"id": b["id"], "description": b["description"]})
        for s in scenes:
            nodes.append({"id": s.id, "description": s.summary or s.title})

        edges = []

        # Stage 1: Local Causality (Beat-to-Beat per Scene)
        for scene in scenes:
            if len(scene.beats) >= 2:
                scene_edges = self._synthesize_local_causality(scene)
                edges.extend(scene_edges)

        # Stage 2: Global Causality (Scene-to-Scene)
        if len(scenes) >= 2:
            global_edges = self._synthesize_global_causality(scenes)
            edges.extend(global_edges)

        # ----------------------------------------------------
        # Programmatic DAG Cycle Prevention (DFS cycle breaker)
        # ----------------------------------------------------
        from collections import defaultdict
        
        adj = defaultdict(list)
        for edge in edges:
            adj[edge["source"]].append(edge["target"])
            
        visited = {} # 0 = unvisited, 1 = visiting, 2 = visited
        cycles_edges_to_remove = set()
        
        def dfs(u):
            visited[u] = 1 # visiting
            for v in adj[u]:
                if visited.get(v, 0) == 1:
                    cycles_edges_to_remove.add((u, v))
                elif visited.get(v, 0) == 0:
                    dfs(v)
            visited[u] = 2 # visited
            
        for node in nodes:
            u = node["id"]
            if visited.get(u, 0) == 0:
                dfs(u)
                
        if cycles_edges_to_remove:
            print(f"[GraphEngine Warning]: Detected {len(cycles_edges_to_remove)} cyclic edges in causality graph. Pruning to maintain DAG structure.", flush=True)
            edges = [e for e in edges if (e["source"], e["target"]) not in cycles_edges_to_remove]

        # ----------------------------------------------------
        # Programmatic Verbatim Evidence Backfilling
        # ----------------------------------------------------
        nodes_desc_map = {}
        for b in beats:
            nodes_desc_map[b["id"]] = (b["id"], b["description"])
        for s in scenes:
            climax_beat_id = s.beats[0]["id"] if s.beats else s.id
            climax_beat_desc = s.beats[0]["description"] if s.beats else (s.summary or s.title)
            if s.beats:
                peak_beat = max(s.beats, key=lambda b: b.get("tension", 0.0))
                climax_beat_id = peak_beat["id"]
                climax_beat_desc = peak_beat["description"]
            nodes_desc_map[s.id] = (climax_beat_id, climax_beat_desc)

        for edge in edges:
            src = edge.get("source")
            tgt = edge.get("target")
            
            evidence_list = []
            if src in nodes_desc_map:
                bid, quote = nodes_desc_map[src]
                evidence_list.append({"beat_id": bid, "quote": quote})
            if tgt in nodes_desc_map:
                bid, quote = nodes_desc_map[tgt]
                evidence_list.append({"beat_id": bid, "quote": quote})
                
            edge["evidence"] = evidence_list

        return {
            "nodes": nodes,
            "edges": edges
        }

    def _synthesize_local_causality(self, scene: StoryNode) -> List[Dict[str, Any]]:
        """Stage 1: Local causality within a single scene."""
        beat_nodes = [{"id": b["id"], "description": b["description"]} for b in scene.beats]
        
        system_instruction = (
            "You are a script analysis engine. Analyze story beat sequences and build a "
            "local causality dependency graph within the scene. Return ONLY a valid JSON object matching the requested schema."
        )
        
        prompt = f"""
        Identify causal dependencies and setup-payoff connections between these story beats in the scene '{scene.title}'.
        For each relationship, output an edge representing which beat MUST happen (source) for another beat to occur (target).
        
        CRITICAL EVALUATION RULE:
        Analyze if Beat B remains logically coherent if Beat A is deleted. Only link A to B as a causal_necessity if B cannot exist/make sense without A.
        Do not create simple chronological chains unless a genuine, direct causal relationship exists.
        
        Beats:
        {json.dumps(beat_nodes, ensure_ascii=False, indent=2)}
        
        Return a JSON object with this structure:
        {{
          "edges": [
            {{ "source": "beat_id", "target": "beat_id", "type": "causal_necessity|information_dependency" }}
          ]
        }}
        """
        
        response_json = call_llm(prompt, system_instruction=system_instruction, json_mode=True, use_complex=True)
        try:
            data = parse_json_response(response_json)
            return data.get("edges", [])
        except Exception as e:
            print(f"[Local Causality Fallback] Error: {e} for scene {scene.title}", flush=True)
            return []

    def _synthesize_global_causality(self, scenes: List[StoryNode]) -> List[Dict[str, Any]]:
        """Stage 2: Global causality between scenes."""
        scene_summaries = [{"id": s.id, "summary": s.summary or s.title} for s in scenes]
        
        system_instruction = (
            "You are a script analysis engine. Analyze scene summaries and build a global scene-level causality graph. "
            "Return ONLY a valid JSON object matching the requested schema."
        )
        
        prompt = f"""
        Identify global causal dependencies between these scenes.
        For each relationship, output an edge representing which scene MUST happen (source) for another scene to occur (target) to maintain plot coherence.
        
        Scenes:
        {json.dumps(scene_summaries, ensure_ascii=False, indent=2)}
        
        Return a JSON object with this structure:
        {{
          "edges": [
            {{ "source": "scene_id", "target": "scene_id", "type": "causal_necessity|information_dependency" }}
          ]
        }}
        """
        
        response_json = call_llm(prompt, system_instruction=system_instruction, json_mode=True, use_complex=True)
        try:
            data = parse_json_response(response_json)
            return data.get("edges", [])
        except Exception as e:
            print(f"[Global Causality Fallback] Error: {e}", flush=True)
            return []

    def synthesize_relationship_graph(
        self, tree: StoryNode, entity_registry: Dict[str, Any], alias_map: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Tracks dynamic changes in character relationships (alliances, power levels) over time.
        Uses EntityRegistry as the Single Source of Truth for Character IDs.
        """
        beats = self._collect_all_beats(tree)
        beat_data = [{"id": b["id"], "description": b["description"]} for b in beats]
        
        characters = list(entity_registry.get("characters", {}).values())
        
        # Infer Relationship timelines using Registry Characters
        edges = self._infer_relationships(beat_data, characters, alias_map)
        
        return {
            "nodes": characters,
            "edges": edges
        }

    def _infer_relationships(
        self, beat_data: List[Dict[str, Any]], characters: List[Dict[str, Any]], alias_map: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """Phase 2: Infer dynamic relationship changes and evolution between registry characters."""
        if not characters:
            return []
            
        system_instruction = (
            "You are a script analysis engine. Analyze relationship evolution timeline between characters. "
            "For each relationship shift, assign a confidence rating (float between 0.0 and 1.0). "
            "Return ONLY a valid JSON object matching the requested schema."
        )
        
        char_list = [{"id": c["id"], "name": c["name"]} for c in characters]
        
        prompt = f"""
        Analyze dynamic relationship changes (alliances, stance, power balance) between the identified characters over the timeline of beats.
        For each active relationship pair, track their stance evolution over time.
        Only add timeline entries for beat IDs where a relationship change actually occurs.
        
        CRITICAL SAVING RULES:
        1. Keep 'source' and 'target' keys exactly as is.
        2. Minify timeline keys: 'tl' (timeline), 'b' (beat_id), 'ty' (type), 'v' (valence), 'p' (power_balance), 'c' (confidence).
        3. Do NOT output confidence 'c' if it is 1.0. Python will default it to 1.0.
        4. Do NOT output valence 'v' or power_balance 'p' if they are 0.0. Python will default them to 0.0.
        
        Characters:
        {json.dumps(char_list, ensure_ascii=False, indent=2)}
        
        Story Beats:
        {json.dumps(beat_data, ensure_ascii=False, indent=2)}
        
        Return a JSON object with this EXACT structure (using minified timeline keys):
        {{
          "edges": [
            {{
              "source": "char_lowercase_id",
              "target": "char_lowercase_id",
              "tl": [
                {{
                  "b": "beat_id",
                  "ty": "relationship type description (e.g. adversary, master_student, ally)",
                  "v": 0.8,
                  "p": -0.5,
                  "c": 0.95
                }}
              ]
            }}
          ]
        }}
        """
        
        response_json = call_llm(prompt, system_instruction=system_instruction, json_mode=True, use_complex=True)
        try:
            data = parse_json_response(response_json)
            raw_edges = data.get("edges", [])
        except Exception as e:
            print(f"[Infer Relationships Failed] Error: {e}", flush=True)
            raw_edges = []
            
        beat_desc_map = {b["id"]: b["description"] for b in beat_data}
        cleaned_edges = []
        me = MergeEngine()
        for edge in raw_edges:
            src = edge.get("source", "")
            tgt = edge.get("target", "")
            
            clean_src = me.resolve_entity(alias_map, src, "char")
            clean_tgt = me.resolve_entity(alias_map, tgt, "char")
            
            # Ensure both characters exist in the registry and are unique
            if clean_src in alias_map.values() and clean_tgt in alias_map.values() and clean_src != clean_tgt:
                timeline = []
                # Support both 'tl' and 'timeline' in case LLM falls back
                raw_timeline = edge.get("tl", edge.get("timeline", []))
                for entry in raw_timeline:
                    # Resolve minified keys with Python decoration (defaulting confidence=1.0, valence/power_balance=0.0)
                    beat_id = entry.get("b", entry.get("beat_id"))
                    rel_type = entry.get("ty", entry.get("type", "stance"))
                    valence = entry.get("v", entry.get("valence", 0.0))
                    power = entry.get("p", entry.get("power_balance", 0.0))
                    confidence = entry.get("c", entry.get("confidence", 1.0))
                    
                    # Robustly normalize beat_id prefix for lookup in case LLM stripped/duplicated it
                    lookup_id = beat_id
                    if lookup_id:
                        clean_id = str(lookup_id).replace("beat_", "")
                        rebuilt_id = f"beat_{clean_id}"
                        if rebuilt_id in beat_desc_map:
                            lookup_id = rebuilt_id
                            
                    quote = beat_desc_map.get(lookup_id, "No description found.")
                    evidence = [
                        {
                            "beat_id": lookup_id if lookup_id else beat_id,
                            "quote": quote
                        }
                    ]
                    
                    timeline.append({
                        "beat_id": lookup_id if lookup_id else beat_id,
                        "type": rel_type,
                        "valence": float(valence),
                        "power_balance": float(power),
                        "confidence": float(confidence),
                        "evidence": evidence
                    })
                cleaned_edges.append({
                    "source": clean_src,
                    "target": clean_tgt,
                    "timeline": timeline
                })
                
        return cleaned_edges
