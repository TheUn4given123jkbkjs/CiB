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
