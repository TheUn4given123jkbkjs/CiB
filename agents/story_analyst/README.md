# Story Analyst Agent

## Purpose
The Story Analyst is the **Story Understanding Engine** of the CiB (Cinematic Intelligence Builder) system. Inspired by CodeWiki-style repository analysis, it processes raw story inputs to build a structured, causal, and hierarchical database of narrative elements, mapping them into a **Semantic Story Blueprint (JSON)**.

---

## Core Philosophy: "Analyze, Don't Direct"
The Story Analyst extracts narrative facts, structures, and logical dependencies from text. It explicitly avoids making directorial, cinematography, or editing choices (such as camera angles, lens choices, color grading, or cut styles), leaving those to the Director and Storyboard Agents.

---

## Key Mechanism: Recursive Bottom-Up Summarization
To prevent downstream agents from parsing raw story data, the Story Analyst compiles narrative meaning bottom-up through a recursive summarization loop:

```
[Story Executive Summary & Director's View] (Root)
                    ▲
             [Act Summaries]
                    ▲
          [Sequence Summaries]
                    ▲
            [Scene Summaries]
                    ▲
         [Beat Summaries] (Leaf)
```

1. **Beat Level:** Summarizes the raw dramatic action or dialogue exchange.
2. **Scene Level:** Synthesizes child beat summaries to capture the local turning point and emotional shift.
3. **Sequence Level:** Synthesizes child scene summaries to capture the micro-climax or sequence objective.
4. **Act Level:** Synthesizes child sequence summaries to capture major narrative shifts or act transitions.
5. **Story Level (Director's View):** Synthesizes act summaries to create a high-level executive dashboard (themes, main conflicts, and critical path).

---

## Key Responsibilities
* **Hierarchical Decomposition:** Segment the narrative into a **Story Tree** (Story → Act → Sequence → Scene → Beat).
* **Causal Linkage:** Synthesize a directed **Causality Graph** of narrative events to map dependencies.
* **Character Relationship Dynamics:** Track character alliances, power balances, and emotional valences as they change over time.
* **Asset & Prop Tracking:** Keep an active **Asset & Prop Graph** mapping item ownership, locations, and states (e.g., intact vs. broken) to prevent continuity drift.
* **Presence Mapping:** Maintain a lightweight **Presence Matrix** tracking which characters and props exist in each scene/beat.
* **Narrative Compression:** Prioritize scenes and beats into **Importance Tiers** (Tier 1: Core Path, Tier 2: Subplots, Tier 3: Atmospheric) and provide pruning rules.
* **Visual Invariant Profiles:** Extract stable physical descriptions of characters and locations to maintain visual consistency.
* **Ground-Truth Verification:** Generate **Reflection Verification Rules** (checklists of text facts) for downstream quality control.

---

## Interface with Director
The Story Analyst communicates exclusively with the Director Agent:
* **Inputs:**
  * Raw story text (script, prose, outline).
  * `DirectorBrief`: Optional guidelines or compression constraints.
* **Outputs:**
  * **Semantic Story Blueprint (JSON):** Containing the hierarchy tree (with recursive summaries), graphs, presence matrix, compression rules, visual profiles, verification rules, and the `director_view` block.
