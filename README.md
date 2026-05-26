# 🚀 TopoGen: Structured Multimodal Reasoning for Topology-Constrained Simulation Generation

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![SUMO Version](https://img.shields.io/badge/SUMO-1.24+-green.svg)](https://eclipse.dev/sumo/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 📉 Introduction
**TopoGen** is a neuro-symbolic framework for structured multimodal reasoning in topology-constrained simulation generation. By decoupling **Topological Reasoning** from **Skill-based Execution**, TopoGen maps high-level multimodal design intent into a two-tier Graph Intermediate Representation (GIR), refines it through a Generator-Auditor verification loop, and compiles the verified topology into executable simulator APIs for [SUMO](https://eclipse.dev/sumo/) and SPICE.

This project is the official implementation of the paper: *"TopoGen: Structured Multimodal Reasoning for Topology-Constrained Simulation Generation"*.

---

## 🧥 System Architecture
TopoGen follows a two-stage pipeline for structured multimodal reasoning and topology-constrained execution:

1.  **Reasoning Layer (The Brain)**: Projects unstructured inputs (sketches + text) into a two-tier **Graph Intermediate Representation (GIR)**. It features a **Generator-Auditor negotiation loop** that iteratively refines the graph to ensure geometric and topological consistency.
2.  **Acting Layer (The Hands)**: A skill-based execution system. It orchestrates a library of pre-verified functional modules (Skills) to compile the GIR into executable simulator artifacts, including SUMO XML files and SPICE-compatible scripts.

![System Framework](assets/framework.png)
*Figure 1: The TopoGen neuro-symbolic architecture.*

---

## ✅ Key Features
- **🔭 Multimodal Intent Ingestion**: Support for hand-drawn sketches (spatial priors) and narrative natural language (semantic constraints).
- **🧻 Generator-Auditor Negotiation**: A built-in protocol where a *Generator* proposes and an *Auditor* critiques, improving semantic accuracy by 24.6 points in the 30-node ablation setting.
- **🚜️ Skill-based Execution**: Orchestrates verified Python primitives to generate executable simulator configurations without manual low-level coding.
- **📊 Traffic-TopoBench**: Includes the first open-source multimodal benchmark for traffic network topology generation with 120 scenarios.

---

## 📳 Workflow Showcase

### Step 1: Multimodal Intent Ingestion
![Ingestion](assets/ingestion.png)
*Users provide high-entropy inputs including sketches and linguistic requirements.*

### Step 2: Topological Grounding & Refinement
![Refinement](assets/refinement.png)
*Interactive visualization of the GIR. Users can adjust attributes via a synchronized tabular editor.*

### Step 3: Skill-based Compilation
![Traffic](assets/traffic.png)
*Compiling verified topologies into executable simulator API calls and SUMO artifacts.*

### Step 4: Simulation Orchestration
![Simulation](assets/simulation.png)
*The Acting Layer invokes functional skills to launch a physically valid simulation in SUMO-GUI.*

---

## 📨 Project Structure
```text
TopoGen/
├── main.py              # Entry Point: Streamlit UI & Orchestration
├── src/                 # Core Source Code (Neuro-symbolic Engine)
│   ├── ai_logic.py      # Reasoning Layer: MLLM & Negotiation
│   ├── sumo_logic.py    # Acting Layer: Skill Library & Compilation
│   └── language.py      # i18n Support (EN/ZH)
├── dataset/             # Traffic-TopoBench Dataset
├── assets/              # README Resources (Images/Diagrams)
└── requirements.txt     # Dependency Manifest
```
---

## 🚜️ Installation & Quick Start
```text
1. Prerequisites
Install Eclipse SUMO and configure the SUMO_HOME environment variable.
Python 3.9 or higher.
2. Setup

# Clone the repository
git clone https://github.com/ruiy7469-hue/TopoGen
cd TopoGen

# Install dependencies
pip install -r requirements.txt

3. Run
streamlit run main.py
```

---
## ⚠️ Important Notes
```
API Redundancy: For stable negotiation, providing two separate API keys is recommended to avoid rate limits.
Complexity: Benchmarked on Traffic-TopoBench across 10 to 60 road-network nodes, with additional SPICE circuit tests.
Grounding: For best results, include node coordinates in text and node IDs in sketches.
```
---
## 📐 License
```
Licensed under MIT. This project is for academic and research purposes only.
```
