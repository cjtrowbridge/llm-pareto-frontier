# LLM Pareto Frontier — Host Instructions

This repository measures inference cost against model capability and renders
the resulting Pareto frontier. The agentic-pipelines framework is mounted as a
submodule; this file hosts only the host-specific routing context and then
defers to the framework.

## Pipeline entrypoints

All commands run from the repository root.

- `python scripts/pareto_pipeline.py` — the main entrypoint. Regenerates the
  per-model `taxonomy/**/model.json` files from `models.csv` plus each model's
  `taxonomy/**/livebench.csv`, recomputes the rollups into
  `taxonomy/taxonomy.json`, renders the Pareto frontier
  (inference cost per million generated tokens vs capability) to
  `artifacts/pareto-frontier.html`, and renders a standalone SVG scatter of
  cost per million tokens (x; the model's lowest documented rate amount)
  vs capability (y) to `artifacts/capability-cost.svg`, plus an interactive
  curve-selector wrapper at `artifacts/capability-cost.html`. The in-file
  docstring records the full stage contract.

Host task surface: `.vscode/tasks.json` exposes the entrypoint as
`Pareto Pipeline: Main`; `.vscode/launch.json` uses the same
`bootstrap.ps1` prerequisite wrapper as its single play action.

## Host assets

- `models.csv` — source of truth for `lab` (canonical), `model_title` (verbatim human title), `budget` (reasoning level, empty when the model has no named level), `livebench_id`, and the `whitepaper` / `livebench_source` URLs
- `scripts/fetch_sources.ps1` — fetches each model's whitepaper and LiveBench table (never overwrites existing files)
- `taxonomy/` — lab/model tree with `model.json`, `lab.json`, `taxonomy.json`
- `pipeline.yaml` — host pipeline definition (schema 2, deterministic stages)
- `api.sample.yaml` / `api.yaml` — local inference config (api.yaml is ignored)
- `scripts/bootstrap.ps1` — host-owned prerequisite wrapper (VS Code boundary)
- `scripts/pareto_pipeline.py` — pipeline main (implemented)
- `TODO.md` — host-owned human checklist
- `plans/current/` — active change plan (execution authority for changes)
- `journal/` — design checkpoints
- `AGENTS.md` — the **Primary sources** section below is the canonical provenance policy for every cited URL in `models.csv` and `model.json` `citations`

## Primary sources

The test: **a primary source is the institution that produced or
measured the fact, publishing its own record of it directly.** Secondary
commentary about that institution's record (news coverage, social posts,
blog posts, forums, aggregator posts quoting the record) is never itself a
citation; it may only be used to *locate* the primary record.

Four kinds qualify:

- **Official model documentation** — the model-building lab's own
  whitepaper / technical report / model card, published on the lab's own
  channels (its site, arXiv, HuggingFace, GitHub) (e.g. the GLM arXiv
  report, the DeepSeek-V4-Pro model card, the Qwen3.8 architecture report).
  View with skepticism: these are self-claims (own-benchmark scores,
  marketing positioning) — record and note the caveat (see **Source
  caveats**), never treat a self-reported number in them as the repo's own
  measured value.
- **Official benchmark releases** — the benchmark institution's own
  published tables / code / evaluation record (e.g. LiveBench's own
  `table_*.csv` in the `LiveBench/new-livebench` repo and its model page).
  Not a comment *about* that benchmark on social media, in a news article,
  or on a third-party site — even one that quotes its numbers.
- **Published pricing** — the model provider's own rate page / model card,
  or the canonical API reseller's own listing:
  `lab_per_million_generated_tokens` → the lab's own price page;
  `openrouter_per_million_generated_tokens` → the OpenRouter model's
  listing page. `jetson_thor_electricity_per_million_generated_tokens` is
  *computed* (W·h per 1M tokens × $/kWh), not a fetched price — its
  primary sources are the chip manufacturer's hardware spec (below) and
  the local electricity rate. Third-party rate roundups are secondary.
- **Hardware specifications** — the chip manufacturer's own spec sheet for
  the hardware used in cost calculations (Jetson Thor power/rate inputs).

Operating rules:

- `model.json` `citations` (benchmark entries, rates) and the `models.csv`
  `whitepaper` / `livebench_source` URLs must point at a qualifying primary
  source; a citation that fails the test is an open `TODO.md` item (per the
  **Open findings** rule), not silently fixed.
- When a secondary source is the only trace to a fact, record the primary
  it points to and note in `TODO.md` or **Source caveats** how the primary
  was located via the secondary.
- The pipeline enforces the *shape* of benchmark citations (the derived
  `<source-id>-<task-slug>` name canon) but not this policy; applying these
  rules to a new row or URL is a human decision recorded in
  `plans/current/` before the row is trusted.

## Naming conventions (taxonomy paths)

`taxonomy/<lab-slug>/<model-slug>/` and every `model.json` benchmark entry
name are derived deterministically from `models.csv` — the pipeline's
DISCOVER stage enforces both, and `scripts/fetch_sources.ps1` mirrors the
directory rules. Rules:

- lab slug: `slugify(lab)` — lowercase; characters outside
  `[a-z0-9.-]` become `-`; separators are single (none leading/trailing,
  no doubles); a `.` is only kept between two alphanumerics, so version
  dots survive (`claude-fable-5.1-…`, `qwen3.8-…`)
- model slug: `slugify` of the title with a trailing run of the budget's
  words (end-anchored, so titles without a budget keep every word) —
  hence `claude-opus-5.5-effort-max` from "Claude Opus 5.5 Max Effort"
  and `qwen3.8-max` from "Qwen3.8-Max" (empty budget, "Max" belongs to
  the name) — then `-{budget}` appended for a non-empty budget; an empty
  budget yields the title slug alone
- a non-empty budget must be lowercase hyphenated words (the DISCOVER
  stage rejects otherwise) and is the reasoning level the model dir name
  encodes; `model.json` and `taxonomy.json` carry a `budget` field
  copied from the CSV (source of truth, never invented)
- benchmark entry names: `model.json` scores are task slices of a single
  cited benchmark snapshot (one row of the cited table), so an entry name
  names the source, not the column: `<source-id>-<task-slug>`, where the
  task slug is the `slugify` of the raw table column and the source id is
  the slug of the row's `livebench_source` URL's owner token
  (`github.com/LiveBench/…` → `livebench`; the cited table file name carries
  the snapshot detail but is not part of the id), so the python column is
  `livebench-python`. The DISCOVER stage rejects a `livebench_source`
  URL whose id cannot be derived (an id is never invented) and rejects any
  derived name that violates the canon
- exception — the composite capability entry: the first benchmark entry of
  every `model.json` is the derived composite (LiveBench Global Average),
  named with the source id alone (no `-<task-slug>` tail), so the shared
  source yields `livebench`; its `value` is derived from the model's own
  per-column entries (not a table column) and its `citations` are re-derived
  each run from the row's `livebench_source` (operator edits to them are not
  carried forward)
- the naming canon itself: tokens of `[a-z0-9]` with a `.` only between two
  alphanumerics (version dots survive: `5.1`, `qwen3.8`), joined
  by single `-` separators (none leading, trailing, or doubled) — this is
  what `slugify` always emits, and it is what every derived identifier above
  must satisfy
- unresolved folder names (missing or unrecognized dirs) fail the run
  before any write is performed; the pipeline never renames — fix the
  dirs or the CSV by hand, then re-run (plan:
  `plans/current/plan-taxonomy-budgets-pypdf.md`)

## Source caveats

- The two GLM `whitepaper.html` files are the GLM-5 family report
  (arXiv:2602.15763 v2), not GLM-5.3-specific reports — kept and
  documented; the search for a GLM-5.3 report stays open in `TODO.md`
- The three Qwen `whitepaper.pdf` files are byte-identical: one
  Qwen3.8-Next/Flash-Next architecture report (Qwen Team, 2026-08-26,
  28 pages) shared across the three rows — kept and documented; the
  search for per-model reports stays open in `TODO.md`
- The three DeepSeek `whitepaper.html` files are the DeepSeek-V4-Pro
  HuggingFace model card (a single document for the whole V4 family)

## Open findings → TODO.md (governance rule)

`TODO.md` is the root-level open-work record. During any agentic
conversation, when a summary or findings report identifies a missing
detail that needs to be found and filled in (e.g. a blank `budget` value
in `models.csv`, a dead source URL, a missing whitepaper file), each
such item must be added to `TODO.md` as an unchecked item in the same
turn the report is delivered, with a pointer to the evidence. Items stay
open until the user resolves, removes, or explicitly defers them; the
agent never self-resolves or silently skips recording them.

## Routing

All framework behavior — design, prompt building, validation, local inference,
operation, analysis, and governance invariants — is defined by the framework
router at `./agentic-pipelines/AGENTS.md`. Load it for any task that touches
the pipeline itself; this file does not restate framework policy.
