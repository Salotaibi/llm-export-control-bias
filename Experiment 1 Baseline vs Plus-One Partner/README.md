# Export-control LLM Bias Study — Replication Package

**Freeze date (UTC):** 2025-10-06T21:50:28Z

## Inputs
- `projects.csv` — projects: **15**
- `countries.csv` — countries: **249**
- `runs_to_do.csv` — full condition list.

## Run outputs
Inventory saved at: `headlines/inventory_runs_summary.csv`

### Files
                                         file             set           model                     model_version  rows  error_rate_pct   first_ts    last_ts
          runs_done_openrouter_chatgpt_4o.csv           temp0      chatgpt-4o                     openai/gpt-4o  7485            0.00 2025-09-29 2025-09-29
     runs_done_openrouter_claude_sonnet_4.csv           temp0 claude-sonnet-4         anthropic/claude-sonnet-4  7485            0.00 2025-09-30 2025-09-30
           runs_done_openrouter_gemini2_5.csv           temp0       gemini2.5             google/gemini-2.5-pro  7485            1.39 2025-10-03 2025-10-03
            runs_done_openrouter_llama3_3.csv           temp0        llama3.3 meta-llama/llama-3.3-70b-instruct  7485            0.00 2025-10-02 2025-10-02
             runs_done_openrouter_qwen2_5.csv           temp0         qwen2.5        qwen/qwen-2.5-72b-instruct  7485            0.00 2025-10-02 2025-10-02
        runs_done_temp02_pilot_chatgpt_4o.csv    temp02_pilot      chatgpt-4o                     openai/gpt-4o   215            0.00 2025-10-05 2025-10-05
   runs_done_temp02_pilot_claude_sonnet_4.csv    temp02_pilot claude-sonnet-4         anthropic/claude-sonnet-4   215            0.00 2025-10-05 2025-10-05
         runs_done_temp02_pilot_gemini2_5.csv    temp02_pilot       gemini2.5             google/gemini-2.5-pro   215            0.00 2025-10-05 2025-10-05
          runs_done_temp02_pilot_llama3_3.csv    temp02_pilot        llama3.3 meta-llama/llama-3.3-70b-instruct   215            0.00 2025-10-05 2025-10-05
           runs_done_temp02_pilot_qwen2_5.csv    temp02_pilot         qwen2.5        qwen/qwen-2.5-72b-instruct   215            0.00 2025-10-05 2025-10-05
     runs_done_temp02_targeted_chatgpt_4o.csv temp02_targeted      chatgpt-4o                     openai/gpt-4o   515            0.00 2025-10-06 2025-10-06
runs_done_temp02_targeted_claude_sonnet_4.csv temp02_targeted claude-sonnet-4         anthropic/claude-sonnet-4   515            0.00 2025-10-06 2025-10-06
      runs_done_temp02_targeted_gemini2_5.csv temp02_targeted       gemini2.5             google/gemini-2.5-pro   515            1.94 2025-10-06 2025-10-06
       runs_done_temp02_targeted_llama3_3.csv temp02_targeted        llama3.3 meta-llama/llama-3.3-70b-instruct   515            0.00 2025-10-06 2025-10-06
        runs_done_temp02_targeted_qwen2_5.csv temp02_targeted         qwen2.5        qwen/qwen-2.5-72b-instruct   515            0.00 2025-10-06 2025-10-06

## Robustness (temperature = 0.2)
- **Targeted set per-model agreement:** chatgpt-4o 95.53%; claude-sonnet-4 98.64%; gemini2.5 93.01%; llama3.3 94.37%; qwen2.5 86.99%
- **Δ rank robustness (Spearman):** chatgpt-4o ρ=0.59 (n=106); claude-sonnet-4 ρ=0.70 (n=106); gemini2.5 ρ=0.23 (n=106); llama3.3 ρ=0.28 (n=106); qwen2.5 ρ=0.27 (n=106)
- Artefacts in `headlines/`:
  - `robustness_temp02_targeted_per_model_agreement.csv`
  - `robustness_temp02_targeted_flip_counts.csv`
  - `robustness_temp02_targeted_spearman.csv`
  - `robustness_temp02_targeted_disagreements.csv`

## Figures & Tables
- Choropleths: `figures/map_delta_<model>.png`
- Bloc CIs: `figures/bloc_yes_ci_<model>.png`
- Tables: `headlines/latex/` (top/bottom Δ; McNemar by bloc/region)

## Notes
- Main estimates reported at **T=0.0**; T=0.2 runs are for robustness.
- Each CSV row has: identifiers, model info, decision, rationale, tokens, and error (if any).
