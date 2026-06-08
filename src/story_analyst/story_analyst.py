import datetime
from typing import Dict, List, Any, Optional

try:
    from .tree import StoryNode
    from .parser import StoryParser
    from .graph_engine import GraphSynthesisEngine
    from .asset_tracker import AssetPresenceEngine
    from .summarizer import RecursiveSummarizationEngine
    from .compression import CompressionEngine
    from .visual_compiler import VisualSemanticCompiler
    from .merge_engine import MergeEngine
except ImportError:
    from tree import StoryNode
    from parser import StoryParser
    from graph_engine import GraphSynthesisEngine
    from asset_tracker import AssetPresenceEngine
    from summarizer import RecursiveSummarizationEngine
    from compression import CompressionEngine
    from visual_compiler import VisualSemanticCompiler
    from merge_engine import MergeEngine

try:
    from .utils import QuotaLimitReachedException, OllamaConnectionException, reset_token_stats, get_token_stats
except ImportError:
    from utils import QuotaLimitReachedException, OllamaConnectionException, reset_token_stats, get_token_stats

class StoryAnalyst:
    """
    The main coordinator class for the Story Analyst agent.
    Called directly by the Director Agent to convert raw story text into a Semantic Blueprint.
    """
    def __init__(self):
        self.parser = StoryParser()
        self.graph_engine = GraphSynthesisEngine()
        self.asset_engine = AssetPresenceEngine()
        self.summarizer = RecursiveSummarizationEngine()
        self.compression_engine = CompressionEngine()
        self.visual_compiler = VisualSemanticCompiler()
        self.merge_engine = MergeEngine()

    def analyze(self, story_text: str, director_brief: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes the 7-stage Story Understanding pipeline in a Registry-Centric flow.
        Gracefully handles persistent rate-limits by returning partial results.
        Supports FULL, NORMAL, and COMPACT blueprint modes.
        
        Args:
            story_text (str): The raw story/script text.
            director_brief (dict, optional): Guiding constraints or focus elements.
            
        Returns:
            dict: The Semantic Story Blueprint JSON with either complete or partial results.
        """
        # Reset token tracking statistics before run
        reset_token_stats()

        # Read blueprint mode from director brief, default to "NORMAL"
        blueprint_mode = "NORMAL"
        if director_brief and "blueprint_mode" in director_brief:
            mode_input = director_brief["blueprint_mode"].upper()
            if mode_input in {"FULL", "NORMAL", "COMPACT"}:
                blueprint_mode = mode_input

        # Initialize output structures with safe defaults for partial fallback
        entity_registry = {"characters": {}, "locations": {}, "props": {}}
        alias_map = {}
        causality_graph = {"nodes": [], "edges": []}
        relationship_graph = {"nodes": [], "edges": []}
        asset_graph = {"nodes": [], "states": []}
        presence_matrix = []
        compression_model = {"importance_tiers": {}, "pruning_rules": []}
        director_view = {}
        visual_layer = {"stable_character_profiles": [], "stable_location_profiles": [], "mood_theme_map": []}
        verification_rules = []
        story_fact_registry = []
        tree = None

        try:
            # 1. Parse and build the skeleton Story Tree (Beats leaf layer initialized via Scene Discovery + Beat Extraction)
            tree = self.parser.parse(story_text)

            # 2. Build Entity Registry at the front of the pipeline (Single Source of Truth)
            registry_results = self.merge_engine.build_registry(tree)
            entity_registry = registry_results["registry"]
            alias_map = registry_results["alias_map"]

            # 3. Propagate Registry IDs back to the Story Tree nodes
            self.merge_engine.update_tree_with_registry(tree, alias_map)

            # 4. Perform bottom-up recursive summarization
            # Generates summaries at beat/scene/sequence/act levels
            self.summarizer.summarize_tree_recursive(tree)

            # 5. Synthesize causality and character relationship graphs (referencing Entity Registry)
            causality_graph = self.graph_engine.synthesize_causality_graph(tree)
            relationship_graph = self.graph_engine.synthesize_relationship_graph(tree, entity_registry, alias_map)

            # 6. Build asset prop graphs and presence mapping (referencing Entity Registry)
            asset_graph = self.asset_engine.build_asset_graph(tree, entity_registry, alias_map, blueprint_mode)
            presence_matrix = self.asset_engine.compile_presence_matrix(tree, entity_registry, alias_map)

            # 7. Run narrative compression models (ranking & pruning rules)
            compression_model = self.compression_engine.compile_compression_model(tree, causality_graph)

            # 8. Compile director view (high-level summaries, conflicts, and hooks)
            director_view = self.summarizer.compile_director_view(
                tree, causality_graph, relationship_graph, asset_graph, presence_matrix, compression_model
            )

            # 8.5. Extract Story Fact Registry (Local route)
            story_fact_registry = self.merge_engine.extract_story_facts(tree)

            # 9. Extract stable visual profiles and dynamic, batched mood maps
            visual_layer = self.visual_compiler.compile_visual_layer(tree, entity_registry)

            # 10. Generate reflection checkpoints (ground truth verification rules)
            verification_rules = self._generate_verification_rules(tree, asset_graph, presence_matrix, entity_registry, blueprint_mode)

        except (QuotaLimitReachedException, OllamaConnectionException) as e:
            print(f"\n[StoryAnalyst Warning]: {e} Returning partial blueprint generated up to this point.\n", flush=True)

        if tree and presence_matrix:
            self._enrich_registry_metadata(entity_registry, tree, presence_matrix, relationship_graph, director_view, compression_model)

        # Collect critical beat IDs for drill-down support in COMPACT mode
        critical_beat_ids = set()
        
        # 1. Collect from top hooks in director view
        if isinstance(director_view, dict):
            for hook in director_view.get("top_hooks", []):
                bid = hook.get("beat_id")
                if bid:
                    critical_beat_ids.add(bid)
                    
        # 2. Collect high tension / climax beats (tension >= 0.7 or peak beat of each scene)
        def harvest_climax_beats(node: StoryNode):
            if node and node.type == "scene":
                if node.beats:
                    peak_beat = max(node.beats, key=lambda b: b.get("tension", 0.0))
                    critical_beat_ids.add(peak_beat["id"])
                    
                    for b in node.beats:
                        if b.get("tension", 0.0) >= 0.7:
                            critical_beat_ids.add(b["id"])
            elif node:
                for child in node.children:
                    harvest_climax_beats(child)
                
        if tree:
            harvest_climax_beats(tree)
            
        # 3. Collect mutation beats from prop timelines
        if isinstance(asset_graph, dict):
            for prop in asset_graph.get("nodes", []):
                for key in ["ownership_history", "location_history", "state_history"]:
                    for entry in prop.get(key, []):
                        bid = entry.get("beat_id")
                        if bid:
                            critical_beat_ids.add(bid)

        # Assemble final Semantic Blueprint JSON matching schema v3.1.0 (using either generated or default values)
        blueprint = {
            "metadata": {
                "version": "3.1.0",
                "analyzer_signature": "StoryAnalyst-Agent-v3",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "story_title": tree.title if tree else "Untitled",
                "blueprint_mode": blueprint_mode,
                "token_usage_statistics": get_token_stats()
            },
            "entity_registry": entity_registry,
            "director_view": director_view,
            "story_tree": tree.to_dict(mode=blueprint_mode, critical_beat_ids=critical_beat_ids) if tree else {},
            "causality_graph": causality_graph,
            "character_relationship_graph": relationship_graph,
            "asset_and_prop_graph": asset_graph,
            "presence_matrix": presence_matrix,
            "visual_semantic_layer": visual_layer,
            "narrative_compression_model": compression_model,
            "reflection_verification_rules": verification_rules,
            "story_fact_registry": story_fact_registry
        }

        return blueprint

    def _generate_verification_rules(
        self, tree: StoryNode, asset_graph: Dict[str, Any], presence_matrix: List[Dict[str, Any]], entity_registry: Dict[str, Any], blueprint_mode: str = "NORMAL"
    ) -> List[Dict[str, Any]]:
        """Generates dynamic ground truth facts for Reflection Agent validation."""
        verification_rules = []

        # Map scene presence
        presence_by_scene = {p["scene_id"]: p for p in presence_matrix}

        # Helper to collect all scene nodes
        def collect_scenes(node: StoryNode) -> List[StoryNode]:
            scenes = []
            if node.type == "scene":
                scenes.append(node)
            else:
                for child in node.children:
                    scenes.extend(collect_scenes(child))
            return scenes

        scenes = collect_scenes(tree)
        all_char_ids = set()
        for node in presence_matrix:
            all_char_ids.update(node.get("characters_present", []))

        # Build chronological list of beat IDs to determine query index for asset states
        beats = []
        beat_map = {}
        def harvest_beats(n):
            if n.type == "scene":
                for b in n.beats:
                    beats.append(b["id"])
                    beat_map[b["id"]] = b["description"]
            for c in n.children:
                harvest_beats(c)
        harvest_beats(tree)

        for scene in scenes:
            presence = presence_by_scene.get(scene.id, {"characters_present": [], "props_present": []})
            chars_present = presence.get("characters_present", [])
            props_present = presence.get("props_present", [])
            
            # Forbidden elements are characters not present in this scene
            forbidden_chars = list(all_char_ids - set(chars_present))
            
            # REQUIRED ELEMENTS EVIDENCE (FULL mode only - Tier 2)
            required_elements_evidence = []
            if blueprint_mode == "FULL":
                for element_id in (chars_present + props_present):
                    mention_beat_id = scene.beats[0]["id"] if scene.beats else scene.id
                    mention_quote = scene.beats[0]["description"] if scene.beats else "Scene presence mention."
                    
                    # Fetch entity details to search name mentions
                    name_to_search = element_id
                    if element_id.startswith("char_") and element_id in entity_registry.get("characters", {}):
                        name_to_search = entity_registry["characters"][element_id].get("name", "").lower()
                    elif element_id.startswith("prop_") and element_id in entity_registry.get("props", {}):
                        name_to_search = entity_registry["props"][element_id].get("name", "").lower()
                    
                    if scene.beats:
                        for b in scene.beats:
                            desc_lower = b["description"].lower()
                            if name_to_search in desc_lower:
                                mention_beat_id = b["id"]
                                mention_quote = b["description"]
                                break
                                
                    required_elements_evidence.append({
                        "id": element_id,
                        "evidence": [
                            {
                                "beat_id": mention_beat_id,
                                "quote": mention_quote
                            }
                        ]
                    })

            # Continuity checks: find expected state of each present prop at the last beat of the scene
            continuity_checks = []
            if scene.beats:
                last_beat_id = scene.beats[-1]["id"]
                last_beat_idx = beats.index(last_beat_id) if last_beat_id in beats else 0
                
                for prop_id in props_present:
                    prop_node = None
                    for p in asset_graph.get("nodes", []):
                        if p.get("id") == prop_id:
                            prop_node = p
                            break
                            
                    expected_state = "active"
                    evidence_beat_id = ""
                    if prop_node:
                        # Find the state at or before last_beat_id chronologically
                        state_hist = prop_node.get("state_history", [])
                        for entry in state_hist:
                            entry_bid = entry.get("beat_id")
                            entry_idx = beats.index(entry_bid) if entry_bid in beats else 0
                            if entry_idx <= last_beat_idx:
                                expected_state = entry.get("state", "active")
                                evidence_beat_id = entry_bid
                            else:
                                break
                    
                    entry = {
                        "prop_id": prop_id,
                        "expected_state": expected_state
                    }
                    
                    # Verbatim evidence tracking (FULL mode only - Tier 2)
                    if blueprint_mode == "FULL":
                        evidence_quote = "Inherited initial prop state."
                        if evidence_beat_id and evidence_beat_id in beat_map:
                            evidence_quote = beat_map[evidence_beat_id]
                        elif scene.beats:
                            evidence_beat_id = scene.beats[0]["id"]
                            evidence_quote = scene.beats[0]["description"]
                                    
                        entry["evidence"] = [
                            {
                                "beat_id": evidence_beat_id,
                                "quote": evidence_quote
                            }
                        ]
                        
                    continuity_checks.append(entry)

            rule = {
                "scene_id": scene.id,
                "required_elements": chars_present + props_present,
                "forbidden_elements": forbidden_chars,
                "continuity_checks": continuity_checks
            }
            if blueprint_mode == "FULL":
                rule["required_elements_evidence"] = required_elements_evidence
                
            verification_rules.append(rule)

        return verification_rules

    def _enrich_registry_metadata(self, entity_registry: Dict[str, Any], tree: StoryNode, presence_matrix: List[Dict[str, Any]], relationship_graph: Dict[str, Any], director_view: Dict[str, Any], compression_model: Dict[str, Any]) -> None:
        """
        Enriches the Entity Registry programmatically with statistical metadata.
        Calculates appearance counts, first/last scene appearances, and locked importance scores.
        """
        def collect_scenes(node: StoryNode) -> List[StoryNode]:
            scenes = []
            if node.type == "scene":
                scenes.append(node)
            else:
                for child in node.children:
                    scenes.extend(collect_scenes(child))
            return scenes

        scenes = collect_scenes(tree)
        scene_ids = [s.id for s in scenes]
        total_scenes = len(scenes) if scenes else 1
        
        # 1. Enrich Characters
        chars = entity_registry.get("characters", {})
        
        # Compute relationship counts first
        char_rel_counts = {}
        for cid in chars:
            rel_edges = relationship_graph.get("edges", [])
            rel_count = 0
            for edge in rel_edges:
                if edge.get("source") == cid or edge.get("target") == cid:
                    rel_count += 1
            char_rel_counts[cid] = rel_count
            
        max_rel_count = max(char_rel_counts.values()) if char_rel_counts else 1
        if max_rel_count == 0:
            max_rel_count = 1
            
        critical_path_scenes = set(compression_model.get("importance_tiers", {}).get("tier_1_core_path", []))
        
        for cid, char in chars.items():
            presence_scenes = []
            for pm in presence_matrix:
                if cid in pm.get("characters_present", []):
                    presence_scenes.append(pm["scene_id"])
            
            char["appearance_frequency"] = len(presence_scenes)
            
            if presence_scenes:
                presence_scenes_sorted = sorted(presence_scenes, key=lambda sid: scene_ids.index(sid) if sid in scene_ids else 9999)
                char["first_seen_scene"] = presence_scenes_sorted[0]
                char["last_seen_scene"] = presence_scenes_sorted[-1]
            else:
                char["first_seen_scene"] = ""
                char["last_seen_scene"] = ""
                
            rel_count = char_rel_counts.get(cid, 0)
            char["relationship_count"] = rel_count
            
            # Compute locked importance score formula:
            # importance_score = 0.4 * normalized_appearance_frequency + 0.4 * normalized_relationship_degree + 0.2 * critical_path_presence
            norm_app_freq = len(presence_scenes) / total_scenes
            norm_rel_deg = rel_count / max_rel_count
            
            present_scenes_set = set(presence_scenes)
            critical_path_presence = 1.0 if (present_scenes_set & critical_path_scenes) else 0.0
            
            importance_score = 0.4 * norm_app_freq + 0.4 * norm_rel_deg + 0.2 * critical_path_presence
            char["importance_score"] = round(importance_score, 2)

        # Synchronize and filter main characters in director_view
        if director_view and "main_characters" in director_view:
            synced_main_chars = []
            for mc in director_view["main_characters"]:
                cid = mc.get("id")
                if cid in chars:
                    imp_score = chars[cid]["importance_score"]
                    if imp_score >= 0.6:
                        mc["importance"] = imp_score
                        synced_main_chars.append(mc)
            
            # Fallback if list becomes empty: keep the character with highest importance
            if not synced_main_chars and chars:
                max_char_id = max(chars, key=lambda cid: chars[cid]["importance_score"])
                synced_main_chars.append({
                    "id": max_char_id,
                    "role_in_plot": chars[max_char_id].get("archetype", "Key Character"),
                    "importance": chars[max_char_id]["importance_score"]
                })
            director_view["main_characters"] = synced_main_chars

        # 2. Enrich Locations
        locs = entity_registry.get("locations", {})
        for lid, loc in locs.items():
            loc_scenes = []
            for s in scenes:
                if s.primary_location == lid:
                    loc_scenes.append(s.id)
            
            loc["appearance_frequency"] = len(loc_scenes)
            
            if loc_scenes:
                loc_scenes_sorted = sorted(loc_scenes, key=lambda sid: scene_ids.index(sid) if sid in scene_ids else 9999)
                loc["first_seen_scene"] = loc_scenes_sorted[0]
                loc["last_seen_scene"] = loc_scenes_sorted[-1]
            else:
                loc["first_seen_scene"] = ""
                loc["last_seen_scene"] = ""

        # 3. Enrich Props
        props = entity_registry.get("props", {})
        for pid, prop in props.items():
            presence_scenes = []
            for pm in presence_matrix:
                if pid in pm.get("props_present", []):
                    presence_scenes.append(pm["scene_id"])
            
            prop["appearance_frequency"] = len(presence_scenes)
            
            if presence_scenes:
                presence_scenes_sorted = sorted(presence_scenes, key=lambda sid: scene_ids.index(sid) if sid in scene_ids else 9999)
                prop["first_seen_scene"] = presence_scenes_sorted[0]
                prop["last_seen_scene"] = presence_scenes_sorted[-1]
            else:
                prop["first_seen_scene"] = ""
                prop["last_seen_scene"] = ""