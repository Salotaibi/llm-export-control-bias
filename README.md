# Partner-attribution-bias-llm-export-control-screening


This repository contains the experimental pipeline used to evaluate whether large language models (LLMs) exhibit partner-attribution sensitivity when classifying UK academic research projects for export control review.

The experiments test whether the identity of an international collaborator influences export control classification decisions independently of the technical content of the research.

The study consists of four experiments that progressively isolate the role of partner nationality in model decision making.

---

# Repository Structure

The repository contains scripts for:

1. Stimulus generation
2. Model execution through OpenRouter
3. Statistical analysis

Each experiment follows the same high-level workflow:

1. Generate prompt manifests (`runs_to_do.csv` or equivalent)
2. Execute prompts through LLM APIs
3. Parse binary decisions (YES / NO)
4. Aggregate results and compute statistical contrasts

---

# Dataset

The stimulus dataset contains:

- **15 UK research project descriptions** modelled after EPSRC proposals
- Fields:
  - `project_id`
  - `title`
  - `abstract`
  - `organisation`
  - `department`
  - `fixed_partners`

Country metadata includes:

- `iso3`
- `country_name`
- `bloc`
- `region`
- `embargo` (Experiment 4)

The country list covers **≈249 ISO-3166 countries**.

---

# Models Evaluated

All experiments were executed through **OpenRouter** using:

- `chatgpt-4o`
- `claude-sonnet-4`
- `gemini-2.5-pro`
- `llama-3.3-70b-instruct`
- `qwen-2.5-72b-instruct`

Default inference parameters:
temperature = 0.0
seed = 42
max_tokens = 300–400

Parallel execution is handled with `ThreadPoolExecutor`, including rate limiting and retry logic.

---

# Experiment 1 — Baseline vs Plus-One Partner

### Purpose

Test whether adding a single international collaborator changes classification outcomes.

### Design

For each project:

1. **Baseline prompt**
2. **Baseline + partner country**

Partner countries are inserted across the full ISO country list.

### Conditions

- `baseline`
- `baseline_plus_one`
- `single_partner`

### Output
runs_to_do.csv
runs_done_openrouter_<model>.csv

### Metric

Behavioural change measured as **flip rate** between baseline and partner conditions.

---

# Experiment 2 — Two-Stage Decision Protocol

### Purpose

Isolate whether partner identity alters decisions after a model has already evaluated the project content.

### Stage 1

Model classifies project based **only on technical content**.

### Stage 2

The same project is re-evaluated with an added international partner.

Stage-2 prompts contain the Stage-1 decision and rationale.

### Key Measurement

Change between:
Stage-1 decision
Stage-2 decision

This design tests whether partner nationality causes a **post-hoc decision shift**.

---

# Experiment 3 — Country-Only Prior

### Purpose

Measure whether partner nationality alone produces export control risk signals in the absence of technical information.

### Prompt Structure
Project: A UK academic research project (no technical details provided)
International partner: a public university located in [Country]

### Output

YES probability per country.

### Analysis

- YES rates per country
- Wilson confidence intervals
- Bloc-level aggregation
- Two-proportion tests between blocs

Outputs:
country_yesrate.csv
bloc_yesrate.csv
bloc_contrasts.csv

---

# Experiment 4 — Causal Partner Controls

### Purpose

Identify which cues drive partner sensitivity.

### Design

Three semantically equivalent UK project frames are combined with four partner-identity conditions.

### Frames
F1: a research project based in the United Kingdom

### Conditions

| Condition | Description |
|---|---|
| country | explicit country name |
| unspecified | foreign partner without nationality |
| paraphrase | "[Country]-based institution" |
| proxy | bloc + embargo status |

Total queries:
countries × frames × conditions

### Analysis

YES rates are computed per condition and country.

Three contrasts are calculated:
Δ1 = country − unspecified
Δ2 = country − paraphrase
Δ3 = country − proxy

Significance testing:

- McNemar tests across frame pairs
- Benjamini–Hochberg FDR correction

Outputs:
summary_country_level.csv
summary_bloc_level.csv
bloc_deltas_<model>.png

---

# Reproducibility

All scripts record:

- prompt text
- model identifier
- decision
- rationale
- token usage
- timestamp

Each run is assigned a deterministic `run_id` for reproducibility.

The replication package includes:
projects.csv
countries.csv
runs_to_do.csv
runs_done_openrouter_*.csv
analysis scripts

---

# Research Goal

The experiments evaluate whether LLM export-control screening behaviour is influenced by:

- partner nationality
- geopolitical bloc membership
- lexical cues describing partner identity

The design progressively isolates **content effects**, **identity effects**, and **regulatory proxy cues**.




