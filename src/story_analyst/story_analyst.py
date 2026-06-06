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
except ImportError:
    from tree import StoryNode
    from parser import StoryParser
    from graph_engine import GraphSynthesisEngine
    from asset_tracker import AssetPresenceEngine
    from summarizer import RecursiveSummarizationEngine
    from compression import CompressionEngine
    from visual_compiler import VisualSemanticCompiler

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

    def analyze(self, story_text: str, director_brief: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Executes the 7-stage Story Understanding pipeline.
        
        Args:
            story_text (str): The raw story/script text.
            director_brief (dict, optional): Guiding constraints or focus elements.
            
        Returns:
            dict: The complete Semantic Story Blueprint JSON matching schema v3.1.0.
        """
        # 1. Parse and build the skeleton Story Tree (Beats leaf layer initialized)
        tree = self.parser.parse(story_text)

        # 2. Synthesize causality and character graphs
        causality_graph = self.graph_engine.synthesize_causality_graph(tree)
        relationship_graph = self.graph_engine.synthesize_relationship_graph(tree)

        # 3. Build asset prop graphs and presence mapping
        asset_graph = self.asset_engine.build_asset_graph(tree)
        presence_matrix = self.asset_engine.compile_presence_matrix(tree)

        # Fallback: if relationship_graph nodes are empty, populate them from presence_matrix characters
        if not relationship_graph.get("nodes") and presence_matrix:
            unique_chars = set()
            for entry in presence_matrix:
                unique_chars.update(entry.get("characters_present", []))
            
            nodes = []
            for char_id in sorted(list(unique_chars)):
                name = char_id.replace("char_", "").replace("_", " ").title()
                nodes.append({
                    "id": char_id,
                    "name": name,
                    "archetype": "Character",
                    "traits": []
                })
            relationship_graph["nodes"] = nodes

        # 4. Calculate compression tiers, pruning rules, and tension/energy curves
        # This calculates tension/energy first so they are present in the Story Tree
        compression_model = self.compression_engine.compile_compression_model(tree, causality_graph)

        # 5. Perform bottom-up recursive summarization
        self.summarizer.summarize_tree_recursive(tree)
        director_view = self.summarizer.compile_director_view(
            tree, causality_graph, relationship_graph, asset_graph, presence_matrix
        )

        # 6. Extract stable visual profiles and mood maps
        visual_layer = self.visual_compiler.compile_visual_layer(tree, relationship_graph)

        # 7. Generate reflection checkpoints (ground truth verification rules)
        verification_rules = self._generate_verification_rules(tree, asset_graph, presence_matrix)

        # Assemble final Semantic Blueprint JSON matching schema v3.1.0
        blueprint = {
            "metadata": {
                "version": "3.1.0",
                "analyzer_signature": "StoryAnalyst-Agent-v3",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "story_title": tree.title
            },
            "director_view": director_view,
            "story_tree": tree.to_dict(),
            "causality_graph": causality_graph,
            "character_relationship_graph": relationship_graph,
            "asset_and_prop_graph": asset_graph,
            "presence_matrix": presence_matrix,
            "visual_semantic_layer": visual_layer,
            "narrative_compression_model": compression_model,
            "reflection_verification_rules": verification_rules
        }

        return blueprint

    def _generate_verification_rules(
        self, tree: StoryNode, asset_graph: Dict[str, Any], presence_matrix: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generates dynamic ground truth facts for Reflection Agent validation."""
        verification_rules = []
        
        # Parse prop states by beat_id to easily look up expected state
        prop_states_by_beat = {}
        for state_entry in asset_graph.get("states", []):
            beat_id = state_entry.get("beat_id")
            prop_id = state_entry.get("prop_id")
            if beat_id and prop_id:
                if beat_id not in prop_states_by_beat:
                    prop_states_by_beat[beat_id] = {}
                prop_states_by_beat[beat_id][prop_id] = state_entry.get("state", "active")

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

        for scene in scenes:
            presence = presence_by_scene.get(scene.id, {"characters_present": [], "props_present": []})
            chars_present = presence.get("characters_present", [])
            props_present = presence.get("props_present", [])
            
            # Forbidden elements are characters not present in this scene
            forbidden_chars = list(all_char_ids - set(chars_present))
            
            # Continuity checks: find expected state of each present prop at the last beat of the scene
            continuity_checks = []
            if scene.beats:
                last_beat_id = scene.beats[-1]["id"]
                for prop_id in props_present:
                    expected = prop_states_by_beat.get(last_beat_id, {}).get(prop_id, "active")
                    continuity_checks.append({
                        "prop_id": prop_id,
                        "expected_state": expected
                    })

            verification_rules.append({
                "scene_id": scene.id,
                "required_elements": chars_present + props_present,
                "forbidden_elements": forbidden_chars,
                "continuity_checks": continuity_checks
            })

        return verification_rules