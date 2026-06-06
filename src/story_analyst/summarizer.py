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
        asset_graph: Dict[str, Any],
        presence_matrix: List[Dict[str, Any]] = None
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
            "CRITICAL REQUIREMENT: You MUST NOT return empty lists for 'main_characters', 'main_conflicts', or 'top_hooks'. "
            "Every list must contain at least 1-3 entries based on the provided story elements. "
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
        
        1. Compile list of main characters and their roles. Reuse the exact character IDs provided in the catalog.
           - For each character, assign an 'importance' score between 0.0 and 1.0 based on their prominence and impact in this part of the story.
           - Only include characters whose importance score is 0.6 or higher.
           - DO NOT return an empty list (always include at least the protagonist/most important character even if they are the only one above 0.6).
        2. Identify main conflicts (internal, interpersonal, systemic) and the scene ID where they peak or resolve.
           - DO NOT return an empty list.
        3. Identify the top hook moments suitable for a trailer.
           - Rule: Pick hooks prioritizing: Mystery/Revelation, Threat, Contradiction, Power Shift, or Emotional Shock. Do not pick generic scenes.
           - Return the exact 'beat_id' for each hook.
           - DO NOT return an empty list.
        
        Return a JSON object with this structure:
        {{
          "main_characters": [
            {{ "id": "char_id_from_catalog", "role_in_plot": "description of role", "importance": 0.95 }}
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
            data = {}

        # ----------------------------------------------------
        # Robust Programmatic Character Importance Evaluation
        # ----------------------------------------------------
        evaluated_scores = self._evaluate_character_importance(
            relationship_graph, presence_matrix, scenes, beats
        )

        main_chars = data.get("main_characters", [])
        if main_chars:
            # If LLM returned characters, assign evaluated importance score and filter >= 0.6
            updated_chars = []
            for c in main_chars:
                char_id = c.get("id")
                # Get programmatically evaluated importance, default to 0.7 if not found
                imp = evaluated_scores.get(char_id, c.get("importance", 0.7))
                if imp >= 0.6:
                    updated_chars.append({
                        "id": char_id,
                        "role_in_plot": c.get("role_in_plot", "Key character in the plot."),
                        "importance": imp
                    })
            
            # If after filtering it is empty, keep the highest importance one
            if not updated_chars and main_chars:
                max_char = max(main_chars, key=lambda c: evaluated_scores.get(c.get("id"), 0.0), default=None)
                if max_char:
                    char_id = max_char.get("id")
                    updated_chars.append({
                        "id": char_id,
                        "role_in_plot": max_char.get("role_in_plot", "Key character in the plot."),
                        "importance": evaluated_scores.get(char_id, 0.7)
                    })
            main_chars = updated_chars
        elif relationship_graph.get("nodes"):
            # Fallback: populate from relationship_graph using evaluated_scores >= 0.6
            for node in relationship_graph.get("nodes", []):
                char_id = node["id"]
                imp = evaluated_scores.get(char_id, 0.0)
                if imp >= 0.6:
                    role = node.get("archetype", "Key Character")
                    if node.get("traits"):
                        role += f" ({', '.join(node['traits'][:3])})"
                    main_chars.append({
                        "id": char_id,
                        "role_in_plot": role,
                        "importance": imp
                    })
            
            # If still empty, select the character with max evaluated score
            if not main_chars:
                max_node = max(relationship_graph.get("nodes", []), key=lambda n: evaluated_scores.get(n["id"], 0.0), default=None)
                if max_node:
                    char_id = max_node["id"]
                    role = max_node.get("archetype", "Key Character")
                    main_chars.append({
                        "id": char_id,
                        "role_in_plot": role,
                        "importance": evaluated_scores.get(char_id, 0.7)
                    })

        data["main_characters"] = main_chars

        # 2. Fallback for top_hooks (pick highest tension beats)
        top_hooks = data.get("top_hooks", [])
        if not top_hooks and beats:
            # Sort beats by tension (descending)
            sorted_beats = sorted(beats, key=lambda b: (b.get("tension", 0.0), b.get("energy", 0.0)), reverse=True)
            for b in sorted_beats[:3]:  # Top 3 tension beats
                h_type = "action" if b.get("energy", 0) > 0.5 else "mystery"
                top_hooks.append({
                    "beat_id": b["id"],
                    "summary": b.get("summary", b.get("description", ""))[:100],
                    "hook_type": h_type,
                    "importance": round(b.get("tension", 0.8), 2)
                })
        data["top_hooks"] = top_hooks

        # 3. Fallback for main_conflicts
        main_conflicts = data.get("main_conflicts", [])
        if not main_conflicts and scenes:
            # Find the scene with the highest tension peak or fallback to first scene
            highest_tension_scene = max(scenes, key=lambda s: getattr(s, "tension_peak", 0.0) if hasattr(s, "tension_peak") else 0.0, default=None)
            res_point = highest_tension_scene.id if highest_tension_scene else (scenes[0].id if scenes else "")
            main_conflicts.append({
                "conflict_type": "interpersonal",
                "description": f"The main narrative clash and power struggle developing in the story, peaking at scene '{highest_tension_scene.title if highest_tension_scene else 'Main Clash'}'.",
                "resolution_point": res_point
            })
        data["main_conflicts"] = main_conflicts

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

    def _evaluate_character_importance(
        self,
        relationship_graph: Dict[str, Any],
        presence_matrix: List[Dict[str, Any]],
        scenes: List[StoryNode],
        beats: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        Evaluation mechanism: Programmatically calculates the importance score (0.0 to 1.0)
        for each character based on scene presence, relationship degree centrality, and beat activity.
        """
        importance_scores = {}
        nodes = relationship_graph.get("nodes", [])
        edges = relationship_graph.get("edges", [])
        
        if not nodes:
            return {}
            
        total_scenes = len(scenes) if scenes else 1
        
        # 1. Calculate Presence Ratio (P)
        char_presence = {}
        if presence_matrix:
            for entry in presence_matrix:
                for char_id in entry.get("characters_present", []):
                    char_presence[char_id] = char_presence.get(char_id, 0) + 1
                    
        # 2. Calculate Relationship Degree Centrality (D)
        char_degree = {}
        for edge in edges:
            src = edge.get("source")
            tgt = edge.get("target")
            if src:
                char_degree[src] = char_degree.get(src, 0) + 1
            if tgt:
                char_degree[tgt] = char_degree.get(tgt, 0) + 1
                
        # 3. Calculate Beat Mention Activity (A)
        char_activity = {}
        for beat in beats:
            desc = beat.get("description", "").lower()
            for node in nodes:
                name_parts = node.get("name", "").lower().split()
                # If character name is mentioned in beat description
                if any(part in desc for part in name_parts if len(part) > 2):
                    char_activity[node["id"]] = char_activity.get(node["id"], 0) + 1

        max_presence = max(char_presence.values(), default=1)
        max_degree = max(char_degree.values(), default=1)
        max_activity = max(char_activity.values(), default=1)
        
        for node in nodes:
            char_id = node["id"]
            
            p_score = char_presence.get(char_id, 0) / total_scenes
            d_score = char_degree.get(char_id, 0) / max(1, max_degree)
            a_score = char_activity.get(char_id, 0) / max(1, max_activity)
            
            # Weighted average: 40% presence, 30% relationship degree, 30% activity
            score = 0.4 * p_score + 0.3 * d_score + 0.3 * a_score
            importance_scores[char_id] = round(min(1.0, score), 2)
            
        return importance_scores

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
