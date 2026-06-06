from typing import Dict, List, Any, Optional

class StoryNode:
    """
    Represents a structural element within the hierarchical Story Tree.
    Can represent a 'story', 'act', 'sequence', or 'scene'.
    """
    VALID_TYPES = {"story", "act", "sequence", "scene"}

    def __init__(
        self,
        node_id: str,
        node_type: str,
        title: str,
        summary: str = "",
        primary_location: Optional[str] = None,
        tension_peak: float = 0.0
    ):
        if node_type not in self.VALID_TYPES:
            raise ValueError(f"Invalid node_type '{node_type}'. Must be one of {self.VALID_TYPES}")

        self.id = node_id
        self.type = node_type
        self.title = title
        self.summary = summary
        self.children: List['StoryNode'] = []
        self.beats: List[Dict[str, Any]] = []  # Active only if node_type is "scene"
        self.primary_location = primary_location
        self.tension_peak = tension_peak
        self.derived_from: List[str] = []

    def add_child(self, child: 'StoryNode') -> None:
        """Adds a sub-component (e.g. adding an Act to a Story, or a Sequence to an Act)."""
        if self.type == "scene":
            raise TypeError("Scene nodes cannot have children nodes. Use add_beat() instead.")
        self.children.append(child)

    def add_beat(
        self,
        beat_id: str,
        beat_type: str,
        description: str,
        summary: str = "",
        tension: float = 0.0,
        energy: float = 0.0
    ) -> None:
        """Adds a leaf beat to a scene node."""
        if self.type != "scene":
            raise TypeError("Beats can only be added to nodes of type 'scene'.")
        
        valid_beat_types = {"action", "dialogue", "transition"}
        if beat_type not in valid_beat_types:
            raise ValueError(f"Invalid beat_type '{beat_type}'. Must be one of {valid_beat_types}")

        beat = {
            "id": beat_id,
            "type": beat_type,
            "description": description,
            "summary": summary,
            "tension": tension,
            "energy": energy
        }
        self.beats.append(beat)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the node and its descendants into the Semantic JSON blueprint format."""
        data = {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "summary": self.summary,
            "derived_from": self.derived_from
        }

        if self.type == "scene":
            data["beats"] = self.beats
            data["tension_peak"] = self.tension_peak
            data["primary_location"] = self.primary_location
        else:
            data["children"] = [child.to_dict() for child in self.children]

        return data
