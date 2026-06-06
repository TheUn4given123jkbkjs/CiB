# CiB Project Summary

## Project Name

CiB (Cinematic Intelligence Builder)

---

## Vision

Build an AI system capable of generating cinematic trailers from story inputs.

The system should analyze a story, extract its narrative structure, create a trailer blueprint, generate visual prompts, and continuously improve through evaluation and knowledge accumulation.

---

## Core Architecture

CiB uses a Director-Centric Architecture.

The Director coordinates all workflow decisions.

Supporting modules:

* Story Analyst
* Storyboard
* Prompt Engineer
* Reflection
* Knowledge Base

---

## Development Philosophy

Each agent is treated as an independent sub-project.

Agent development should remain isolated whenever possible.

Only the minimum required context should be loaded for any task.

Repository-wide scanning should be avoided.

---

## Current Focus

Project architecture and documentation design.

No production implementation exists yet.