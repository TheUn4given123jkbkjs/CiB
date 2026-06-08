# Architecture Decisions

## Decision 001

Title:
Director-Centric Architecture

Status:
Accepted

Date:
04/06/2026

---

## Decision 002

Title:
Agent Isolation

Status:
Accepted

Date:
04/06/2026

---

## Decision 003

Title:
Controlled Context Loading

Status:
Accepted

Date:
04/06/2026

---

## Decision 004

Title:
Story Analyst Conceptual Design

Status:
Accepted

Date:
04/06/2026

Description:
Defined the purpose, responsibilities, and I/O for the Story Analyst agent. It will focus on narrative decomposition and structured JSON output (Story Blueprint) to bridge the gap between prose and cinematic structure.

---

## Decision 005

Title:
Story Analyst Redesign: Story Understanding Engine

Status:
Accepted

Date:
04/06/2026

Description:
Redesigned the Story Analyst to act as a Story Understanding Engine inspired by repository code analysis. To prevent over-engineering, the agent is strictly bounded to extract narrative facts (Story Tree, Causality Graph, Character Relationship Graph, Asset/Prop tracking, Presence Matrix, Compression Tiers, and Verification Rules). Directorial choices (camera angles, shot types, lighting style, and transitions) are deliberately excluded and delegated to downstream agents (Director and Storyboard).

---

## Decision 006

Title:
Recursive Understanding and Director's View

Status:
Accepted

Date:
06/06/2026

Description:
Introduced a bottom-up Recursive Summarization flow (Beat → Scene → Sequence → Act → Story) in the Story Analyst. Each node in the Story Tree compiles summaries from its children. A top-level `director_view` block (Executive Summary) is added to the blueprint. This provides downstream agents, particularly the Director, with a clean semantic index to query the story at different levels of abstraction without parsing raw narrative text.

---

## Decision 007

Title:
Story Analyst Prompt & Data-Flow Optimization

Status:
Accepted

Date:
06/06/2026

Description:
Optimized pipeline data-flow and model interaction for the Story Analyst. 
Specifically:
1. Reused graph context (characters and asset graphs) in the summarizer and visual compiler to align character/prop IDs.
2. Implemented two-stage tension/energy scoring: beat-level text heuristics (Stage 1) followed by higher-level scene scoring using LLM (Stage 2) to scale/enhance the profiles.
3. Implemented state mutation extraction for assets and chronological propagation using Python logic.
4. Added core entity guardrails to retain proper names in summaries, improved cinematic hook selection (prioritizing mystery/revelation/threat), and excluded cinematic/camera setup from visual invariants.
5. Added derived_from fields in the Story Tree to track summary provenance/lineage.

---

## Decision 008

Title:
Director's View Fallback Extractor & Environment Configuration

Status:
Accepted

Date:
06/06/2026

Description:
Implemented a robust fallback system in the Recursive Summarization Engine to guarantee completeness of the `director_view` (specifically `main_characters`, `main_conflicts`, and `top_hooks`). If the LLM returns empty arrays, Python-side fallbacks programmatically extract characters from the relationship graph, select trailer hooks from the highest-tension beats, and identify conflicts from the highest-tension scenes. Additionally, integrated parent directory scanning for `.env` to automatically configure `GEMINI_API_KEY` for local run simplicity.

---

## Decision 009

Title:
Separation of Character Extraction and Relationship Inference in Graph Synthesis

Status:
Accepted

Date:
06/06/2026

Description:
To resolve prompt weight overload and improve reliability when generating the character relationship graph (avoiding empty responses under 429 quota limits or heavy token contexts), the synthesis process was split into a 2-Phase pipeline:
1. Phase 1 (Character Extraction): Queries LLM solely to extract character nodes (ID, name, archetype, traits).
2. Phase 2 (Relationship Inference): Given the extracted character nodes and script beats, queries LLM to trace stance and relationship evolution over the timeline.
Additionally, added a coordinator-level fallback in `StoryAnalyst.analyze`: if the character nodes list remains empty, it dynamically reconstructs default nodes using character IDs present in the `presence_matrix`.

---

## Decision 010

Title:
Dynamic Range Classification for Narrative Importance Tiers

Status:
Accepted

Date:
06/06/2026

Description:
To resolve issues where all scenes cluster into a single importance tier (such as tier_1_core_path) due to uniform or high fallback tension values, the categorization logic in `compression.py` was refactored:
1. Removed absolute hardcoded score thresholds (0.7 and 0.4).
2. Implemented dynamic range-based relative thresholding using $R = \text{max\_peak} - \text{min\_peak}$ across the story.
3. Implemented a fallback distribution mechanism: if any of the three tiers is completely empty (under stories containing >= 3 scenes), it automatically sorts the scenes by tension and partitions them into three equal-ish slices. This guarantees balanced representations in Core Path, Subplots, and Atmospheric tiers.

---

## Decision 011

Title:
Sprint 1 Foundation Stabilization - Story Analyst Refactor

Status:
Accepted

Date:
07/06/2026

Description:
Refactored the Story Analyst pipeline to stabilize performance, improve token efficiency, and align with CodeWiki's hierarchical structure analysis patterns. Specifically:
1. Two-Stage Parser: Separated `parser.py` into a Scene Discovery stage (structural mapping and confidence score output) and a Beat Extraction stage (local verbatim beat extraction).
2. Summarizer Redesign: Batched all beat and scene summaries of a scene in a single LLM call per scene (saving over 80% of API calls) with token-budget subscene partitioning (6,000 token limit).
3. Independent Merge Engine: Created `merge_engine.py` to de-duplicate character, location, and prop IDs, output an Entity Registry catalog, and unify all IDs in the tree and graphs (with source_chunk lineage mapping).
4. Hybrid Causality: Redesigned the graph engine to build local causality (beat-to-beat within a scene) and global causality (scene-to-scene via scene summaries), using empty lists for fallbacks instead of fake chronological chains.

---

## Decision 012

Title:
Story Analyst Sprint 2 - Semantic Quality & Registry Centricity

Status:
Accepted

Date:
07/06/2026

Description:
Refactored the Story Analyst pipeline to enhance semantic data structures, establish a Single Source of Truth (SSOT) for narrative entities, and enforce architectural quality metrics:
1. Entity Registry Centricity: Shifted the Entity Registry discovery phase to the absolute front of the pipeline (immediately following initial parsing). This registry acts as the SSOT. Subsequent stages (graphs, asset tracker, summarizer, visual compiler) resolve raw name extractions to canonical Registry IDs using the generated alias map.
2. Entity Lineage: Enriched the Entity Registry to explicitly track entity name variants and aliases (e.g. Lý Vân Tiêu, Lý thiếu gia, hắn) as a lineage lineage/alias array, preparing the system for cross-chapter memory and retrieval.
3. Temporal Relationship Timelines with Confidence: Transformed flat character relationship edges into chronological event timelines that track power balance, emotional valence, and extraction confidence (0.0 to 1.0) per stance change event.
4. Split Asset Histories: Refactored flat prop states in the asset graph into three distinct, chronologically-tracked timelines within each prop node: ownership_history, location_history, and state_history.
5. Batched Mood & Theme Analysis: Replaced static/mock atmospheric mapping with dynamic LLM inference by batching scene summaries into a single call, preventing quota limits and scaling issues.
6. Architecture-Driven Quality KPIs: Replaced arbitrary numeric metrics with concrete structural integrity checks: zero duplicate entity IDs, zero orphan graph edges, registry coverage > 90%, asset continuity consistency > 95%, and relationship timeline validity > 95%.

---

## Decision 013

Title:
Graceful Partial Blueprint Return on Quota Exhaustion

Status:
Accepted

Date:
07/06/2026

Description:
Implemented a resilience mechanism to handle persistent Gemini API 429 quota exhaustion errors during sequential pipeline runs under the Free Tier rate limits:
1. Custom Quota Exception: Added `QuotaLimitReachedException` to `utils.py`, raised only after the retry-and-backoff mechanism (max 3 retries with 12s sleep) is fully exhausted.
2. Graceful Catch & Early Return: Wrapped the 10 stages of the pipeline in `story_analyst.py` with a `try...except QuotaLimitReachedException` block. 
3. Default Object Initialization: Pre-initialized all output variables with empty default configurations. If quota exhaustion occurs at any point, the pipeline terminates further LLM requests (conserving key quotas) and immediately returns the assembled blueprint containing whatever partial details were successfully generated up to that stage.

---

## Decision 014

Title:
Story Analyst Sprint 4 - Hybrid Routing, Registry Metadata & Verbatim Evidence

Status:
Accepted

Date:
08/06/2026

Description:
Refactored the Story Analyst pipeline to support hybrid model execution, full local connectivity fallback, verbatim audit trails, and enriched metadata:
1. Hybrid LLM Routing: Integrated a `use_complex=True` parameter in `call_llm` to route logical reasoning tasks (causality graph, relationship timelines, and director view) to a remote high-reasoning model (Gemini 2.5 Flash), while leaving local token-heavy tasks (beat extraction, summaries) on standard configurations.
2. Robust Fallback Resilience: Enabled automatic full fallback from Ollama to Gemini API. If the local Ollama server is offline or unreachable, `call_llm` catches the connection/timeout error, logs an warning, and automatically swaps configurations to run via Gemini API, using active rate-limit retry backoffs.
3. Programmatic Verbatim Evidence Backfilling: Added an audit trail to all semantic outcomes. Instead of letting the LLM output paraphrased quotes, the LLM returns the beat ID, and Python looks up the exact verbatim quote in the story tree to populate `evidence` arrays programmatically. This ensures 100% factual accuracy and saves considerable output tokens.
4. Statistical Metadata Enrichment: Enriched the Entity Registry characters, locations, and props programmatically in Python at the end of the pipeline with statistical metrics (appearance frequency, first/last seen scene IDs, relationship count, and importance score) using tree traversal.
5. DAG Causality Validation: Implemented a DFS-based cycle detection pass in graph engine to check and prune any cyclic edges, ensuring the Causality Graph represents a mathematically sound Directed Acyclic Graph (DAG).

---

## Decision 015

Title:
Sprint 4 Architectural Alignment & Verification (Tiered Evidence, Locked Formula, and Story Fact Registry)

Status:
Accepted

Date:
08/06/2026

Description:
To stabilize the pipeline, limit JSON growth, align hybrid routing, and add continuity verification supports, we implemented:
1. Tiered Evidence Budget: Restructured evidence backfilling. Tier 1 (hooks, conflicts, relationship timeline, causality edges) is always included. Tier 2 (asset prop histories, verification elements and continuity evidence) is optional and only included when `blueprint_mode == "FULL"`.
2. Hybrid Routing Matrix: Mapped Parser, Registry Extraction, Asset Mutation, Scene Summarization, Mood/Theme, and Scene-level scoring to the Local model (Ollama). Mapped Director View, Causality Graph, and Character Relationship Graph to the remote Gemini 2.5 Flash API.
3. Locked Importance Score Formula: Programs and calculations for character importance scores are programmatically locked in both `story_analyst.py` and `summarizer.py` to:
   0.4 * normalized_appearance_frequency + 0.4 * normalized_relationship_degree + 0.2 * critical_path_presence.
4. Story Fact Registry: Created a new top-level `story_fact_registry` block in the blueprint JSON, populated by standard/local LLM fact extraction from scene summaries, providing Reflection Agent with historical state boundaries (valid_from, valid_to).
5. Token Usage Tracking: Integrated automatic Request and Input/Output Token statistics tracking for both Local (Ollama) and Remote (Gemini) calls, appended to the final blueprint's metadata block.
6. Console Request Log Dashboard: Injected stdout print statements for requests and responses showing time elapsed and tokens, enabling real-time terminal benchmarking.
7. Timeout and Retry Optimization: Increased the Ollama request timeout to 180s to allow standard hardware to compile output, and configured it to fail immediately upon socket read timeout (bypassing retries) to avoid long, redundant retry loops.

---

## Decision 016

Title:
Local Qwen 2.5 Routing, Connection Resiliency & Graceful Partial Progress Retention

Status:
Accepted

Date:
08/06/2026

Description:
Refactored pipeline settings and exception handling to run entirely on a local model (Qwen 2.5 7B via Ollama) without requiring remote API keys, and maximized resiliency against local processing delays:
1. Environment Key Fallback: Cleared COMPLEX_API_KEY from .env, which forces all complex engine calls (use_complex=True) to fall back and execute on the standard local Ollama model (API_URL).
2. Connection & Timeout Retry Resiliency: Adjusted request timeout to 300s and increased max attempts to 4 (max_retries = 3). Extended the retry loop to catch socket timeouts and TimeoutErrors (sleeping 5s before retrying) rather than failing immediately.
3. Partial Progress Retention: Modified story_analyst.py to catch OllamaConnectionException alongside QuotaLimitReachedException. If the local model times out or disconnects after all 4 attempts, the system intercepts the error, compiles and saves the furthest progress generated up to that stage in outputs/story_blueprint.json.

---

## Decision 017

Title:
Blueprint Visualization Script

Status:
Accepted

Date:
08/06/2026

Description:
Added a standalone Python script `visualize_blueprint.py` at the project root to provide visual inspection of the story blueprint output without modifying any pipeline source code:
1. Causality Graph: Reads causality_graph edges from the blueprint and renders a directed NetworkX graph showing beat-to-beat causal relationships with cause_type edge labels.
2. Character Relationship Graph: Reads character relationships from the registry and renders an undirected NetworkX graph showing all character-to-character relationships with type labels.
3. Narrative Tension Curve: Reads per-scene tension/energy scores and plots a matplotlib line chart showing how narrative intensity evolves across scenes.
4. The script is self-contained and reads directly from outputs/story_blueprint.json, keeping visualization logic decoupled from the pipeline.