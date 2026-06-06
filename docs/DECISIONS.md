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