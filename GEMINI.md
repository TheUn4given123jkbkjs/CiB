# CiB Development Rules

## Primary Goal

Minimize context usage and avoid repository-wide scans.

Always prefer targeted file reads.

---

## Startup Procedure

Before doing any task:

1. Read `knowledge/project_summary.md`
2. Read `knowledge/current_state.md`

Do not read any other file unless required.

---

## Architecture Questions

If the task involves project architecture:

Read:

* docs/ARCHITECTURE.md
* docs/DECISIONS.md

Only.

---

## Agent-Specific Tasks

If the task concerns a specific agent:

Read only:

* agents/<agent>/README.md
* agents/<agent>/ARCHITECTURE.md
* agents/<agent>/STATUS.md

Do not inspect other agents.

Treat each agent as an isolated sub-project.

---

## Source Code Rules

Read source code only when implementation, debugging, refactoring, or testing is requested.

Never scan the entire src directory.

Read only files directly related to the task.

---

## Output Rules

Never read files inside outputs/.

Outputs are generated artifacts and not source-of-truth documents.

---

## Knowledge Update

After any architectural change:

Update:

* docs/DECISIONS.md

After any project progress change:

Update:

* knowledge/current_state.md

---

## Repository Scan Restriction

Repository-wide scans are prohibited unless explicitly requested by the user.