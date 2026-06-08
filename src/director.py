import os
import sys
import json
from typing import Dict, Any, Optional

# Add the src folder to path for import compatibility
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from story_analyst.story_analyst import StoryAnalyst
except ImportError:
    from .story_analyst.story_analyst import StoryAnalyst

class Director:
    """
    Coordinates the execution of supporting agents. 
    In this stage, runs the Story Analyst on inputs/script.txt and 
    saves the resulting Semantic Story Blueprint to output/story_blueprint.json.
    """
    def __init__(self):
        self.story_analyst = StoryAnalyst()

    def run_story_analyst(self, script_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes the Story Analyst pipeline.
        
        Args:
            script_text (str, optional): The raw story text. If not provided, it attempts
                                         to load from 'inputs/script.txt'.
                                         
        Returns:
            dict: The compiled Semantic Story Blueprint JSON.
        """
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        inputs_dir = os.path.join(root_dir, "inputs")
        output_dir = os.path.join(root_dir, "outputs")

        # Create directories if they do not exist
        os.makedirs(inputs_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        script_path = os.path.join(inputs_dir, "script.txt")
        output_path = os.path.join(output_dir, "story_blueprint.json")

        if script_text is not None:
            # Save the passed script text as inputs/script.txt
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_text)
        else:
            # Try to read script from inputs/script.txt
            if not os.path.exists(script_path):
                # Fallback check for root test.txt if inputs/script.txt is missing
                root_test_path = os.path.join(root_dir, "test.txt")
                if os.path.exists(root_test_path):
                    print(f"[Director] 'inputs/script.txt' not found. Copying '{root_test_path}'...")
                    with open(root_test_path, "r", encoding="utf-8") as f:
                        script_text = f.read()
                    with open(script_path, "w", encoding="utf-8") as f:
                        f.write(script_text)
                else:
                    raise FileNotFoundError(
                        f"No script text provided, and neither '{script_path}' nor '{root_test_path}' exists."
                    )
            else:
                with open(script_path, "r", encoding="utf-8") as f:
                    script_text = f.read()

        print(f"[Director] Initiating Story Analyst understanding pipeline...")
        # Set compression mode: "NORMAL" (default), "COMPACT" (maximum compression), or "FULL" (complete detail)
        director_brief = {"blueprint_mode": "NORMAL"}
        blueprint = self.story_analyst.analyze(script_text, director_brief=director_brief)

        # Output the JSON to output/story_blueprint.json
        with open(output_path, "w", encoding="utf-8") as out:
            json.dump(blueprint, out, indent=2, ensure_ascii=False)

        print(f"[Director] Success! Saved Semantic Story Blueprint to '{output_path}'.")
        return blueprint

if __name__ == "__main__":
    # Ensure console output handles UTF-8 on Windows
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')

    director = Director()
    try:
        director.run_story_analyst()
    except Exception as e:
        print(f"[Director Error]: {e}")
