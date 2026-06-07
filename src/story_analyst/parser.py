from typing import Dict, List, Any, Optional
import json
import re

try:
    from .tree import StoryNode
    from .utils import generate_id, call_llm, parse_json_response
except ImportError:
    from tree import StoryNode
    from utils import generate_id, call_llm, parse_json_response

class StoryParser:
    """
    Stage 1: Parses raw narrative text using a two-stage process:
    1. Scene Discovery: Identifies acts, sequences, scene boundaries, locations, and confidence levels.
    2. Beat Extraction: Extracts verbatim beats locally within discovered scene boundaries.
    """
    def __init__(self):
        pass

    def parse(self, story_text: str) -> StoryNode:
        """
        Runs the two-stage parsing pipeline on raw story text and returns the Story Tree.
        """
        # Stage 1: Scene Discovery
        discovery_data = self._discover_scenes(story_text)
        
        story_title = discovery_data.get("title", "Parsed Story")
        root = StoryNode(
            node_id=generate_id("story"),
            node_type="story",
            title=story_title
        )

        acts_data = discovery_data.get("acts", [])
        if not acts_data:
            # Fallback simple parsing if Scene Discovery fails completely
            return self._fallback_parse(story_text, root)

        # Build tree and perform Stage 2: Beat Extraction per scene
        for act_data in acts_data:
            act_node = StoryNode(
                node_id=generate_id("act"),
                node_type="act",
                title=act_data.get("title", "Untitled Act")
            )
            for seq_data in act_data.get("sequences", []):
                seq_node = StoryNode(
                    node_id=generate_id("seq"),
                    node_type="sequence",
                    title=seq_data.get("title", "Untitled Sequence")
                )
                for scene_data in seq_data.get("scenes", []):
                    scene_title = scene_data.get("title", "Untitled Scene")
                    start_cue = scene_data.get("start_cue", "").strip()
                    end_cue = scene_data.get("end_cue", "").strip()
                    confidence = scene_data.get("confidence", 1.0)
                    
                    # Isolate text of the scene using cues
                    scene_text = self._extract_scene_text(story_text, start_cue, end_cue)
                    
                    scene_node = StoryNode(
                        node_id=generate_id("scene"),
                        node_type="scene",
                        title=scene_title,
                        primary_location=generate_id("loc_" + scene_data.get("primary_location", "unknown").lower().replace(" ", "_")),
                        tension_peak=0.0
                    )
                    
                    # Store confidence score and source_chunk info on the scene node
                    scene_node.confidence = confidence
                    scene_node.source_chunk = "chunk_0"  # For short scripts, chunking is single-pass
                    
                    # Stage 2: Beat Extraction for this scene
                    beats = self._extract_beats(scene_title, scene_text)
                    for beat in beats:
                        scene_node.add_beat(
                            beat_id=generate_id("beat"),
                            beat_type=beat.get("type", "action"),
                            description=beat.get("description", ""),
                            summary=""
                        )
                        
                    seq_node.add_child(scene_node)
                act_node.add_child(seq_node)
            root.add_child(act_node)

        return root

    def _discover_scenes(self, story_text: str) -> Dict[str, Any]:
        """Stage 1: Discover structural hierarchy and scene boundaries."""
        system_instruction = (
            "You are a script analysis engine. Segment the raw input text into acts, sequences, and scenes. "
            "For each scene, identify the scene title, primary location, verbatim start sentence/phrase, and verbatim end sentence/phrase. "
            "Evaluate your boundary 'confidence' score (float between 0.0 and 1.0). "
            "Return ONLY a valid JSON object matching the requested schema."
        )
        
        prompt = f"""
        Analyze this raw story text and discover the hierarchy of Acts, Sequences, and Scenes.
        
        Story Text:
        ---
        {story_text}
        ---
        
        Return a JSON object with this structure:
        {{
          "title": "Story Title",
          "acts": [
            {{
              "title": "Act Title",
              "sequences": [
                {{
                  "title": "Sequence Title",
                  "scenes": [
                    {{
                      "title": "Scene Title",
                      "primary_location": "location name",
                      "start_cue": "verbatim first sentence/phrase of this scene in the text",
                      "end_cue": "verbatim last sentence/phrase of this scene in the text",
                      "confidence": "this score is the confidence of your segmentation. score is float between 0.0 and 1.0. 1.0 means high confidence"
                    }}
                  ]
                }}
              ]
            }}
          ]
        }}
        """
        
        response_json = call_llm(prompt, system_instruction=system_instruction, json_mode=True)
        try:
            return parse_json_response(response_json)
        except Exception as e:
            print(f"[Scene Discovery] Error: {e}", flush=True)
            return {}

    def _extract_beats(self, scene_title: str, scene_text: str) -> List[Dict[str, Any]]:
        """Stage 2: Extract verbatim beats within a single scene context."""
        if not scene_text.strip():
            return []
            
        system_instruction = (
            "You are a script analysis engine. Extract chronologically ordered beats from the provided scene text. "
            "For each beat, classify its type as 'action', 'dialogue', or 'transition' and include its description (verbatim sentence or short clause from the source text). "
            "Return ONLY a valid JSON object matching the requested schema."
        )
        
        prompt = f"""
        Extract individual beats from this scene.
        Ensure descriptions are verbatim sentences or clauses from the scene text. Do not summarize or synthesize here.
        
        Scene Title: {scene_title}
        Scene Text:
        ---
        {scene_text}
        ---
        
        Return a JSON object with this structure:
        {{
          "beats": [
            {{
              "type": "action|dialogue|transition",
              "description": "verbatim text excerpt"
            }}
          ]
        }}
        """
        
        response_json = call_llm(prompt, system_instruction=system_instruction, json_mode=True)
        try:
            data = parse_json_response(response_json)
            return data.get("beats", [])
        except Exception as e:
            print(f"[Beat Extraction Failed] Error: {e} for scene {scene_title}", flush=True)
            # Local paragraph fallback
            fallback_beats = []
            paragraphs = [p.strip() for p in scene_text.split("\n") if p.strip()]
            for p in paragraphs:
                btype = "dialogue" if p.startswith("–") or p.startswith("-") or "”" in p else "action"
                fallback_beats.append({"type": btype, "description": p})
            return fallback_beats

    def _extract_scene_text(self, story_text: str, start_cue: str, end_cue: str) -> str:
        """Helper to cleanly extract scene text between start and end cues."""
        if not start_cue or not end_cue:
            return story_text
            
        # Clean cues for simple string searching
        start_cue_clean = start_cue.strip()
        end_cue_clean = end_cue.strip()
        
        # Simple index search
        start_idx = story_text.find(start_cue_clean)
        if start_idx == -1:
            # Try finding first word
            first_word = start_cue_clean.split()[0] if start_cue_clean.split() else ""
            start_idx = story_text.find(first_word) if first_word else 0
            if start_idx == -1:
                start_idx = 0
                
        end_idx = story_text.find(end_cue_clean, start_idx)
        if end_idx == -1:
            # Try finding last word
            last_word = end_cue_clean.split()[-1] if end_cue_clean.split() else ""
            end_idx = story_text.find(last_word, start_idx) if last_word else -1
            if end_idx == -1:
                end_idx = len(story_text)
            else:
                end_idx += len(last_word)
        else:
            end_idx += len(end_cue_clean)
            
        scene_text = story_text[start_idx:end_idx].strip()
        return scene_text if scene_text else story_text

    def _fallback_parse(self, story_text: str, root: StoryNode) -> StoryNode:
        """Default fallback parsing if Scene Discovery fails entirely."""
        print("[Parser] Falling back to default paragraph segmentation", flush=True)
        fallback_act = StoryNode(generate_id("act"), "act", "Act I")
        fallback_seq = StoryNode(generate_id("seq"), "sequence", "Sequence 1")
        fallback_scene = StoryNode(generate_id("scene"), "scene", "Scene 1", primary_location=generate_id("loc_unknown"))
        fallback_scene.confidence = 0.5
        fallback_scene.source_chunk = "chunk_0"
        
        paragraphs = [p.strip() for p in story_text.split("\n") if p.strip()]
        if not paragraphs:
            paragraphs = ["No text content found."]
            
        for para in paragraphs:
            beat_type = "dialogue" if para.startswith("–") or para.startswith("-") or "”" in para else "action"
            fallback_scene.add_beat(generate_id("beat"), beat_type, para)
            
        fallback_seq.add_child(fallback_scene)
        fallback_act.add_child(fallback_seq)
        root.add_child(fallback_act)
        return root
