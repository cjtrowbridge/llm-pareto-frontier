# Current plan: reasoning budgets, taxonomy slug normalization, pypdf PDF→Markdown

## Status
active — created 2026-09-29 with user sign-off on the canon below ("ok go
ahead"). Execution authority for this change set. Supersedes
`plan-pareto-frontier-bootstrap.md` for this scope (that file is history).

## Goal
1. Record each model's reasoning-effort budget in `models.csv` (new `budget`
   column) and expose it through the taxonomy JSON tree.
2. Normalize every `taxonomy/` folder to a canonical slug derived from the
   canonical titles, with the budget encoded into the model folder name.
3. Add a deterministic pipeline stage that extracts each
   `taxonomy/**/whitepaper.pdf` to a `whitepaper.md` beside it (pypdf), so the
   report text is directly readable.
4. Record Alibaba Cloud's published international output-token rates for the
   exact managed Qwen IDs present in the taxonomy.

### Rate-data amendment (2026-09-29)

User-authorized rate completion: retain the existing USD-per-million-generated
token convention and add Model Studio's international, 0<Token≤1M output rates
for exact ID matches only: `qwen3.8-27b` = `$3.00` and `qwen3.8-max` =
`$6.00`. Cite Alibaba Cloud's primary model-pricing page in each corresponding
`lab_per_million_generated_tokens` rate. `Qwen3.8-Flash-Next` remains
unpriced: the rate card does not identify `qwen3.8-flash-next`, so no inferred
mapping to another managed ID is permitted.

### Mainstream-model cohort amendment (2026-09-29)

User authorized adding the missing mainstream models after citation research.
This amendment is the execution authority for that cohort. The governing
roadmap is absent from this host (a repository-wide search found no roadmap
artifact), so there is no roadmap to synchronize; this omission remains
explicit until the host adopts one.

Scope and gate:

- Add a `models.csv` row and canonical taxonomy directory only when all of the
  following are present: an exact official-model record, an exact row in the
  pinned official `LiveBench/new-livebench` `table_2026_06_25.csv`, and the
  same source table copied as the model's `livebench.csv`.
- Use the publisher record in the `whitepaper` column and the official
  LiveBench table URL in `livebench_source`; do not cite secondary reporting.
  The existing pipeline will derive the benchmark citations from that source.
- Preserve the source-policy rate requirement: add no numeric rate unless its
  publisher price page identifies the exact model/output-token tier. Missing
  rates leave the model rendered as unpriced, never estimated.
- The requested Qwen3.5 4B and 9B and Qwen3.6 35B-A3B are deferred: their
  official model cards exist, but they have no row in the pinned table. Keep
  the TODO finding open rather than fabricate a benchmark score.

Initial eligible cohort (publisher record grouped where one official document
covers a family): OpenAI GPT-5.2 High/Codex, GPT-5.4 xHigh/Mini xHigh/Nano
xHigh, GPT-5.5 xHigh, GPT-5.6 Terra Max/Luna Max, GPT-6 Sol Max/Luna Max,
and GPT-6 Sol Max/Luna Max; GPT-6.1 Sol Max/xHigh are deferred because the
locally pinned source copy has no corresponding rows. Anthropic Claude Opus
4.5/4.6/4.7/4.8/5 and Sonnet
4.6/5/5.5 configurations; GLM-5.2; Nemotron-3-Ultra-550B-A55B; Gemini 3.5
Flash/Flash-Lite, 3.6/3.7/3.8 Flash; Grok 4.3/4.5/4.6/Build 0.1; Kimi
K2.6/K2.7-Code/K3; MiniMax M3; and the explicitly versioned DeepSeek V4
rows. Exact source URLs are recorded in the 2026-09-29 TODO finding and must
be retained in the new CSV rows.

Acceptance: DISCOVER resolves every added row exactly once; all new benchmark
entries cite the pinned table; the run completes without modifying fetched
source files; Qwen deferred rows remain absent from the CSV and called out in
TODO.md.

### Zero-origin logarithmic-rendering amendment (2026-09-29)

User requested that both scatter plots start at zero and use logarithmic
scaling. Since ordinary log axes cannot represent zero, both renderers use a
zero-inclusive `log1p(value / threshold)` transform (a non-negative symlog
scale): cost uses a 1 USD / 1M-token linear threshold and capability uses a
100-point threshold. The later user direction supersedes the zero-origin
capability domain: both plots now visibly show only the 50–100 capability
range, with ticks every ten points. The cost domain remains zero-inclusive.
Axis labels and the standalone SVG footnote must disclose this transform.

### Centered standalone-SVG bounds amendment (2026-09-29)

User superseded the standalone SVG's zero-origin bounds to make the
ROC-style envelope legible. The SVG uses positive logarithmic transforms on
both axes and calculates each bound from the plotted minimum and maximum: in
transformed coordinates, each extreme is padded by one-eighth of the data
span, placing the full plotted range from 10% to 90% of both the 1000 px width
and height. The HTML frontier plot retains the earlier zero-inclusive `log1p`
axes. The standalone SVG labels disclose ordinary log scaling rather than
zero-inclusive scaling.

### Interactive curve-selector amendment (2026-09-29)

User authorized an interactive companion at `artifacts/capability-cost.html`.
It embeds the deterministic standalone SVG inline and selects among the
default **Best capability available by budget** step curve, a straight-segment
Pareto frontier, and points only. The static `capability-cost.svg` keeps the
budget step curve as its default. The selector updates only curve visibility
and explanatory text; model dots, labels, citations, hover groups, and data
are unchanged. Add the HTML artifact to the pipeline's allowed changes and
describe it in the host entrypoint documentation.

### Open-vs-rentier filter amendment (2026-09-29)

User authorized native SVG controls, visible in both the standalone SVG and
the HTML wrapper. The curve selector is rendered as three accessible SVG radio
buttons; both access checkboxes begin checked. The open/self-hostable category
is the DeepSeek V4 family plus Qwen3.8-27B and Qwen3.8-Flash-Next; their dots,
labels, and connectors are green. All other plotted models are hosted-only
(`rentier`) and render red. The filter hides/shows only the associated model
groups; it does not recompute the global summary curves. Evidence: DeepSeek's
official model card publishes downloadable MIT weights and local serving
instructions; Qwen publishes local-serving instructions for Flash-Next;
Qwen3.8-27B is an open-weight release. The classification means suitable
self-hosted hardware, not that every checkpoint fits a typical consumer PC.

### Minimal filter-control amendment (2026-09-29)

User requested removal of the visible “hosted-only” and “open” wording.
Retain the two colored, checked filter controls and their interaction, but
render them without visible category labels. Give each control an accessible
ARIA label so the filtering meaning remains available to assistive technology.

### Restore checkbox text (2026-09-29)

The user reports that the checkboxes are missing their visible text. Restore
one concise label immediately beside each native SVG checkbox: “Rentier
models” and “Self-hostable models.” Keep the previously rejected standalone
“hosted-only” and “open” wording absent, and do not add a legend or second
plot. Preserve the existing filter behavior and plot geometry.

### Missing-model source completion amendment (2026-09-29)

The user requested acceptable sources for the models still absent from the chart.
For GLM-5.2, Nemotron-3-Ultra-550B-A55B, Kimi K2.6 Thinking, Kimi K2.7
Code, and Kimi K3, use the exact OpenRouter model listing as the primary
reseller source for the output-token price, stored under the existing
`openrouter_per_million_generated_tokens` rate ID. Their existing exact
LiveBench rows supply capability. Leave the requested Qwen 4B, 9B, and 35B
sizes and GPT-6.1 Sol variants unplotted until an exact comparable LiveBench
row is available. Do not borrow family scores.

### Requested-Qwen cohort correction (2026-09-29)

The user clarified that the desired small Qwen models are Qwen3.5-4B,
Qwen3.5-9B, and the latest Qwen3.6-35B-A3B. Qwen3.6-27B was added in error;
remove its CSV row, taxonomy directory, and open-model classification, then
regenerate the chart and rollups. Qwen3.8-27B already represents the desired
27B size. The three requested smaller models still require comparable
LiveBench rows before they can be placed on the current chart.

### Readable scatter rendering amendment (2026-09-29)

The all-model label strategy does not scale to the expanded cohort and makes
both charts unreadable. Render every eligible model as a point with an SVG
hover title. Retain the full, cited model table in the HTML artifact. The
standalone scatter lists every model below the plot by descending capability
coefficient, then title as the deterministic tie-breaker. The names are
rotated 90 degrees and a pale line runs from each name to its dot. Capability
coefficient = min-max-normalized capability / (1 + min-max-normalized cost),
where each normalization spans 0–1 across the currently plotted models; the
formula is stated in the chart footer and each point's hover text. The
cost-ordered series remains separate for drawing the best-available
capability at each cost as a ROC-style step envelope, and label the normalized
area on the displayed axes as descriptive rather than a classifier ROC AUC.
Use one neutral model-dot color and no visual key, legend, or category color
treatment. Axis and grid lines stay visible. The standalone SVG's central
plotting panel is a fixed 1000×1000 px square; canvas height below that panel
expands only enough to contain the rotated model names and footnote. Each
model's dot, name, and connector are one keyboard-focusable SVG group:
hovering or focusing any part highlights all three, with a wide invisible
connector hit target so the visible fine line remains easy to select.

### Documented-rate completion amendment (2026-09-29)

User authorized completing the cost layer so the cited new models can render.
The pipeline may seed `lab_per_million_generated_tokens` only from an explicit,
title-keyed table of first-party output-token prices in its source. Each seed
contains the exact primary price URL and is applied only where that rate is
otherwise empty; operator-supplied rates remain authoritative. No default is
permitted for a model whose publisher price is unavailable or does not identify
the exact model. The initial documented subset covers the OpenAI, Anthropic,
xAI, MiniMax, and DeepSeek candidates whose official output prices were
verified; GLM, NVIDIA, Gemini, and Kimi candidates stay visibly unpriced until
their exact first-party API rate is established.

### Qwen3.8-Flash-Next rate completion amendment (2026-09-29)

User authorized filling all three cost fields for Qwen3.8-Flash-Next. The
OpenRouter catalog identifies `Qwen/Qwen3.8-Flash-Next` as its
`qwen/qwen3.8-flash` listing; use that listing's $0.470/M output price. Use
Alibaba Model Studio's `$0.382/M` output price for its corresponding
`qwen3.8-flash` managed ID. For the Jetson Thor field, record `$0.070/M` as a
clearly bounded theoretical FP4 electricity estimate, not a measured serving
result: Qwen reports 6B activated parameters/token; 2 FLOPs/parameter and
NVIDIA's 2,070 FP4 TFLOPS imply 172.5 token/s; 130 W, 1M tokens, and EIA's
March 2026 California residential $0.3335/kWh imply $0.0698/M, rounded to
$0.070/M. Cite the Qwen model record, NVIDIA's official Thor specification,
and EIA's electricity table. This is an explicit source-backed calculation,
not a claim of achieved throughput.

### Taxonomy Markdown-index amendment (2026-09-30)

Add a deterministic `taxonomy_index` material stage after cost and capability
are computed. It writes a generated `index.md` at each taxonomy level: the
taxonomy root lists labs; each lab lists its models; each model documents its
own benchmark and rate tables. Use only existing CSV, `model.json`, and
resolved benchmark data. Every level must link to its children and applicable
primary sources: model-card/whitepaper and LiveBench sources from `models.csv`,
plus per-benchmark and per-rate citations from `model.json`. Model and lab
tables also link to their local JSON and parent index. Markdown must be
deterministic, UTF-8/LF, byte-compared, atomically promoted, and never become
an input or source of truth. Add `taxonomy/**/index.md` to the pipeline's
allowed outputs and describe the stage in the executable contract. Keep all
existing source files, chart geometry, and chart presentation unchanged.

## Canon (locked requirements)

### Canonical titles
- `models.csv` column layout becomes:
  `lab, model_title, budget, livebench_id, whitepaper, livebench_source`.
  The old free-text `model` column is retired; `model_title` is the verbatim
  human title and the sole source for `model.json` `model`.
- `lab` values are the canonical 7-lab set: `Anthropic`, `DeepSeek`,
  `Google DeepMind`, `OpenAI`, `Qwen`, `GLM`, `xAI` (replacing
  `Qwen / Alibaba`, `Z.ai / GLM`, `xAI / SpaceXAI`).
- `budget` holds the lab's own named level in `metric-level` form, or is
  empty when the model has no named reasoning budget.

### Budget values (evidence from 2026-09-29 research)
| lab | model_title | budget | evidence |
|---|---|---|---|
| Anthropic | Claude Fable 5.1 Max Effort | `effort-max` | LiveBench id `claude-fable-5-1-max-effort` |
| Anthropic | Claude Opus 5.5 Max Effort | `effort-max` | id `claude-opus-5-5-max-effort` |
| Anthropic | Claude Opus 5.5 xHigh Effort | `effort-xhigh` | id `claude-opus-5-5-xhigh-effort` |
| DeepSeek | DeepSeek-V4-Pro | *(empty)* | bare model; modes exist but none is in this row |
| DeepSeek | DeepSeek-V4-Flash | *(empty)* | bare model |
| DeepSeek | DeepSeek-V4.1-Flash-Max | `think-max` | V4 report names **Non-think / Think High / Think Max**; "the maximum reasoning effort mode" |
| GLM | GLM-5.3 | *(empty)* | thinking is per-turn on/off; no named levels |
| GLM | GLM-5.3-Flash | *(empty)* | ditto; "Flash" = cheaper variant |
| Google DeepMind | Gemini 3.1 Pro Preview High | `thinking-high` | model card "Thinking (High)" |
| OpenAI | GPT-5.6 Sol Max | `reasoning-effort-max` | whitepaper "maximum reasoning effort"; effort slider |
| OpenAI | GPT-6 Astra Max | `reasoning-effort-max` | whitepaper names levels incl. max |
| Qwen | Qwen3.8-27B | *(empty)* | tech report has no thinking-budget content |
| Qwen | Qwen3.8-Flash-Next | *(empty)* | ditto |
| Qwen | Qwen3.8-Max | *(empty)* | Max = product tier, not a budget |
| xAI | Grok 4.7 xHigh | `effort-xhigh` | id `grok-4.7-xhigh`; x.ai effort footnote |

No value is invented: each is the lab's own vocabulary from its id / model
card / whitepaper.

### Slug grammar
- Charset `[a-z0-9.-]`; single `-` separators, none leading/trailing; `--`
  collapses; any non-slug character becomes `-`.
- A `.` is allowed **only between two alphanumerics** (keeps `5.1`, `qwen3.8`);
  any other dot becomes `-`. Version dots are preserved: e.g.
  `claude-fable-5.1-effort-max` (this refines the earlier discussion example
  that showed `5-1`).
- Uniqueness is case-insensitive within a lab.
- Budget suffix: model slug = `slug(base title with the budget phrase
  stripped)` + `-` + `budget`; empty budget → bare base slug (no trailing
  dash).
- Budget-phrase strip: tokenize the title on `[\s\-/]+` and on dots that are
  not between two alphanumerics; find the longest run of adjacent tokens that
  each match one of the budget's two words (case-insensitive); remove the run
  only if it contains at least one alphabetic token. This tolerates both token
  orders — LiveBench runs Anthropic reversed (`max-effort` id vs
  "Max Effort" title) — and strips a single token ("High" in
  "… Preview High", "Max" in "…-Flash-Max").

### Expected paths (one-time renames, done under plan authority)
| current dir | expected dir |
|---|---|
| `Anthropic/` | `anthropic/` |
| `DeepSeek/` | `deepseek/` |
| `Google DeepMind/` | `google-deepmind/` |
| `OpenAI/` | `openai/` |
| `Qwen Alibaba/` | `qwen/` |
| `xAI SpaceXAI/` | `xai/` |
| `Z.ai GLM/` | `glm/` |
| `…/Claude Fable 5.1 Max Effort/` | `…/claude-fable-5.1-effort-max/` |
| `…/Claude Opus 5.5 Max Effort/` | `…/claude-opus-5.5-effort-max/` |
| `…/Claude Opus 5.5 xHigh Effort/` | `…/claude-opus-5-5-effort-xhigh/` |
| `…/DeepSeek-V4-Pro/` | `…/deepseek-v4-pro/` |
| `…/DeepSeek-V4-Flash/` | `…/deepseek-v4-flash/` |
| `…/DeepSeek-V4.1-Flash-Max/` | `…/deepseek-v4.1-flash-think-max/` |
| `…/Gemini 3.1 Pro Preview High/` | `…/gemini-3.1-pro-preview-thinking-high/` |
| `…/GPT-5.6 Sol Max/` | `…/gpt-5.6-sol-reasoning-effort-max/` |
| `…/GPT-6 Astra Max/` | `…/gpt-6-astra-reasoning-effort-max/` |
| `…/Qwen3.8-27B/` | `…/qwen3.8-27b/` |
| `…/Qwen3.8-Flash-Next/` | `…/qwen3.8-flash-next/` |
| `…/Qwen3.8-Max/` | `…/qwen3.8-max/` |
| `…/Grok 4.7 xHigh/` | `…/grok-4.7-effort-xhigh/` |
| `…/GLM-5.3/` | `…/glm-5.3/` |
| `…/GLM-5.3-Flash/` | `…/glm-5.3-flash/` |

### Mismatch policy
The pipeline never renames. DISCOVER derives the expected
`(lab-slug, model-slug)` for every CSV row and diffs against disk; any missing
or unrecognized directory is a **hard failure before any write (exit 1)** with
every problem listed. Renames are a one-time host operation (this plan is the
authority for the 22 above).

### Data repairs found during research (signed off)
- DeepSeek whitepaper URL `…/blob/main/DeepSeek_V4.pdf` → HTTP 404 on all 3
  rows. Replaced with the working source: the HuggingFace model card page
  `https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro` (the card *is* the full
  technical report; arXiv:2606.19348). No whitepaper file was cached for any
  DeepSeek row; `scripts/fetch_sources.ps1` is re-run once after the renames
  to fetch the three (as `whitepaper.html`; not a PDF, so no `.md` stage).
- GLM rows' `whitepaper.html` is the **GLM-5** report (arXiv:2602.15763), not
  GLM-5.3; no 5.3 report located. Resolution: keep the source as the family
  report; version caveat recorded here and in the TODO close-out.
- The three Qwen `whitepaper.pdf` files are byte-identical (sha256 prefix
  `04F263446D74A35C…`) — the single Qwen3.8-Next/Flash-Next family architecture
  report. Resolution: keep all three rows pointing at it; the extraction is
  then also the single shared text.

## Changes by file
- `models.csv` — new column layout (lab renames above, `model_title`,
  `budget` per the table, DeepSeek URL fix). Otherwise untouched.
- `scripts/pareto_pipeline.py`
  - `REQUIRED_CSV_COLUMNS` = new 6-column layout; `budget` validated to be a
    well-formed slug fragment (fails before any write otherwise).
  - New `slugify()` + budget-strip helpers (the grammar above); DISCOVER
    derives expected lab/model slugs from CSV and fails on any disk
    divergence (missing or unrecognized), before any stage writes.
    `sanitize()` (old folder-name logic) is removed.
  - `model.json` canonical shape gains `"budget"` (string, `""` when empty)
    after `"model"`; `taxonomy.json` model entries gain `"budget"` after
    `"model"`. Values come from CSV (source of truth), not carried forward.
  - New material stage `whitepaper_md` (stage 2 of 8): for each
    `taxonomy/**/whitepaper.pdf`, extract text with pypdf into
    `whitepaper.md` beside it — `# Whitepaper extraction` header, source +
    method note, then `## Page N` sections. Plain text: pypdf does not parse
    tables (limitation, no table parser added). Idempotent by re-extract +
    byte-compare; write only on change; no bookkeeping file.
  - pypdf import mirrors the framework: insert
    `.agentic-pipelines/dependencies` at `sys.path[0]`; a missing import fails
    the run with the bootstrap hint.
  - Stage list: `discover, whitepaper_md, generate, rollup, cost,
    capability, frontier_render, report` (8 material stages); docstring
    (JSON standard + stage contract) updated to match.
- `requirements-pipeline.txt` — add `pypdf==5.9.0` (bootstrap fingerprint
  change auto-triggers the install into `.agentic-pipelines/dependencies/`).
- `scripts/bootstrap.ps1` — add `--check-module pypdf` to the framework
  bootstrap call.
- `scripts/fetch_sources.ps1` — derive folders with the same slug grammar
  (`Get-Slug` + budget-aware `Get-ModelSlug`); read `model_title`/`budget`
  instead of `lab`-sanitized `model`; `Write-Source` now skips an existing
  destination (honoring the script's documented "existing files are never
  overwritten").
- `pipeline.yaml` — `allowed_changes` gains `taxonomy/**/whitepaper.md`.
  `protected_invariants` unchanged (`whitepaper.*` sources stay read-only;
  `.md` is a derived product, not a source).
- `AGENTS.md` — "Naming conventions (taxonomy paths)" section recording the
  grammar; `models.csv` asset line updated to the new columns.

## One-time sequence
1. Apply file changes (above) + one-time renames (table).
2. `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap.ps1`
   → installs pypdf (fingerprint changed) and performs pipeline run 1
   (writes: 23 taxonomy JSONs, 3 `whitepaper.md`, frontier HTML).
3. Re-run `python scripts/pareto_pipeline.py` → must be a full no-op
   (0 files rewritten).
4. Negative test: rename one model dir aside → run must fail at DISCOVER with
   exit 1 and list the divergence, writing nothing; restore the dir, re-run
   → no-op.
5. Close the five research items in `TODO.md` with their resolutions.

## Acceptance conditions
- Run 1 exits 0 with the expected change set; run 2 and post-restore run are
  byte-identical no-ops (every file reported unchanged).
- DISCOVER divergence → exit 1 before any write (verified by negative test).
- `pypdf` resolves from `.agentic-pipelines/dependencies/` (not system Python)
  per the framework bootstrap.
- `taxonomy/**/whitepaper.md` content equals the pypdf text extraction of the
  (unchanged) `whitepaper.pdf`.
- `models.csv`, every `livebench.csv`, and every `whitepaper.pdf`/`.html` are
  byte-untouched except the CSV edits listed above.

## Non-goals
- No git commit/push by automation (operator action).
- No in-pipeline auto-rename, ever.
- No capability-method change (stays provisional, unchanged by this plan).
- No table parsing in the PDF extraction.
- No HTML→MD (PDF only, per request).
