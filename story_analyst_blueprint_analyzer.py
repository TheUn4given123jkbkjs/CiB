import json
import os
import sys
from pathlib import Path

def analyze_blueprint(blueprint_path: str):
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
        
    print(f"Analyzing Blueprint: {blueprint_path}\n")
    
    if not os.path.exists(blueprint_path):
        print(f"Error: File not found at {blueprint_path}")
        return
        
    with open(blueprint_path, 'r', encoding='utf-8') as f:
        try:
            blueprint = json.load(f)
        except Exception as e:
            print(f"Error reading JSON: {e}")
            return
            
    stats = {}
    director = blueprint.get('director_view', {})
    
    stats['main_characters'] = len(director.get('main_characters', []))
    stats['main_conflicts'] = len(director.get('main_conflicts', []))
    stats['critical_path_summary'] = 1 if director.get('critical_path_summary') else 0
    stats['top_hooks'] = len(director.get('top_hooks', []))
    
    story_tree = blueprint.get('story_tree', {})
    act_count = sequence_count = scene_count = beat_count = summary_count = 0
    
    def traverse(node):
        nonlocal act_count, sequence_count, scene_count, beat_count, summary_count
        if node.get('summary'): 
            summary_count += 1
        t = node.get('type')
        if t == 'act': 
            act_count += 1
        elif t == 'sequence': 
            sequence_count += 1
        elif t == 'scene':
            scene_count += 1
            for beat in node.get('beats', []):
                beat_count += 1
                if beat.get('summary'): 
                    summary_count += 1
        for child in node.get('children', []):
            traverse(child)
            
    traverse(story_tree)
    
    stats['acts'] = act_count
    stats['sequences'] = sequence_count
    stats['scenes'] = scene_count
    stats['beats'] = beat_count
    stats['summaries'] = summary_count
    
    # Graphs
    stats['causality_nodes'] = len(blueprint.get('causality_graph', {}).get('nodes', []))
    stats['causality_edges'] = len(blueprint.get('causality_graph', {}).get('edges', []))
    
    stats['relationship_nodes'] = len(blueprint.get('character_relationship_graph', {}).get('nodes', []))
    stats['relationship_edges'] = len(blueprint.get('character_relationship_graph', {}).get('edges', []))
    stats['relationship_events'] = sum(
        len(edge.get('timeline', [])) 
        for edge in blueprint.get('character_relationship_graph', {}).get('edges', [])
    )
    
    prop_nodes = blueprint.get('asset_and_prop_graph', {}).get('nodes', [])
    stats['props'] = len(prop_nodes)
    stats['prop_states'] = sum(
        len(node.get('ownership_history', [])) + 
        len(node.get('location_history', [])) + 
        len(node.get('state_history', []))
        for node in prop_nodes
    )
    
    stats['presence_rows'] = len(blueprint.get('presence_matrix', []))
    stats['verification_rules'] = len(blueprint.get('reflection_verification_rules', []))
    
    print("=== Blueprint Statistics ===")
    for k, v in stats.items():
        print(f"{k:30}: {v}")
    print("=" * 28 + "\n")
    
    # Quality Scoring
    def clamp(x):
        return max(0.0, min(10.0, float(x)))
        
    # 1. Completeness Score (Max 10)
    completeness = (
        (2.5 if stats['main_characters'] > 0 else 0) +
        (2.5 if stats['main_conflicts'] > 0 else 0) +
        (2.5 if stats['critical_path_summary'] > 0 else 0) +
        (2.5 if stats['top_hooks'] > 0 else 0)
    )
    
    # 2. Graph Density Score (Max 10)
    total_nodes = stats['causality_nodes'] + stats['relationship_nodes'] + stats['props']
    total_edges = stats['causality_edges'] + stats['relationship_edges']
    graph_density = clamp((total_edges / max(total_nodes, 1)) * 10)
    
    # 3. Compression Score (Max 10)
    compression = blueprint.get('narrative_compression_model', {})
    tiers = compression.get('importance_tiers', {})
    total_scenes_in_tiers = sum(len(v) for v in tiers.values())
    compression_score = clamp((total_scenes_in_tiers / max(stats['scenes'], 1)) * 10)
    
    # 4. Hook Quality Proxy (Max 10)
    hook_score = clamp(stats['top_hooks'] * 3.33)
    
    # 5. Continuity & Resilience Score (Based on rules and asset tracking states, Max 10)
    continuity_score = clamp(stats['verification_rules'] / max(stats['scenes'], 1) * 10)
    
    overall = round((
        completeness +
        graph_density +
        compression_score +
        hook_score +
        continuity_score
    ) / 5, 2)
    
    print("=== Quality Metrics ===")
    print(f"Completeness Score : {round(completeness, 2)} / 10")
    print(f"Graph Density Score: {round(graph_density, 2)} / 10")
    print(f"Compression Score : {round(compression_score, 2)} / 10")
    print(f"Hook Quality Proxy : {round(hook_score, 2)} / 10")
    print(f"Continuity Score    : {round(continuity_score, 2)} / 10")
    print("-" * 23)
    print(f"Overall Blueprint Score: {overall} / 10\n")

if __name__ == "__main__":
    blueprint_path = 'outputs/story_blueprint.json'
    if len(sys.argv) > 1:
        blueprint_path = sys.argv[1]
    analyze_blueprint(blueprint_path)
