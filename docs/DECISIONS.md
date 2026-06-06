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



