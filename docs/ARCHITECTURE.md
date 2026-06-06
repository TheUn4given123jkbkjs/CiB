# CiB Architecture

# Overview

CiB is an AI trailer generation system designed around a Director-Centric Architecture.

The Director is the central orchestrator of the entire system.

All workflow decisions pass through the Director.

Agents do not communicate directly with each other.

---

# Design Principles

## Director-Centric Coordination

The Director controls:

* task planning
* task delegation
* workflow sequencing
* result aggregation
* quality control

Agents only perform their assigned responsibilities.

---

## Agent Isolation

Each agent is treated as an independent sub-project.

An agent should be understandable and developable without requiring the full repository context.

Each agent maintains its own:

* architecture
* status
* task list
* implementation

---

## Controlled Context Loading

The system should minimize unnecessary context consumption.

When working on an agent:

* load only project summary
* load only current project state
* load only the selected agent documentation

Repository-wide scanning should be avoided.

---

## Knowledge Accumulation

Knowledge generated during development should be preserved.

The system should continuously accumulate:

* successful patterns
* failed patterns
* evaluations
* lessons learned
* reusable blueprints

This knowledge is managed through the Knowledge Base module.

---

# High-Level System Structure

Director
│
├── Story Analyst
├── Storyboard
├── Prompt Engineer
├── Reflection
└── Knowledge Base

---

# Workflow

Story Input
↓
Director
↓
Story Analyst
↓
Storyboard
↓
Prompt Engineer
↓
Reflection
↓
Knowledge Base
↓
Director

---

# Agent Responsibilities

## Director

Responsible for orchestration and workflow management.

Status:
Architecture not finalized.

---

## Story Analyst

Responsible for understanding story structure and producing a structured representation.

Status:
Architecture not finalized.

---

## Storyboard

Responsible for transforming story structures into trailer-oriented scene planning.

Status:
Architecture not finalized.

---

## Prompt Engineer

Responsible for generating prompts for downstream media generation systems.

Status:
Architecture not finalized.

---

## Reflection

Responsible for evaluation, critique, and improvement feedback.

Status:
Architecture not finalized.

---

## Knowledge Base

Responsible for storing reusable knowledge extracted from development and generation processes.

Status:
Architecture not finalized.

---

# Architecture Status

Current Stage:

Architecture Foundation

Detailed agent architectures have not yet been finalized.

This document defines only the high-level system architecture.