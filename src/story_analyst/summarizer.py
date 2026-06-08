from typing import Dict, List, Any, Optional
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
    Uses token-budget batching (6000 tokens) at scene level.
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
            self._summarize_scene_batched(node)
            return node.summary

        child_summaries = []
        node.derived_from = []
        for child in node.children:
            summary = self.summarize_tree_recursive(child)
            child_summaries.append(summary)
            node.derived_from.append(child.id)

        node.summary = self._synthesize(child_summaries, node.type, node.title)
        return node.summary

    def _summarize_scene_batched(self, node: StoryNode) -> None:
        """
        Summarizes all beats of a scene and the scene itself in a single LLM call per batch,
        respecting a token/character context budget (~6,000 tokens or 24,000 characters).
        """
        if not node.beats:
            node.summary = f"Scene: {node.title} has no events."
            node.derived_from = []
            return

        beats_to_process = node.beats
        # Target context budget of 6000 tokens (approx 24,000 characters of description)
        target_char_budget = 24000
        
        # Partition beats into subscene batches if they exceed the budget
        batches = []
        current_batch = []
        current_len = 0
        for beat in beats_to_process:
            beat_len = len(beat.get("description", ""))
            if current_len + beat_len > target_char_budget and current_batch:
                batches.append(current_batch)
                current_batch = []
                current_len = 0
            current_batch.append(beat)
            current_len += beat_len
        if current_batch:
            batches.append(current_batch)

        node.derived_from = [b["id"] for b in node.beats]
        
        subscene_summaries = []
        for batch_idx, batch in enumerate(batches):
            sub_title = f"{node.title} (Part {batch_idx + 1})" if len(batches) > 1 else node.title
            
            # Format beats for prompt
            beats_input = [{"id": b["id"], "description": b["description"]} for b in batch]
            
            system_instruction = (
                "You are a script editor and narrative summarization engine. "
                "For the provided scene and its individual beats, synthesize a concise summary for each beat, "
                "and then compile a synthesized summary for the scene. "
                "CRITICAL RULE: You MUST retain all core entities (unique proper names of characters, locations, and specific items/weapons/relics). Do not generalize them. "
                "Return ONLY a valid JSON object matching the requested schema."
            )
            
            prompt = f"""
            Synthesize a concise summary (1 sentence, in English, keeping all proper names) for each beat in the scene, and then compile an overall scene summary (1-2 sentences, in English, keeping all proper names).
            
            Scene Title: {sub_title}
            Beats:
            {json.dumps(beats_input, ensure_ascii=False, indent=2)}
            
            Return a JSON object with this structure:
            {{
              "beat_summaries": [
                {{ "id": "beat_id", "summary": "concise beat summary..." }}
              ],
              "scene_summary": "concise scene summary..."
            }}
            """
            
            response_json = call_llm(prompt, system_instruction=system_instruction, json_mode=True)
            
            try:
                data = parse_json_response(response_json)
                # Apply beat summaries
                beat_sums = {item["id"]: item["summary"] for item in data.get("beat_summaries", []) if "id" in item and "summary" in item}
                for b in batch:
                    b["summary"] = beat_sums.get(b["id"], b["description"][:45] + "...")
                
                subscene_summary = data.get("scene_summary", f"Scene: {sub_title}.")
                subscene_summaries.append(subscene_summary)
            except Exception as e:
                print(f"[Summarizer Scene Fallback] Error parsing LLM response for {sub_title}: {e}", flush=True)
                # Fallback: summarize individually
                for b in batch:
                    b["summary"] = self._synthesize_beat(b["description"])
                subscene_summary = f"Scene: {sub_title}. Key events: " + " -> ".join([b["summary"] for b in batch[:2]]) + "..."
                subscene_summaries.append(subscene_summary)

        # Combine subscenes
        if len(subscene_summaries) == 1:
            node.summary = subscene_summaries[0]
        else:
            # Synthesize subscene summaries into the overall scene summary
            node.summary = self._synthesize(subscene_summaries, "scene", node.title)

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
        presence_matrix: List[Dict[str, Any]] = None,
        compression_model: Dict[str, Any] = None
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
        
        response_json = call_llm(prompt, system_instruction=system_instruction, json_mode=True, use_complex=True)
        
        try:
            data = parse_json_response(response_json)
        except Exception as e:
            print(f"[Director View Fallback] Error: {e}", flush=True)
            data = {}

        # ----------------------------------------------------
        # Robust Programmatic Character Importance Evaluation
        # ----------------------------------------------------
        evaluated_scores = self._evaluate_character_importance(
            relationship_graph, presence_matrix, scenes, beats, compression_model
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
        
        # Enrich top_hooks with evidence verbatim quote
        beat_desc_map = {b["id"]: b["description"] for b in beats}
        reconstructed_hooks = []
        for hook in top_hooks:
            bid = hook.get("beat_id")
            
            # Robustly normalize beat_id prefix for lookup in case LLM stripped/duplicated it
            lookup_id = bid
            if lookup_id:
                clean_id = str(lookup_id).replace("beat_", "")
                rebuilt_id = f"beat_{clean_id}"
                if rebuilt_id in beat_desc_map:
                    lookup_id = rebuilt_id
                    
            quote = beat_desc_map.get(lookup_id, hook.get("summary", "No description found."))
            hook["evidence"] = [
                {
                    "beat_id": lookup_id if lookup_id else bid,
                    "quote": quote
                }
            ]
            reconstructed_hooks.append(hook)
        data["top_hooks"] = reconstructed_hooks

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
            
        # Enrich main_conflicts with evidence beat & quote
        scenes_map = {s.id: s for s in scenes}
        reconstructed_conflicts = []
        for conf in main_conflicts:
            res_point = conf.get("resolution_point")
            scene = scenes_map.get(res_point)
            evidence_beat_id = ""
            evidence_quote = "No explicit resolution scene found."
            if scene:
                if scene.beats:
                    peak_beat = max(scene.beats, key=lambda b: b.get("tension", 0.0))
                    evidence_beat_id = peak_beat["id"]
                    evidence_quote = peak_beat["description"]
                else:
                    evidence_beat_id = scene.id
                    evidence_quote = scene.summary or scene.title
            
            conf["evidence_beat_id"] = evidence_beat_id
            conf["evidence_quote"] = evidence_quote
            reconstructed_conflicts.append(conf)
        data["main_conflicts"] = reconstructed_conflicts

        # Complete the final director_view dict
        critical_path_summary = []
        for s in scenes:
            climax_beat_id = s.beats[0]["id"] if s.beats else s.id
            climax_beat_desc = s.beats[0]["description"] if s.beats else (s.summary or s.title)
            if s.beats:
                peak_beat = max(s.beats, key=lambda b: b.get("tension", 0.0))
                climax_beat_id = peak_beat["id"]
                climax_beat_desc = peak_beat["description"]
            
            critical_path_summary.append({
                "scene_id": s.id,
                "summary": s.summary,
                "evidence": [
                    {
                        "beat_id": climax_beat_id,
                        "quote": climax_beat_desc
                    }
                ]
            })

        director_view = {
            "story_summary": root.summary,
            "main_characters": data.get("main_characters", []),
            "main_conflicts": data.get("main_conflicts", []),
            "critical_path_summary": critical_path_summary,
            "top_hooks": data.get("top_hooks", [])
        }
        return director_view

    def _evaluate_character_importance(
        self,
        relationship_graph: Dict[str, Any],
        presence_matrix: List[Dict[str, Any]],
        scenes: List[StoryNode],
        beats: List[Dict[str, Any]],
        compression_model: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]:
        """
        Evaluation mechanism: Programmatically calculates the importance score (0.0 to 1.0)
        for each character using the locked mathematical formula:
        importance_score = 0.4 * norm_app_freq + 0.4 * norm_rel_deg + 0.2 * critical_path_presence
        """
        importance_scores = {}
        nodes = relationship_graph.get("nodes", [])
        edges = relationship_graph.get("edges", [])
        
        if not nodes:
            return {}
            
        total_scenes = len(scenes) if scenes else 1
        critical_path_scenes = set()
        if compression_model:
            critical_path_scenes = set(compression_model.get("importance_tiers", {}).get("tier_1_core_path", []))
        
        # 1. Calculate appearance counts
        char_presence = {}
        if presence_matrix:
            for entry in presence_matrix:
                for char_id in entry.get("characters_present", []):
                    char_presence[char_id] = char_presence.get(char_id, 0) + 1
                    
        # 2. Calculate relationship degree
        char_degree = {}
        for edge in edges:
            src = edge.get("source")
            tgt = edge.get("target")
            if src:
                char_degree[src] = char_degree.get(src, 0) + 1
            if tgt:
                char_degree[tgt] = char_degree.get(tgt, 0) + 1
                
        max_rel_count = max(char_degree.values(), default=1)
        if max_rel_count == 0:
            max_rel_count = 1
            
        for node in nodes:
            char_id = node["id"]
            
            # Compute normalized appearance frequency
            presence_count = char_presence.get(char_id, 0)
            norm_app_freq = presence_count / total_scenes
            
            # Compute normalized relationship degree
            rel_count = char_degree.get(char_id, 0)
            norm_rel_deg = rel_count / max_rel_count
            
            # Compute critical path presence
            present_scenes = []
            if presence_matrix:
                for pm in presence_matrix:
                    if char_id in pm.get("characters_present", []):
                        present_scenes.append(pm["scene_id"])
            present_scenes_set = set(present_scenes)
            critical_path_presence = 1.0 if (present_scenes_set & critical_path_scenes) else 0.0
            
            # Calculate locked importance score
            importance_score = 0.4 * norm_app_freq + 0.4 * norm_rel_deg + 0.2 * critical_path_presence
            importance_scores[char_id] = round(importance_score, 2)
            
        return importance_scores

    def _synthesize_beat(self, description: str) -> str:
        """Lightweight synthesis of raw beat description into a concise beat summary using LLM."""
        system_instruction = (
            "You are a concise screenplay summarization assistant. "
            "CRITICAL RULE: You MUST retain all core entities (unique proper names of characters, locations, and specific items/weapons/relics) in the summary. Do not generalize proper nouns into generic terms."
        )
        prompt = f"Summarize the following action/dialogue into 1 concise sentence (in English, keeping all proper names):\n{description}"
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
            "You are an experienced screenwriter specializing in narrative structure summarization. "
            "CRITICAL RULE: You MUST retain all core entities (unique proper names of characters, locations, and specific items/weapons/relics) in the summary. Do not generalize proper nouns into generic terms."
        )
        prompt = f"Summarize the '{level}' section titled '{title}' based on the following child summaries (in English, 1-2 sentences, keeping all proper names):\n- {combined_text}"
        
        result = call_llm(prompt, system_instruction=system_instruction)
        if not result or "Error call_llm" in result or "Fallback LLM" in result:
            if level == "scene":
                return f"Scene: {title}. Key events: " + " -> ".join(summaries[:2]) + "..."
            elif level == "sequence":
                return f"Sequence '{title}' comprising scenes: " + ", ".join(summaries[:2])
            elif level == "act":
                return f"Act '{title}' progresses through sequences: " + ", ".join(summaries[:2])
            else:
                return f"Story overview '{title}': " + " | ".join(summaries[:2])
        return result
