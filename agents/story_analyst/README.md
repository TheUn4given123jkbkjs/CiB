# Story Analyst Agent

## Purpose
The Story Analyst is the **Story Understanding Engine** of the CiB (Cinematic Intelligence Builder) system. Moving away from flat, traditional NLP entity extractors, it operates like a repository code-understanding tool, translating raw story prose into structured, causal, and hierarchical data. It provides a rich semantic blueprint used by downstream agents (Director, Storyboard, Prompt Engineer, Reflection, Knowledge Base) to make cinematic choices, perform visual generation, and check continuity.

---

## Core Philosophy: "Analyze, Don't Direct"
The Story Analyst focuses strictly on **narrative facts and logical dependencies** written in the story text. It leaves artistic, cinematic, and directorial choices (such as camera angles, lens sizes, shot compositions, and editing cuts) to downstream agents like the Director and Storyboard.

The agent is designed to answer:
1. **What happens?** (Story Tree and event containment)
2. **Why does it happen?** (Causal and informational dependency graphs)
3. **Who is involved?** (Character relationships and presence matrix)
4. **What items are involved?** (Asset and prop ownership/state graphs)
5. **What is critical vs. optional?** (Narrative compression and pruning rules)
6. **What is the ground truth?** (Reflection verification rules)

---

## Key Responsibilities
* **Hierarchical Decomposition:** Segment the narrative into a **Story Tree** (Story → Act → Sequence → Scene → Beat).
* **Causal Linkage:** Synthesize a directed **Causality Graph** of narrative events, tracking setups, payoffs, and dependency requirements.
* **Character Relationship Dynamics:** Track character alliances, power balances, and emotional valences as they change over time.
* **Asset & Prop Tracking:** Keep an active **Asset & Prop Graph** showing where items are, who holds them, and their state (e.g., intact, broken, active) to prevent continuity drift.
* **Presence Mapping:** Maintain a lightweight **Presence Matrix** tracking which characters and props exist in each scene/beat.
* **Narrative Compression:** Prioritize scenes and beats into **Importance Tiers** (Tier 1: Core Path, Tier 2: Subplots, Tier 3: Atmospheric) and provide pruning logic.
* **Visual Invariant Profiles:** Extract stable, text-based visual descriptions for characters and locations (e.g., scars, hair colors, architectural styles) to maintain consistency.
* **Ground-Truth Verification:** Generate **Reflection Verification Rules** (checklists of text facts) for quality control.

---

## Interface with Director
The Story Analyst communicates exclusively with the Director Agent:
* **Inputs:**
  * Raw story text (script, prose, outline).
  * `DirectorBrief`: Optional focus guidelines or constraint targets.
* **Outputs:**
  * **Semantic Story Blueprint (JSON):** Containing the hierarchy tree, graphs, presence matrix, compression rules, visual profiles, and verification rules.

---

## Status
* **Conceptual Design:** Finalized and approved (Director-Centric Review complete).
* **Next Steps:** finalization of parsing schemas, prototype development.
