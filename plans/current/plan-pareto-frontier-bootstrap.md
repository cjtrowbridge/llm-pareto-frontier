# Current plan: bootstrap host scaffolding + Pareto frontier pipeline

## Status
superseded 2026-09-29 for the budget/taxonomy-normalization/pypdf scope by
`plan-taxonomy-budgets-pypdf.md` (the active change plan). The scaffold and
original 7-stage pipeline below remain the historical record; rate data entry
and the capability scoring decision stay open (see `TODO.md`).

## Goal
Set up the host repo for agentic-pipelines integration and define the
`llm-pareto-frontier` pipeline: every run regenerates per-model JSON and rolls
all `model.json`/`lab.json` files up into `taxonomy/taxonomy.json`, then (when
implemented) renders the Pareto frontier of inference cost per million
generated tokens vs model capability.

## Scope
- Mount agentic-pipelines at `./agentic-pipelines` (done: git submodule)
- Move lab folders into `taxonomy/` (done)
- Per-model `model.json`, per-lab `lab.json`, root `taxonomy/taxonomy.json` (done — initial generation)
- Host scaffolding: `AGENTS.md` shim, `TODO.md`, `pipeline.yaml`, `requirements-pipeline.txt`, `api.sample.yaml` (tracked) / `api.yaml` (ignored), `prompts/`, `plans/`, `journal/`, `.gitignore`, `.vscode/` task + launch entrypoint, `scripts/bootstrap.ps1`, `scripts/pareto_pipeline.py` (implemented)

## Inference cost definition
`cost_per_million_generated_tokens = min(home_electricity_thor, openrouter, lab)`,
all rates normalized to per million tokens generated.

## Dependencies / sequencing
1. Scaffolding (this checkpoint) — no run
2. Pipeline implementation per `TODO.md` — each stage validated deterministically
3. Capability baseline decision — before any frontier can be claimed

## Acceptance conditions (this checkpoint)
- All host files parse (YAML/JSON/PowerShell) and `.gitignore` covers runtime evidence
- `launch.json` play action → `bootstrap.ps1` → `pareto_pipeline.py` main entrypoint exactly once
- Smoke run: `python scripts/pareto_pipeline.py` exits 0, and a repeated run is a no-op (verified 2026-09-29)

## Open decisions
- Capability scoring method (which benchmarks, how aggregated) — human decision
- Actual rate values and citation URLs — operator data entry
- `api.yaml` is never created by automation until an LLM stage is declared