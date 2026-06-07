# Story Analyst Architecture & Quality Review

**Role:** Senior AI Systems Architect & Narrative Intelligence Engineer
**Object Under Review:** Story Analyst Agent (Cinematic Intelligence Builder - CiB)
**Date of Review:** June 7, 2026

---

## Executive Summary

The Story Analyst agent serves as the core **Story Understanding Engine** of the Cinematic Intelligence Builder (CiB). Its primary goal is to parse raw story text, extract hierarchical trees, synthesize causal and relationship graphs, track assets/props, perform bottom-up recursive summarization, and export a structured **Semantic Story Blueprint (JSON)**.

While the agent successfully delivers on schema compliance and separation of concerns ("Analyze, Don't Direct"), it is currently in a **Functional Prototype** stage. It is heavily limited by extreme token inefficiency (making sequential individual LLM calls for every beat), a complete lack of chunking or map-reduce mechanisms for long text scalability, and a critical placeholder in the visual compiler where the mood and theme maps are completely hardcoded.

---

## SECTION 1: Architecture Review

### Evaluation
* **Separation of Concerns:** 9/10. Highly separated. Modules map directly to stages of the narrative analysis pipeline. Directorial assumptions are successfully excluded.
* **Data Flow & Pipeline Design:** 8/10. A clear 7-stage sequential pipeline.
* **Scalability to Long Stories:** 2/10. Extremely low. Single-pass processing will overflow context limits on longer texts.
* **Maintainability & Extensibility:** 8/10. Clean Python class structures.

### Key Strengths
* High isolation of duties. Downstream visual/storyboard agents receive highly structured semantic data without needing to re-parse the raw script.
* Unified entry point (`StoryAnalyst.analyze`) coordinates all engines cleanly.

### Key Weaknesses & Bottlenecks
* **Fully Sequential Execution:** No parallelization is used, even though several stages (like Graph Synthesis and Asset Tracking) have no inter-dependencies.
* **Context Redundancy:** The raw text is re-read by multiple modules (Parser, Graph Engine, Asset Engine, Visual Compiler), multiplying input token costs.

> [!CAUTION]
> **Scalability Risk:** The pipeline will fail on novels or scripts with more than ~5,000 words due to single-prompt context constraints and JSON output length limits.

* **Architecture Score: 6.5 / 10**

---

## SECTION 2: Parser Review (`parser.py` & `tree.py`)

### Evaluation
* **Story Decomposition:** 7/10. Act-Sequence-Scene-Beat hierarchy is logical.
* **Scene Segmentation:** 5/10. Entirely non-deterministic since it relies on a single LLM call to output the full skeleton.
* **Robustness:** 4/10. High risk of parsing errors on raw prose or web novels.
* **Fallback Mechanisms:** 5/10. The fallback collapses the hierarchy into a single Act/Sequence/Scene structure.

### Key Strengths
* Verbatim beat extraction preserves original script dialogue and action lines.
* Node serialization (`StoryNode.to_dict`) is clean and robust.

### Key Weaknesses
* **Novels & Web Novels:** Cannot reliably process novels due to length limits.
* **Script Formatting Dependency:** Highly dependent on structured inputs. Translated content or poorly formatted scripts easily break JSON segment maps.

* **Parser Score: 5.5 / 10**

---

## SECTION 3: Graph Engine Review (`graph_engine.py`)

### Evaluation
* **Character Extraction:** 8/10. Optimized 2-Phase pipeline (extracting characters first, then relationships) reduces token overload.
* **Relationship Evolution:** 8/10. Stance, valence, and power balance are mapped to specific beat IDs, making them dynamic.
* **Causality Graph:** 6/10. Causal necessity prompt is well-designed.
* **Causality Fallback:** 3/10. Falls back to a flat chronological chain (A -> B -> C), violating semantic rules.

### Key Strengths
* Timeline-based stance evolution tracking allows downstream storyboarders to see exactly when character relationships shift.
* Strict validation of causal necessity (logical dependency) over chronological sequence.

### Key Weaknesses
* As script length increases, the relationship inference prompt becomes extremely expensive, as it requires matching every character pair across all beats.

* **Graph Engine Score: 7.0 / 10**

---

## SECTION 4: Asset Tracker Review (`asset_tracker.py`)

### Evaluation
* **Prop Extraction:** 7/10. Uses LLM to identify weapons, documents, and key items.
* **Prop State Propagation:** 9/10. **Excellent optimization.** The LLM only extracts mutations (location/state changes), while chronological propagation is calculated deterministically in Python.
* **Continuity Preservation:** 8/10. Defaults unknown locations to the parent scene's primary location.

### Key Strengths
* Dramatically reduces token count and costs by avoiding per-beat LLM queries for state.
* The state propagation logic prevents visual continuity drift.

### Key Weaknesses
* **Implicit Mutations:** If a character carries an item to a new room but the script doesn't explicitly describe the mutation, the tracker will miss the move.

* **Asset Tracker Score: 8.0 / 10**

---

## SECTION 5: Recursive Summarization Review (`summarizer.py`)

### Evaluation
* **Bottom-Up Summarization:** 8/10. Hierarchical synthesis is clean.
* **Proper Noun Retention:** 9/10. Guardrails successfully preserve names (e.g., "Arthur" instead of "a student").
* **Director's View:** 7/10. Gathers main characters, conflicts, and hooks correctly.
* **Summarization Efficiency:** 2/10. **Worst part of the system.**

### Key Bottleneck
* **LLM Call Explosion:** Summarizing a story with $N$ beats requires $N$ separate sequential LLM calls just for the beats, plus calls for scenes, sequences, acts, and the root. For 60 beats, this translates to over 70 sequential API calls, creating massive latency (2-3 minutes per run) and quota limits (429 errors).

* **Summarizer Score: 5.0 / 10**

---

## SECTION 6: Compression Engine Review (`compression.py`)

### Evaluation
* **Narrative Compression:** 8/10. Successfully groups scenes into Core Path, Subplots, and Atmospheric.
* **Importance Ranking:** 8/10. Relies on dynamic range classification and soft rebalancing, neutralizing flat score issues.
* **Pruning Logic:** 7/10. Generates clean dependency-based pruning rules.
* **Tension/Energy Curves:** 6/10. Brittle keyword-based heuristics combined with scene-level LLM scaling.

### Key Strengths
* High resilience to flat fallback scores.
* Coherent pruning rules ensure that if a scene/beat is cut, its logical dependencies are also cut.

### Key Weaknesses
* Heuristics rely on a hardcoded string search of Vietnamese/English tension keywords, which misses contextual drama or subtext.

* **Compression Score: 7.5 / 10**

---

## SECTION 7: Visual Semantic Review (`visual_compiler.py`)

### Evaluation
* **Character Profile Invariants:** 8/10. Gathers physical look parameters, aligning IDs with the relationship graph.
* **Location Profile Invariants:** 7/10. Stable scene descriptions.
* **Mood/Theme Mapping:** 1/10. **Critical placeholder.** 

> [!WARNING]
> **Hardcoded Placeholder:** The compiler completely bypasses semantic analysis for moods and themes. It hardcodes `{"primary_mood": "mysterious", "primary_theme": "discovery"}` for every single segment ID in the tree.

* **Visual Compiler Score: 4.0 / 10**

---

## SECTION 8: Token Efficiency Review

### Evaluation
* **LLM Usage Strategy:** 3/10. Heavy redundancy and sequential call overload.
* **Prompt Reuse:** 4/10. The same raw text is sent to multiple prompts instead of batching analyses.
* **Cost Efficiency:** 2/10. Extremely high cost-per-run due to individual beat summarizations.

### Key Suggestions
* Batch beat summarization (e.g. summarize 10 beats in a single LLM call).
* Cache LLM outputs based on beat description hashes.

* **Token Efficiency Score: 3.0 / 10**

---

## SECTION 9: CodeWiki Comparison

### Evaluation
* **Tree Construction:** Similar to folder/file structures. (Successful)
* **Graph Construction:** Similar to import/dependency graphs. (Successful)
* **Missing Concepts:** 
  1. **Incremental Updates:** CodeWiki only re-analyzes modified files. Story Analyst re-runs the entire pipeline for minor script edits.
  2. **Chunking / Map-Reduce:** CodeWiki chunks codebases of millions of lines. Story Analyst fails on long prose.
  3. **Semantic Code Search:** Lacks vector database support.

* **CodeWiki Alignment Score: 6.0 / 10**

---

## SECTION 10: Blueprint Quality Review

### Evaluation
* **Schema Compliance:** 10/10. Blueprint matches schema v3.1.0 perfectly.
* **Strongest Sections:** `story_tree` hierarchy, `presence_matrix`, `reflection_verification_rules`.
* **Weakest Sections:** Hardcoded `mood_theme_map`, flat causality fallback.
* **Downstream Value:** 9/10. Very high. Downstream storyboard and prompt agents have all necessary parameters in a single queryable JSON.

* **Blueprint Quality Score: 7.5 / 10**

---

## FINAL VERDICT

### 1. Module Score Table

| Module | Score | Critical Issues |
| :--- | :---: | :--- |
| **parser.py** | 5.5 | Brittle single-pass segmentation; non-scalable; hierarchy collapses on fallback. |
| **tree.py** | 8.5 | Clean object model; good serialization. |
| **graph_engine.py** | 7.0 | High token cost; fallback defaults to linear chronological chaining. |
| **asset_tracker.py** | 8.0 | Great state propagation logic; can miss implicit ownership movements. |
| **summarizer.py** | 5.0 | Sequential LLM call explosion (1 call per beat); high latency. |
| **compression.py** | 7.5 | Dynamic range classification works well; heuristics are brittle. |
| **visual_compiler.py**| 4.0 | Mood/theme maps are entirely hardcoded to placeholders. |
| **utils.py** | 8.0 | Robust JSON regex parser; lacks API call batching or retry/backoff. |
| **story_analyst.py** | 7.0 | Clean orchestrator; runs sequentially without parallel execution. |

### 2. Top 10 Architectural Strengths
1. **Director-Centric Separation:** Complete isolation from downstream directorial choices.
2. **Dynamic Range Partitioning:** Adapts to arbitrary tension values for balanced tiering.
3. **2-Phase Graph Synthesis:** Separation of character node extraction and stance evolution logic.
4. **Deterministic Prop Propagation:** Mutation-only LLM queries combined with chronological propagation in Python.
5. **Proper Noun Guardrails:** Strictly retains names in summaries to prevent semantic drift.
6. **Presence Matrix Integrity:** Cross-validates character/prop IDs across the story tree.
7. **Lineage Tracking:** `derived_from` field records summary source beat/scene IDs.
8. **Automated Reflection Rules:** Generates exact verification constraints for downstream agents.
9. **Robust JSON Parsing:** Utility regex repairs unescaped quotes/newlines to handle LLM quirks.
10. **Decoupled Architecture:** Clean structure allows independent module upgrades.

### 3. Top 10 Architectural Weaknesses
1. **Hardcoded Visual Layer:** Mood/theme maps are completely static placeholders.
2. **Recursive Summarization Latency:** $N$ sequential LLM calls for $N$ beats creates a severe performance bottleneck.
3. **No Chunking/Map-Reduce:** Fails to scale to novels or long narrative chapters.
4. **Causality Fallback Violation:** Flat chronological chaining violates logical necessity rules.
5. **Context Window Overlap:** Redundant loading of script text across multiple stages.
6. **No parallelization:** Fully synchronous execution stages.
7. **Keyword-Based Tension Heuristics:** Fails to capture subtextual or contextual drama.
8. **NER Limitations:** Asset tracker misses implicit prop movements.
9. **No Caching:** Modified scripts trigger complete re-analysis.
10. **Lack of Semantic Lineage:** `derived_from` stores IDs but doesn't explain the logic of synthesis.

### 4. Top 10 Highest Priority Improvements
1. **Dynamically Analyze Mood/Theme:** Replace the hardcoded visual compiler mappings with actual LLM analysis.
2. **Batch Beat Summarizations:** Combine beat summaries into 5-10 chunk prompts to reduce N LLM calls.
3. **Implement Chunking Parser:** Allow processing of novels using a sliding window parser.
4. **Parallelize Pipelines:** Run Graph synthesis, Visual compilation, and Asset tracking concurrently.
5. **Replace Chronological Causality Fallback:** Fallback to a disconnected graph or local dependencies instead of a fake linear chain.
6. **Implement Embedding-Based Caching:** Skip LLM calls for unchanged beats based on hash matching.
7. **Refine Tension Heuristics:** Use sentiment/valence analysis rather than simple keyword matching.
8. **Track Implicit Prop Movements:** Prompt the LLM to identify when a character leaves a room carrying a prop.
9. **Implement Retry & Backoff:** Add robust rate limit and error handling to the global LLM wrapper.
10. **Add Entity Registry:** Standardize IDs in the parser step to prevent inconsistencies down the road.

### 5. Biggest Current Bottleneck
* **The sequential LLM call loop in `summarizer.py`:** Generating summaries for $N$ beats takes a massive amount of time and is highly prone to rate limit errors.

### 6. Biggest Long-Term Scalability Risk
* **Lack of Chunking/Map-Reduce:** The agent cannot process full novels or long story scripts without hitting token window limits.

---

### Overall Story Analyst Score: 6.1 / 10

### Maturity Classification: Functional Prototype

### Estimated Completion: 60%
**Justification:** The core pipelines are fully written, schema-compliant, and integrate smoothly with the Director. However, the system is not yet production-ready. The massive sequential LLM calls make it slow and expensive, and the hardcoded visual maps and brittle fallbacks represent gaps in narrative intelligence.
