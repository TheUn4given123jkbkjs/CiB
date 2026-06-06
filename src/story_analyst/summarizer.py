from typing import Dict, List, Any
import json

try:
    from .tree import StoryNode
    from .utils import call_llm, parse_json_response
except ImportError:
    from tree import StoryNode
    from utils import call_llm, parse_json_response

class RecursiveSummarizationEngine:
    """
    Stage 4: Recursive Bottom-Up Summarization.
    Traverses the StoryTree from leaf nodes (beats) to the root story,
    synthesizing node summaries and compiling the Director's View.
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

    def summarize_tree_recursive(self, node: StoryNode) -> str:
        """
        Traverses the StoryTree in post-order (bottom-up) to populate the 'summary'
        field of each node with synthesized semantic summaries, and tracks the derived_from lineage.
        """
        if node.type == "scene":
            beat_contents = []
            node.derived_from = []
            for beat in node.beats:
                if not beat.get("summary"):
                    beat["summary"] = self._synthesize_beat(beat["description"])
                beat_contents.append(beat["summary"])
                node.derived_from.append(beat["id"])
            
            node.summary = self._synthesize(beat_contents, "scene", node.title)
            return node.summary

        child_summaries = []
        node.derived_from = []
        for child in node.children:
            summary = self.summarize_tree_recursive(child)
            child_summaries.append(summary)
            node.derived_from.append(child.id)

        node.summary = self._synthesize(child_summaries, node.type, node.title)
        return node.summary

    def _collect_scenes(self, node: StoryNode) -> List[StoryNode]:
        """Helper to collect all scene nodes from the tree."""
        scenes = []
        if node.type == "scene":
            scenes.append(node)
        else:
            for child in node.children:
                scenes.extend(self._collect_scenes(child))
        return scenes

    def compile_director_view(
        self,
        root: StoryNode,
        causality: Dict[str, Any],
        relationship_graph: Dict[str, Any],
        asset_graph: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Synthesizes the global story summary and compiles the Director's View block,
        reusing character and asset IDs from the synthesized graphs to prevent hallucinated IDs.
        """
        scenes = self._collect_scenes(root)
        scenes_summaries = [{"id": s.id, "title": s.title, "summary": s.summary} for s in scenes]
        
        beats = self._collect_all_beats(root)
        beat_summaries = [{"id": b["id"], "summary": b["summary"], "description": b["description"]} for b in beats]
        
        # Format character info for matching IDs
        char_ids_names = []
        for char in relationship_graph.get("nodes", []):
            char_ids_names.append(f"- ID: {char['id']}, Name: {char['name']}")
        char_context = "\n".join(char_ids_names) if char_ids_names else "None identified yet."

        # Format asset info for matching IDs
        prop_ids_names = []
        for prop in asset_graph.get("nodes", []):
            prop_ids_names.append(f"- ID: {prop['id']}, Name: {prop['name']}")
        prop_context = "\n".join(prop_ids_names) if prop_ids_names else "None identified yet."

        system_instruction = (
            "You are a film director's story consultant. Synthesize an executive overview of the story. "
            "You MUST strictly reuse the Character IDs and Prop/Asset IDs supplied in the context. "
            "Return ONLY a valid JSON object matching the requested schema."
        )
        
        prompt = f"""
        Analyze the following story elements.
        
        Character Reference Catalog (Use these EXACT IDs for 'main_characters'):
        {char_context}
        
        Asset Reference Catalog (Use these EXACT IDs if referencing props):
        {prop_context}
        
        Chronological Beats (Use these EXACT IDs for 'top_hooks'):
        {json.dumps(beat_summaries, ensure_ascii=False, indent=2)}
        
        Scene Summaries:
        {json.dumps(scenes_summaries, ensure_ascii=False, indent=2)}
        
        1. Compile list of main characters and their roles. Reuse the exact character IDs provided.
        2. Identify main conflicts (internal, interpersonal, systemic) and the scene ID where they peak or resolve.
        3. Identify the top hook moments suitable for a trailer.
           - Rule: Pick hooks prioritizing: Mystery/Revelation, Threat, Contradiction, Power Shift, or Emotional Shock. Do not pick generic scenes.
           - Return the exact 'beat_id' for each hook.
        
        Return a JSON object with this structure:
        {{
          "main_characters": [
            {{ "id": "char_id_from_catalog", "role_in_plot": "description of role" }}
          ],
          "main_conflicts": [
            {{ "conflict_type": "interpersonal|internal|systemic", "description": "description of conflict", "resolution_point": "scene_id_where_it_resolves" }}
          ],
          "top_hooks": [
            {{ "beat_id": "beat_id_from_catalog", "summary": "description of hook", "hook_type": "mystery|action|emotional|threat|revelation|shock", "importance": 0.95 }}
          ]
        }}
        """
        
        response_json = call_llm(prompt, system_instruction=system_instruction, json_mode=True)
        
        try:
            data = parse_json_response(response_json)
        except Exception as e:
            print(f"[Director View Fallback] Error: {e}", flush=True)
            data = {
                "main_characters": [],
                "main_conflicts": [],
                "top_hooks": []
            }
            
        # Complete the final director_view dict
        director_view = {
            "story_summary": root.summary,
            "main_characters": data.get("main_characters", []),
            "main_conflicts": data.get("main_conflicts", []),
            "critical_path_summary": [
                {
                    "scene_id": s.id,
                    "summary": s.summary
                }
                for s in scenes
            ],
            "top_hooks": data.get("top_hooks", [])
        }
        return director_view

    def _synthesize_beat(self, description: str) -> str:
        """Lightweight synthesis of raw beat description into a concise beat summary using LLM."""
        system_instruction = (
            "Bạn là một trợ lý tóm tắt kịch bản cực ngắn. "
            "CRITICAL RULE: You MUST retain all core entities (unique proper names of characters, locations, and specific items/weapons/relics) in the summary. Do not generalize proper nouns into generic terms (e.g., do not rewrite a character's name like 'Arthur' into 'a king/student', 'Camelot' into 'a castle/classroom', or 'Excalibur' into 'a sword/weapon')."
        )
        prompt = f"Hãy tóm tắt hành động/lời thoại sau đây thành 1 câu ngắn gọn (bằng Tiếng Việt, giữ nguyên tên riêng):\n{description}"
        result = call_llm(prompt, system_instruction=system_instruction)
        if not result or "Error call_llm" in result or "Fallback LLM" in result:
            clean = description.strip().replace("\n", " ")
            if len(clean) > 45:
                return clean[:45] + "..."
            return clean
        return result

    def _synthesize(self, summaries: List[str], level: str, title: str) -> str:
        """Combines child summaries and prompts the LLM to synthesize a parent summary."""
        combined_text = "\n- ".join(summaries)
        system_instruction = (
            "Bạn là một biên kịch lão luyện tóm tắt cấu trúc cốt truyện. "
            "CRITICAL RULE: You MUST retain all core entities (unique proper names of characters, locations, and specific items/weapons/relics) in the summary. Do not generalize proper nouns into generic terms (e.g., do not rewrite a character's name like 'Arthur' into 'a king/student', 'Camelot' into 'a castle/classroom', or 'Excalibur' into 'a sword/weapon')."
        )
        prompt = f"Hãy tóm tắt phần '{level}' có tên '{title}' dựa trên danh sách tóm tắt con sau đây (bằng Tiếng Việt, ngắn gọn 1-2 câu, giữ nguyên tên riêng):\n- {combined_text}"
        
        result = call_llm(prompt, system_instruction=system_instruction)
        if not result or "Error call_llm" in result or "Fallback LLM" in result:
            if level == "scene":
                return f"Phân cảnh: {title}. Diễn biến chính: " + " -> ".join(summaries[:2]) + "..."
            elif level == "sequence":
                return f"Chuỗi sự kiện '{title}' gồm các phân cảnh: " + ", ".join(summaries[:2])
            elif level == "act":
                return f"Hồi '{title}' tiến triển qua các chuỗi: " + ", ".join(summaries[:2])
            else:
                return f"Tổng quan truyện '{title}': " + " | ".join(summaries[:2])
        return result
