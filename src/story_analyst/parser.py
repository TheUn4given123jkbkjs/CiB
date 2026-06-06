from typing import Dict, Any, Optional
import json

try:
    from .tree import StoryNode
    from .utils import generate_id, call_llm, parse_json_response
except ImportError:
    from tree import StoryNode
    from utils import generate_id, call_llm, parse_json_response

class StoryParser:
    """
    Stage 1: Parses raw narrative text using the LLM
    and populates a skeleton Story Tree structure with leaf beats.
    """
    def __init__(self):
        pass

    def parse(self, story_text: str) -> StoryNode:
        """
        Calls Gemini to segment raw text into structural nodes (Acts, Sequences, Scenes)
        and leaf beats, then constructs the StoryTree.
        """
        system_instruction = (
            "You are a script analysis engine. Segment the raw input text into acts, sequences, scenes, "
            "and individual beats. Return ONLY a valid JSON object matching the requested schema."
        )
        
        prompt = f"""
        Segment this story into Acts, Sequences, Scenes, and Beats.
        Identify the primary location of each Scene.
        For each Beat, classify its type as 'action', 'dialogue', or 'transition' and include its description (verbatim sentence or short clause from the source text).
        
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
                      "beats": [
                        {{
                          "type": "action|dialogue|transition",
                          "description": "text excerpt"
                        }}
                      ]
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
            data = parse_json_response(response_json)
        except Exception as e:
            print(f"[Parser Fallback] Error parsing JSON: {e}", flush=True)
            data = {}

        story_title = data.get("title", "Parsed Story")
        root = StoryNode(
            node_id=generate_id("story"),
            node_type="story",
            title=story_title
        )

        acts_data = data.get("acts", [])
        if not acts_data:
            # Simple fallback segmentation if LLM output is empty/invalid
            fallback_act = StoryNode(generate_id("act"), "act", "Act I")
            fallback_seq = StoryNode(generate_id("seq"), "sequence", "Sequence 1")
            fallback_scene = StoryNode(generate_id("scene"), "scene", "Scene 1", primary_location=generate_id("loc_unknown"))
            
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

        # Build the tree recursively from LLM JSON response
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
                    scene_node = StoryNode(
                        node_id=generate_id("scene"),
                        node_type="scene",
                        title=scene_data.get("title", "Untitled Scene"),
                        primary_location=generate_id("loc_" + scene_data.get("primary_location", "unknown").lower().replace(" ", "_"))
                    )
                    for beat_data in scene_data.get("beats", []):
                        scene_node.add_beat(
                            beat_id=generate_id("beat"),
                            beat_type=beat_data.get("type", "action"),
                            description=beat_data.get("description", ""),
                            summary=""
                        )
                    seq_node.add_child(scene_node)
                act_node.add_child(seq_node)
            root.add_child(act_node)

        return root
