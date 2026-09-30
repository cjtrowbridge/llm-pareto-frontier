#!/usr/bin/env python3
"""llm-pareto-frontier pipeline — main entrypoint.

This is the host main entrypoint for pipeline id `llm-pareto-frontier`
(defined in `pipeline.yaml`, schema 2). It is a deterministic pipeline: no
LLM stage may be added without a real `llm_justification` and governance
review per `agentic-pipelines/AGENTS.md`.

Run contract (applies to every invocation, including interactive runs):

- Every command runs from the host repository root (cwd must contain
  `models.csv`, `taxonomy/`, `pipeline.yaml`, and `agentic-pipelines/AGENTS.md`;
  fail fast with a visible error otherwise — for the last one, the hint is
  `git submodule update --init agentic-pipelines`).
- Bootstrap is the first stage of every pipeline operation: the VS Code
  surfaces enter `scripts/bootstrap.ps1` (submodule init, declared
  requirements into the ignored `.agentic-pipelines/dependencies/` dir,
  preflight when `api.yaml` exists) BEFORE reaching this script. Direct CLI
  invocations (CI, schedulers) use the same wrapper.
- Operator-visible progress is emitted for each material stage: completed vs
  remaining work, elapsed time, and an ETA derived from elapsed time. No
  credentials or protected inputs may appear in output (the data here is
  public benchmark/pricing data).
- Ctrl+C is a controlled interruption: report it visibly, preserve truthful
  state for unfinished work, persist the run report, and exit 130. Never
  report interrupted work as successful.
- Every execution persists a structured, non-secret machine report
  (`run.json`) and a human-readable run narrative (`narrative.md`) under
  `reports/<run_id>/` (ignored), checkpointed at the terminal event (success,
  no-op, failure, or interruption).

JSON standard for the taxonomy tree (the pipeline converges the tree to this
canonical form on every run):

- Bytes: UTF-8, no BOM, LF newlines, one trailing newline. Serializer:
  `json.dumps(doc, indent=2, ensure_ascii=False) + "\\n"` — that is the
  canonical encoding; the byte-compare for no-op detection runs against it.
- Key order is fixed (insertion order is canonical). The rollup is
  EMBEDDING: every parent file contains its children's model.json documents
  (nothing else at that level), so the root `taxonomy.json` alone carries
  the whole tree's real data:
    lab.json      { "lab",
                    "models": [<its models' model.json documents>] }
    model.json    { "lab", "model", "budget",
                    "benchmarks": [{ "name", "value", "citations" }],
                    "rates":      [{ "name", "amount", "citations" }] }
    taxonomy.json { "labs":
                    [{ "lab", "models": [<model.json documents>] }] }
- `budget` is the model's lab-idiomatic reasoning-effort level exactly as
  written in `models.csv` ("" when the model has no named level); it is a
  pure passthrough from the CSV and is the level encoded in the model
  folder name (naming convention: AGENTS.md).
- `benchmarks` contain ONLY the columns for which the model has a real value:
  the numeric score from the model's resolved `livebench.csv` row (never
  invented). Entries first carry the derived composite entry (below), then
  the columns in LiveBench table column order (minus the `model` column);
  a column the model has no value for is simply absent — model.json never
  carries blank/null benchmark data.
- A benchmark entry's `name` names the benchmark a score came from, not the
  raw table column (each column is one task slice of a single benchmark
  snapshot): `name = <source-id>-<slugify(column)>`, where the source id is
  the slug of the row's `livebench_source` URL's owner token (the reference
  to the cited table file carries the snapshot detail; the id names the
  benchmark's source, not a snapshot — the current shared source yields
  `livebench`, so the python column is `livebench-python`). A URL that yields
  no id fails the run (an id is never invented); the naming canon is
  AGENTS.md. `citations` default
  to the row's `livebench_source` url and carry forward operator edits across
  runs keyed to the column, so a name change never drops them. The first
  benchmark entry of every model.json is the derived composite: `name` is the
  source id alone (the shared LiveBench source yields `livebench`) and `value`
  is the capability score (stage 6, `LIVEBENCH_CATEGORIES`) — a row of no
  table column, derived from that model's own per-column entries. Its
  `citations` always default to the row's `livebench_source` (operator edits
  to them are not carried forward — every run re-derives them).
- `rates` contain ONLY the rate ids for which the model has real data (a real
  `amount` and/or operator citations). The three recognised ids (in this
  fixed order):
    jetson_thor_electricity_per_million_generated_tokens
        Home inference: energy for 1M generated tokens on a Jetson Thor
        (measured power draw W x token-count->hours conversion) x local $/kWh.
    openrouter_per_million_generated_tokens
        OpenRouter list price, output price converted to per-1M-generated.
    lab_per_million_generated_tokens
        The lab's price per 1M generated tokens.
  `amount` is USD per MILLION GENERATED TOKENS, operator-filled; `citations`
  reference the measurement/pricing source. The pipeline carries
  operator-filled `amount` and `citations` forward unchanged, never invents
  values, and drops unknown extra entries with a visible warning. A rate id
  that is not yet filled (no amount and no citations) is simply absent —
  model.json never carries blank rate data.
- Only whole files are ever rewritten: stage candidate -> validate ->
  byte-compare -> atomic replace in the same directory, so an interrupted run
  leaves each file either at the previous promoted bytes or the new full
  bytes, never a mix. A file is written only when its bytes differ
  (idempotent runs produce no rewrites). `models.csv`, `livebench.csv`, and
  whitepapers are never modified. `reports/` and `artifacts/` are ignored
  evidence, never source.

Stages (in order):

1. DISCOVER
   Read `models.csv` (source of truth: lab, model_title, budget, livebench_id,
   whitepaper, livebench_source) and validate each `budget` as a well-formed
   slug fragment; derive each row's expected taxonomy path from the naming
   convention (lab slug; model slug = version-dotted title with any budget
   phrase stripped, then '-<budget>' appended) and walk `taxonomy/` (one dir
   per lab, one per model, each model dir containing `livebench.csv`),
   checking the csv<->directory mapping in BOTH directions — any missing or
   orphan dir is a hard failure BEFORE any file is written (the pipeline never
   renames); verify all model tables carry the identical benchmark column
   order; derive each row's benchmark source id from its `livebench_source`
   URL (the URL's owner slug — a row whose URL has no owner token fails
   the run) and check each derived entry name
   (`<source-id>-<slugify(column)>`) against the naming canon; resolve each
   model row to its LiveBench row (prefer `livebench_id`; otherwise normalized
   name match on model_title, then the dot->hyphen variant, then a unique
   substring match) — any unresolved or ambiguous model fails the run with
   every such model listed (no guessing).

2. WHITEPAPER PDF -> MD  (mutates: taxonomy/**/whitepaper.md)
   For every `taxonomy/**/whitepaper.pdf`, extract the page text with pypdf
   into a `whitepaper.md` beside it: a `# Whitepaper extraction` header, then
   one `## Page N of M` section per page. Plain text only — pypdf does not
   parse tables. Written only when the bytes differ (idempotent, no
   bookkeeping file).

3. GENERATE PER-MODEL model.json  (mutates: taxonomy/**/model.json)
   Rebuild every `model.json` per the JSON standard above (including the
   `budget` passthrough from models.csv), carrying forward operator data from
   the previous file. Only benchmark entries with a real value and rate
   entries with a real amount and/or citation are emitted (no nulls/blanks).

4. ROLL UP  (runs EVERY time, including when model.json files were unchanged)
   Embedding rollup: rebuild each lab `lab.json` and the root
   `taxonomy.json` so every parent contains its children's full model.json
   documents (the root thus carries every model's real benchmark values,
   rate amounts, and citations at the top level). Children are read from
   disk and validated BEFORE any write: lab dirs == models.csv labs, each
   document's `model` matches its models.csv row, benchmark names are an
   in-order subset of the model's derived names (the composite capability
   entry name + the `<source-id>-<slugify(column)>` column names, all derived
   from the row's `livebench_source` URL), rate names an in-order subset of
   the three ids.
   On mismatch: visible hard failure, staged candidates NOT promoted.

5. COST  (deterministic; mutates nothing)
   `cost = min(usable rate amounts)`; usable = numeric and > 0. Record which
   rate won plus its citations. Any amount of exactly 0 is excluded with a
   visible note (it would poison the frontier), and a model with no usable
   amount is excluded from the frontier with a visible reason.

6. CAPABILITY  (deterministic)
   Parse each resolved row's benchmark values; capability = the LiveBench
   official Global Average — the equally-weighted mean of the seven category
   means (category -> column map in LIVEBENCH_CATEGORIES, copied from
   LiveBench/new-livebench scripts/generate_model_rows.py). This same value
   is the model.json composite benchmark entry (name = the source id alone, e.g.
   `livebench`), derived from the model's own per-column entries — the
   table stores no published overall column; derivation: derive_composite().

7. PARETO FRONTIER + RENDER  (mutates: artifacts/pareto-frontier.html)
   A point is on the frontier iff no other point has cost <= AND capability >=
   with at least one strict; exact (cost, capability) ties keep both members,
   flagged. Render one self-contained HTML page (inline CSS + inline SVG, no
  CDN, no timestamp — a pure function of the data, so unchanged data yields a
   byte-identical page) with the point plot, a per-model cost/rate/citation/
   status table, and the full benchmark-value table. Byte-compare/promote.

8. CAPABILITY-COST CHARTS  (deterministic; mutates: artifacts/capability-cost.svg,
   artifacts/capability-cost.html)
   One standalone scatter SVG (no timestamp — a pure function of the data,
   so unchanged data yields byte-identical bytes): one point per model with
   both a computed cost and a capability score, x = cost — the model's
   lowest documented price, i.e. the stage 5 minimum of its usable rate
   amounts (positive logarithmic scale) — and y = capability (the LiveBench
   Global Average composite entry, also on a positive logarithmic scale).
   Each axis derives its bounds from the plotted minimum and maximum so those
   extrema occupy the centered 80% of the square panel.
   A ROC-style best-available-capability step line shows the cost/capability
   envelope and its normalized area, not a classifier ROC/AUC. Model names
   run across the bottom by ascending cost, then descending capability for
   ties, rotated 90 degrees with pale connectors to their points. The
   hypothetical min-max coefficient remains available in point hover text.
   The HTML wrapper offers the default budget step curve, a straight-segment
   Pareto frontier, and points only. Byte-compare/promote.

9. REPORT  (the checkpoint; runs again best-effort on failure/interruption)
   `reports/<run_id>/run.json` + `narrative.md`; final visible summary with
   frontier members, skipped models, and warnings.
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path

# pypdf resolves from the host-local, git-ignored dependency directory that
# the framework bootstrap installs requirements-pipeline.txt into (see
# scripts/bootstrap.ps1).
_DEPS_DIR = Path(__file__).resolve().parent.parent / ".agentic-pipelines" / "dependencies"
if _DEPS_DIR.is_dir():
    sys.path.insert(0, str(_DEPS_DIR))

try:
    from pypdf import PdfReader
except ModuleNotFoundError as exc:
    sys.stderr.write(
        "pareto_pipeline: pypdf is not importable (" + repr(exc) + "). "
        "Run scripts/bootstrap.ps1 first so the framework bootstrap installs "
        "requirements-pipeline.txt into .agentic-pipelines/dependencies/; "
        "the whitepaper_md stage cannot run without it.\n"
    )
    raise SystemExit(1) from exc

PIPELINE_ID = "llm-pareto-frontier"

MATERIAL_STAGES = (
    "discover",
    "whitepaper_md",
    "generate",
    "rollup",
    "cost",
    "capability",
    "frontier_render",
    "capability_cost_chart",
    "report",
)

RATE_IDS = (
    "jetson_thor_electricity_per_million_generated_tokens",
    "openrouter_per_million_generated_tokens",
    "lab_per_million_generated_tokens",
)

# Models with published downloadable weights and local-serving instructions.
# "Open" here means self-hostable with suitable home hardware; it does not
# claim that every checkpoint fits a typical consumer machine.
OPEN_SELF_HOSTED_MODELS = frozenset(
    {
        ("Qwen", "Qwen3.8-27B"),
        ("Qwen", "Qwen3.8-Flash-Next"),
    }
)


def _is_open_self_hosted_model(rec: dict) -> bool:
    return rec["lab"] == "DeepSeek" or (rec["lab"], rec["model"]) in OPEN_SELF_HOSTED_MODELS

# Exact first-party standard output-token prices, in USD per million generated
# tokens. These seeds are source data, not estimates: they allow the catalog to
# begin with a documented lab rate while preserving any later operator override.
DOCUMENTED_LAB_RATE_SEEDS: dict[tuple[str, str], tuple[float, str]] = {
    ("OpenAI", "GPT-5.2 High"): (14.0, "https://developers.openai.com/api/docs/models/gpt-5.2"),
    ("OpenAI", "GPT-5.2 Codex"): (14.0, "https://developers.openai.com/api/docs/models/gpt-5.2-codex"),
    ("OpenAI", "GPT-5.4 xHigh"): (15.0, "https://developers.openai.com/api/docs/models/gpt-5.4"),
    ("OpenAI", "GPT-5.4 Mini xHigh"): (4.5, "https://developers.openai.com/api/docs/models/gpt-5.4-mini"),
    ("OpenAI", "GPT-5.4 Nano xHigh"): (1.25, "https://developers.openai.com/api/docs/models/gpt-5.4-nano"),
    ("OpenAI", "GPT-5.5 xHigh"): (30.0, "https://developers.openai.com/api/docs/models/gpt-5.5"),
    ("OpenAI", "GPT-5.6 Luna Max"): (1.2, "https://developers.openai.com/api/docs/models/gpt-5.6-luna"),
    ("OpenAI", "GPT-5.6 Terra Max"): (12.0, "https://developers.openai.com/api/docs/models/gpt-5.6-terra"),
    ("OpenAI", "GPT-6 Sol Max"): (10.0, "https://developers.openai.com/api/docs/models"),
    ("OpenAI", "GPT-6 Luna Max"): (0.5, "https://developers.openai.com/api/docs/models"),
    ("Anthropic", "Claude Opus 4.8 Max Effort"): (25.0, "https://platform.claude.com/docs/en/models/opus-4-8/overview"),
    ("Anthropic", "Claude Opus 4.5 Thinking 64K High Effort"): (25.0, "https://platform.claude.com/docs/en/models/opus-4-5/overview"),
    ("Anthropic", "Claude Opus 4.6 Thinking Auto High Effort"): (25.0, "https://platform.claude.com/docs/en/models/opus-4-6/overview"),
    ("Anthropic", "Claude Opus 4.7 xHigh Effort"): (25.0, "https://platform.claude.com/docs/en/about-claude/pricing"),
    ("Anthropic", "Claude Opus 5 Max Effort"): (25.0, "https://platform.claude.com/docs/en/models/opus-5/overview"),
    ("Anthropic", "Claude Sonnet 4.6 Thinking Auto Medium Effort"): (15.0, "https://platform.claude.com/docs/en/models/sonnet-4-6/overview"),
    ("Anthropic", "Claude Sonnet 5 xHigh Effort"): (10.0, "https://platform.claude.com/docs/en/models/sonnet-5/overview"),
    ("Anthropic", "Claude Sonnet 5.5 Max Effort"): (10.0, "https://platform.claude.com/docs/en/models/sonnet-5-5/overview"),
    ("Anthropic", "Claude Sonnet 5.5 xHigh Effort"): (10.0, "https://platform.claude.com/docs/en/models/sonnet-5-5/overview"),
    ("xAI", "Grok 4.3"): (2.5, "https://docs.x.ai/developers/pricing"),
    ("xAI", "Grok 4.5"): (6.0, "https://docs.x.ai/developers/pricing"),
    ("xAI", "Grok 4.6"): (6.0, "https://docs.x.ai/developers/pricing"),
    ("xAI", "Grok Build 0.1"): (2.0, "https://docs.x.ai/developers/pricing"),
    ("MiniMax", "MiniMax M3"): (2.4, "https://platform.minimax.io/subscribe/token-plan?tab=api-enterprise"),
    ("DeepSeek", "DeepSeek-V4-Flash-0731"): (1.2, "https://api-docs.deepseek.com/quick_start/pricing/"),
    ("DeepSeek", "DeepSeek-V4-Flash-Vision-Exp"): (1.2, "https://api-docs.deepseek.com/quick_start/pricing/"),
    ("DeepSeek", "DeepSeek-V4-Pro-0813"): (3.96, "https://api-docs.deepseek.com/quick_start/pricing/"),
    # Google publishes the current standard paid tier; the 3.6–3.8 introductory
    # rate is explicitly valid through December 31, 2026.
    ("Google DeepMind", "Gemini 3.5 Flash High"): (9.0, "https://ai.google.dev/gemini-api/docs/pricing"),
    ("Google DeepMind", "Gemini 3.5 Flash-Lite High"): (2.5, "https://ai.google.dev/gemini-api/docs/pricing"),
    ("Google DeepMind", "Gemini 3.6 Flash High"): (3.75, "https://ai.google.dev/gemini-api/docs/pricing"),
    ("Google DeepMind", "Gemini 3.7 Flash High"): (3.75, "https://ai.google.dev/gemini-api/docs/pricing"),
    ("Google DeepMind", "Gemini 3.8 Flash High"): (3.75, "https://ai.google.dev/gemini-api/docs/pricing"),
}

EXIT_OK = 0
EXIT_FAIL = 1
EXIT_INTERRUPTED = 130

TABLE_COLUMN = "model"
REQUIRED_CSV_COLUMNS = (
    "lab",
    "model_title",
    "budget",
    "livebench_id",
    "whitepaper",
    "livebench_source",
)
# Naming convention (mirrored by scripts/fetch_sources.ps1; canonical copy in
# AGENTS.md): lowercase [a-z0-9], single '-' separators, and a '.' only
# between two alphanumerics (version dots are preserved). A budget is a
# well-formed slug fragment in metric-level form (e.g. "effort-max").
SLUG_BUDGET_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Vocabulary words that may appear in a budget phrase; the title-phrase strip
# below only matches these, so product-tier words ("Max" in "Qwen3.8-Max" for
# an empty budget, version numerals) are never stripped by mistake.
SLUG_BUDGET_WORDS = frozenset(
    {"effort", "xhigh", "max", "high", "thinking", "reasoning", "think"}
)
# The naming canon every derived identifier must satisfy (lab/model slugs,
# budgets, benchmark entry names): tokens of lowercase alphanumerics with a
# '.' only between two alphanumerics (version dots survive: 5.1, qwen3.8),
# joined by single '-' separators. slugify() always emits this
# canon; derived names are checked against it in DISCOVER.
SLUG_NAME_RE = re.compile(r"^[a-z0-9]+(?:\.[a-z0-9]+)*(?:-[a-z0-9]+(?:\.[a-z0-9]+)*)*$")


def source_benchmark_prefix(citation: str) -> str:
    """Derive the benchmark entry name prefix (source id) from a
    livebench_source URL.

    Each column of the cited table is one task slice of a single benchmark
    snapshot, so model.json names entries `<prefix>-<slugify(column)>` where
    the prefix is the slug of the URL's owner token — the benchmark's source,
    not an invented version or snapshot label. A
    `github.com/<owner>/<repo>/(blob|raw)/<ref>/…/<table-file>` URL thus
    yields `livebench`, so the python column is `livebench-python`; a plain
    host/<owner>/…/<file> URL uses its first path part the same way. The id
    is always derived from the cited URL (never invented): a URL with no
    owner token is an error.
    """
    from urllib.parse import urlparse

    parsed = urlparse(citation)
    if not parsed.scheme or not parsed.netloc:
        raise PipelineError(
            [
                f"livebench_source {citation!r} is not a parseable url; the "
                "benchmark source id cannot be derived (the pipeline never "
                "invents an id)"
            ],
            "discover",
        )
    path_parts = [p for p in parsed.path.split("/") if p]
    owner = None
    if "github.com" in parsed.netloc:
        # github.com/<owner>/<repo>/(blob|raw)/<ref>/<path>.../<file>
        owner = path_parts[0] if len(path_parts) >= 2 else None
    elif path_parts:
        # plain host/<owner>/.../file form: first path part the owner
        owner = path_parts[0] if len(path_parts) >= 2 else None
    if not owner:
        raise PipelineError(
            [
                f"livebench_source {citation!r} has no owner token; the "
                "benchmark source id cannot be derived (the pipeline never "
                "invents an id)"
            ],
            "discover",
        )
    return slugify(owner)


# Category -> table columns (capability categories), declared at the stage 6
# boundary below; the composite name/value helpers here look it up lazily so
# they can be used from earlier stages.


def composite_benchmark_name(rec: dict) -> str:
    """The name of a model's derived composite benchmark entry.

    The composite is a row of no table column, so it is named with the
    source id alone (no `-<task-slug>` tail): the shared LiveBench source
    yields `livebench`. The id is always the one derived from the row's
    `livebench_source` URL (never invented).
    """
    prefix = source_benchmark_prefix(rec["citation"])
    if not SLUG_NAME_RE.match(name := prefix):
        raise PipelineError(
            [
                f"{rec['lab']} / {rec['model']}: composite benchmark name "
                f"{name!r} violates the naming canon (see AGENTS.md)"
            ],
            "discover",
        )
    return name


def derive_composite(rec: dict) -> float | None:
    """Composite capability for one model: the equally-weighted mean of the
    category means over that model's own per-column scores (the LiveBench
    official Global Average; category -> column map in
    LIVEBENCH_CATEGORIES). None when the model has no parseable value.
    """
    scores = rec["scores"]
    cat_values: list[float] = []
    for cols in LIVEBENCH_CATEGORIES.values():
        vals = [scores[c] for c in cols if scores.get(c) is not None]
        if vals:
            cat_values.append(sum(vals) / len(vals))
    if not cat_values:
        return None
    return sum(cat_values) / len(cat_values)


class PipelineError(Exception):
    """Fatal, expected failure: candidates stay staged, none promoted."""

    def __init__(self, messages: list[str], stage: str) -> None:
        super().__init__("; ".join(messages))
        self.messages = messages
        self.stage = stage


def log(msg: str) -> None:
    print(f"pareto_pipeline: {msg}", flush=True)


def rel(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


def fmt_duration(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, secs = divmod(seconds, 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{int(hours)}h {int(minutes)}m {int(secs)}s"
    return f"{int(minutes)}m {int(secs)}s"


def _slug_tokens(name: str) -> list[str]:
    """Tokenize a name for slugification.

    A token is a run of alphanumerics; a '.' is kept inside a token only
    between two alphanumerics (version dots: '5.1', 'qwen3.8'), any other
    character starts a new token boundary. Mirrored by Get-Slug in
    scripts/fetch_sources.ps1.
    """
    s = name.casefold()
    tokens: list[str] = []
    cur: list[str] = []
    n = len(s)
    for i, c in enumerate(s):
        kept = c.isalnum() or (
            c == "." and 0 < i < n - 1 and s[i - 1].isalnum() and s[i + 1].isalnum()
        )
        if kept:
            cur.append(c)
        elif cur:
            tokens.append("".join(cur))
            cur = []
    if cur:
        tokens.append("".join(cur))
    return tokens


def slugify(name: str) -> str:
    """Canonical taxonomy folder slug (naming convention: AGENTS.md)."""
    return "-".join(_slug_tokens(name))


def strip_budget_phrase(title: str, budget: str) -> str:
    """Remove the budget phrase from a model title (either token order).

    The phrase is the longest end-anchored run of title tokens that each
    match a vocabulary word of the budget string, case-insensitively: 'Max
    Effort' against 'effort-max', '…Preview High' against 'thinking-high',
    and the single level token 'Max' in 'DeepSeek-V4.1-Flash-Max' against
    'think-max'. Titles without a matching tail ('Qwen3.8-Max' with an
    empty budget) are untouched.
    """
    if not budget:
        return title
    words = {w for w in budget.lower().split("-") if w in SLUG_BUDGET_WORDS}
    if not words:
        return title
    tokens = _slug_tokens(title)
    i = len(tokens)
    while i > 0 and tokens[i - 1] in words:
        i -= 1
    return " ".join(tokens[:i])


def expected_model_slug(title: str, budget: str) -> str:
    """Model folder name: stripped-title slug, plus '-<budget>' when set."""
    base = slugify(strip_budget_phrase(title, budget))
    return f"{base}-{budget}" if budget else base


def canonical_json_bytes(doc: object) -> bytes:
    return (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".part")
    tmp.write_bytes(data)
    try:
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def read_bytes_or_none(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except OSError:
        return None


class Run:
    """Truthful-by-construction run state: only stages that actually finished
    are recorded done; only whole-file promotions count as changes."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.started_mono = time.monotonic()
        self.started_utc = datetime.now(timezone.utc)
        self.finished_utc: datetime | None = None
        self.run_id = self.started_utc.strftime("%Y%m%dT%H%M%SZ")
        self.status = "running"  # running|success|no-op|failure|interrupted
        self.stage: str | None = None
        self.stage_failed: str | None = None
        self.stage_detail: dict[str, str] = {}
        self.stage_seconds: dict[str, float] = {}
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []
        self.changed_paths: list[str] = []
        self.noop_paths: list[str] = []
        self.models: list[dict] = []
        self.table_columns: list[str] = []
        self.frontier: list[str] = []
        self.ties: list[list[str]] = []
        self.skipped: list[dict] = []
        self.report_written = False

    def finish_stage(self, stage: str, detail: str, seconds: float) -> None:
        self.stage_detail[stage] = detail
        self.stage_seconds[stage] = round(seconds, 3)

    def elapsed(self) -> float:
        return time.monotonic() - self.started_mono

    def warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)

    def note(self, msg: str) -> None:
        if msg not in self.notes:
            self.notes.append(msg)

    def change(self, relpath: str) -> None:
        if relpath not in self.changed_paths:
            self.changed_paths.append(relpath)

    def noop(self, relpath: str) -> None:
        if relpath not in self.noop_paths:
            self.noop_paths.append(relpath)

    def promote_or_noop(self, path: Path, data: bytes, stage: str) -> bool:
        """Validate (implicitly caller-side) and promote a staged candidate.

        Returns True when the file was rewritten.
        """
        existing = read_bytes_or_none(path)
        if existing == data:
            self.noop(rel(self.repo_root, path))
            return False
        atomic_write_bytes(path, data)
        self.change(rel(self.repo_root, path))
        return True


# ---------------------------------------------------------------------------
# Stage 1: discover
# ---------------------------------------------------------------------------
def _read_table(model_dir: Path) -> tuple[list[str], list[tuple[str, dict[str, str]]]]:
    """Return (column names, [(row_id, {col: raw value})]) from a livebench.csv."""
    with open(model_dir / "livebench.csv", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        if not fieldnames or fieldnames[0] != TABLE_COLUMN:
            raise PipelineError(
                [
                    f"{model_dir.name}: livebench.csv first column must be "
                    f"{TABLE_COLUMN!r} (found: {fieldnames[:1]})"
                ],
                "discover",
            )
        cols = fieldnames[1:]
        rows: list[tuple[str, dict[str, str]]] = []
        seen: dict[str, int] = {}
        for line_no, row in enumerate(reader, start=2):
            rid = (row.get(TABLE_COLUMN) or "").strip()
            if not rid:
                raise PipelineError(
                    [f"{model_dir.name}: livebench.csv line {line_no} has an empty {TABLE_COLUMN!r} id"],
                    "discover",
                )
            if rid in seen:
                raise PipelineError(
                    [
                        f"{model_dir.name}: livebench.csv has duplicate {TABLE_COLUMN!r} id "
                        f"{rid!r} (lines {seen[rid]} and {line_no})"
                    ],
                    "discover",
                )
            seen[rid] = line_no
            rows.append((rid, {c: (row.get(c) or "").strip() for c in cols}))
        return cols, rows


def _resolve_row_id(
    lab: str, model: str, livebench_id: str, rows: list[tuple[str, dict[str, str]]]
) -> tuple[str, str]:
    """Resolve a model row to its LiveBench row id; return (row_id, mode).

    Raises PipelineError with a single descriptive message when the match is
    missing or ambiguous — resolution never guesses.
    """
    where = f"{lab} / {model}"
    ids = [rid for rid, _ in rows]
    if livebench_id:
        hits = [rid for rid in ids if rid.casefold() == livebench_id.casefold()]
        if len(hits) == 1:
            return hits[0], "livebench_id"
        if hits:
            msg = f"{where}: livebench_id {livebench_id!r} is ambiguous: {hits}"
        else:
            msg = f"{where}: livebench_id {livebench_id!r} not found in its livebench.csv"
        raise PipelineError([msg], "discover")
    base = re.sub(r"[\s/]+", "-", model.casefold())
    for cand in dict.fromkeys((base, base.replace(".", "-"))):
        hits = [rid for rid in ids if rid.casefold() == cand]
        if len(hits) == 1:
            return hits[0], "name-match"
        if len(hits) > 1:
            raise PipelineError(
                [f"{where}: normalized name {cand!r} is ambiguous: {hits}"], "discover"
            )
    sub = [
        rid
        for rid in ids
        if rid.casefold() in base or base in rid.casefold()
    ]
    if len(sub) == 1:
        return sub[0], "name-match-substring"
    if len(sub) > 1:
        raise PipelineError(
            [f"{where}: name {model!r} substring-matches multiple rows: {sub}"], "discover"
        )
    raise PipelineError(
        [f"{where}: no matching LiveBench row for model {model!r} (no livebench_id given)"],
        "discover",
    )


def stage_discover(run: Run) -> str:
    root = run.repo_root
    with open(root / "models.csv", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = list(reader.fieldnames or [])
        missing_cols = [c for c in REQUIRED_CSV_COLUMNS if c not in cols]
        if missing_cols:
            raise PipelineError(
                [f"models.csv missing column(s): {', '.join(missing_cols)} (found: {', '.join(cols)})"],
                "discover",
            )
        parsed: list[dict] = []
        seen: dict[tuple[str, str], int] = {}
        for line_no, raw in enumerate(reader, start=2):
            lab = (raw.get("lab") or "").strip()
            model = (raw.get("model_title") or "").strip()
            budget = (raw.get("budget") or "").strip()
            if not lab or not model:
                raise PipelineError(
                    [f"models.csv line {line_no}: empty lab or model_title field"], "discover"
                )
            if budget and not SLUG_BUDGET_RE.match(budget):
                raise PipelineError(
                    [
                        f"models.csv line {line_no}: budget {budget!r} is not a "
                        "well-formed slug fragment (lowercase [a-z0-9] words "
                        "joined by single '-')"
                    ],
                    "discover",
                )
            key = (lab.casefold(), model.casefold())
            if key in seen:
                raise PipelineError(
                    [
                        f"models.csv: duplicate (lab, model_title) {lab!r}/{model!r} "
                        f"(lines {seen[key]} and {line_no})"
                    ],
                    "discover",
                )
            seen[key] = line_no
            parsed.append(
                {
                    "lab": lab,
                    "model": model,
                    "budget": budget,
                    "livebench_id": (raw.get("livebench_id") or "").strip(),
                    "livebench_source": (raw.get("livebench_source") or "").strip(),
                }
            )

    # csv -> expected directories (naming convention; the pipeline never
    # renames — divergence is a hard failure below, before any write)
    for row in parsed:
        row["lab_folder"] = slugify(row["lab"])
        row["model_folder"] = expected_model_slug(row["model"], row["budget"])

    # disk: walk taxonomy/
    tax = root / "taxonomy"
    disk_labs: dict[str, list[Path]] = {}
    for child in sorted(tax.iterdir(), key=lambda p: p.name):
        if child.is_dir():
            disk_labs[child.name] = []
        elif child.name != "taxonomy.json":
            run.warn(f"stray file in taxonomy/: {child.name}")
    for lab_folder, model_dirs in disk_labs.items():
        for sub in sorted((tax / lab_folder).iterdir(), key=lambda p: p.name):
            if not sub.is_dir():
                continue  # lab.json etc. live here
            if not (sub / "livebench.csv").is_file():
                raise PipelineError(
                    [
                        f"orphan dir taxonomy/{lab_folder}/{sub.name}: "
                        "contains no livebench.csv and matches no models.csv row"
                    ],
                    "discover",
                )
            disk_labs[lab_folder].append(sub)

    expected_dir: dict[tuple[str, str], dict] = {}
    for row in parsed:
        key = (row["lab_folder"], row["model_folder"])
        if key in expected_dir:
            raise PipelineError(
                [
                    "models.csv: two rows map to the same taxonomy dir "
                    f"taxonomy/{key[0]}/{key[1]}/ "
                    f"({expected_dir[key]['lab']} / {expected_dir[key]['model']} and "
                    f"{row['lab']} / {row['model']})"
                ],
                "discover",
            )
        expected_dir[key] = row
    # case-insensitive model-slug uniqueness within each lab (the filesystem
    # is case-preserving but case-insensitive, so '…Effort' + '…effort' must
    # collide here and not at write time)
    casefolded: dict[tuple[str, str], tuple[str, str, str]] = {}
    for (lab_folder, model_folder), row in expected_dir.items():
        ckey = (lab_folder.casefold(), model_folder.casefold())
        if ckey in casefolded:
            first_path, first_lab, first_model = casefolded[ckey]
            raise PipelineError(
                [
                    "models.csv: two rows map to case-insensitively identical "
                    f"taxonomy dirs, {first_path} and "
                    f"taxonomy/{lab_folder}/{model_folder}/ "
                    f"({first_lab} / {first_model} vs {row['lab']} / {row['model']})"
                ],
                "discover",
            )
        casefolded[ckey] = (f"taxonomy/{lab_folder}/{model_folder}/", row["lab"], row["model"])
    problems: list[str] = []
    for (lab_folder, model_folder), row in expected_dir.items():
        lab_dir = disk_labs.get(lab_folder)
        if lab_dir is None:
            problems.append(
                f"missing dir taxonomy/{lab_folder}/ (models.csv row: {row['lab']} / {row['model']})"
            )
            continue
        if not any(d.name == model_folder for d in lab_dir):
            problems.append(
                f"missing dir taxonomy/{lab_folder}/{model_folder}/ "
                f"(models.csv row: {row['lab']} / {row['model']})"
            )
    for lab_folder, dirs in disk_labs.items():
        lab_rows = [r for r in parsed if r["lab_folder"] == lab_folder]
        if not lab_rows:
            for d in dirs:
                problems.append(
                    f"orphan lab dir taxonomy/{lab_folder}/ "
                    f"(contains {d.name}/; no models.csv row maps to it)"
                )
            continue
        lab_model_folders = {r["model_folder"] for r in lab_rows}
        for d in dirs:
            if d.name not in lab_model_folders:
                problems.append(
                    f"orphan model dir taxonomy/{lab_folder}/{d.name}/ (no matching models.csv row)"
                )
    if problems:
        raise PipelineError(problems, "discover")

    # tables + resolution
    run.models = []
    for row in parsed:
        model_dir = tax / row["lab_folder"] / row["model_folder"]
        cols_table, table_rows = _read_table(model_dir)
        if not run.table_columns:
            run.table_columns = cols_table
        elif cols_table != run.table_columns:
            raise PipelineError(
                [
                    f"taxonomy/{row['lab_folder']}/{row['model_folder']}/livebench.csv: "
                    f"benchmark column order differs from the shared table "
                    f"(expected {run.table_columns[:3]}..., got {cols_table[:3]}...)"
                ],
                "discover",
            )
        row_id, mode = _resolve_row_id(
            row["lab"], row["model"], row["livebench_id"], table_rows
        )
        _, row_values = next(
            (rid, vals) for rid, vals in table_rows if rid == row_id
        )
        prefix = source_benchmark_prefix(row["livebench_source"])
        benchmark_names = {col: f"{prefix}-{slugify(col)}" for col in run.table_columns}
        for name in benchmark_names.values():
            if not SLUG_NAME_RE.match(name):
                raise PipelineError(
                    [
                        f"{row['lab']} / {row['model']}: derived benchmark name "
                        f"{name!r} violates the naming canon (see AGENTS.md)"
                    ],
                    "discover",
                )
        scores: dict[str, float | None] = {}
        unparseable: list[str] = []
        for col in run.table_columns:
            raw_val = row_values.get(col, "")
            if raw_val == "":
                scores[col] = None
                unparseable.append(col)
                continue
            try:
                scores[col] = float(raw_val)
            except ValueError:
                scores[col] = None
                unparseable.append(col)
        if unparseable:
            run.warn(
                f"{row['lab']} / {row['model']}: unparseable benchmark value(s): "
                f"{', '.join(unparseable)} (omitted from model.json)"
            )
        provisional_rec = {
            "lab": row["lab"],
            "model": row["model"],
            "citation": row["livebench_source"],
            "scores": scores,
        }
        composite_name = composite_benchmark_name(provisional_rec)
        composite_value = derive_composite(provisional_rec)
        run.models.append(
            {
                "lab": row["lab"],
                "model": row["model"],
                "budget": row["budget"],
                "lab_folder": row["lab_folder"],
                "model_folder": row["model_folder"],
                "citation": row["livebench_source"],
                "benchmark_names": benchmark_names,
                "composite": {"name": composite_name, "value": composite_value},
                "row_id": row_id,
                "match_mode": mode,
                "scores": scores,
            }
        )
    mode_counts: dict[str, int] = {}
    for m in run.models:
        mode_counts[m["match_mode"]] = mode_counts.get(m["match_mode"], 0) + 1
    detail = (
        f"{len(run.models)} model rows, {len(run.table_columns)} benchmark columns "
        f"(identical order across all {len(run.models)} tables); resolved: "
        + ", ".join(f"{v} {k}" for k, v in sorted(mode_counts.items()))
    )
    return detail


# ---------------------------------------------------------------------------
# Stage 2: whitepaper pdf -> md (mutates: taxonomy/**/whitepaper.md)
# ---------------------------------------------------------------------------
def stage_whitepaper_md(run: Run) -> str:
    """Extract each whitepaper.pdf to a whitepaper.md beside it (pypdf).

    Plain text, one `## Page N of M` section per page; written only when the
    bytes differ, so an unchanged PDF yields no rewrite.
    """
    tax = run.repo_root / "taxonomy"
    pdfs = sorted(tax.rglob("whitepaper.pdf"))
    rewritten = 0
    for pdf in pdfs:
        try:
            reader = PdfReader(io.BytesIO(pdf.read_bytes()))
            page_texts = [(p.extract_text() or "") for p in reader.pages]
            total = len(page_texts)
        except Exception as exc:
            raise PipelineError(
                [
                    f"{rel(run.repo_root, pdf)}: pypdf could not extract text "
                    f"({exc!r}) — a corrupt or unusual PDF is a source problem, "
                    "not a pipeline write target"
                ],
                "whitepaper_md",
            )
        parts = [
            "# Whitepaper extraction",
            "",
            f"Source: {rel(run.repo_root, pdf)}",
            "Method: pypdf per-page text extraction (plain text; tables are not parsed).",
            "",
        ]
        for n, text in enumerate(page_texts, start=1):
            text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
            parts.append(f"## Page {n} of {total}")
            parts.append("")
            parts.append(text if text else "(no extractable text)")
            parts.append("")
        data = ("\n".join(parts)).encode("utf-8")
        out = pdf.with_name("whitepaper.md")
        out_rel = rel(run.repo_root, out)
        if run.promote_or_noop(out, data, "whitepaper_md"):
            rewritten += 1
            log(f"  whitepaper_md: {out_rel} rewritten")
        else:
            log(f"  whitepaper_md: {out_rel} unchanged")
    return f"{rewritten}/{len(pdfs)} whitepaper.md file(s) rewritten"


# ---------------------------------------------------------------------------
# Stage 3: generate per-model model.json
# ---------------------------------------------------------------------------
def _load_previous(path: Path) -> dict | None:
    old = read_bytes_or_none(path)
    if old is None:
        return None
    try:
        doc = json.loads(old.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def _carry_forward(
    run: Run, rec: dict, prev: dict | None
) -> tuple[dict[str, list[str]], dict[str, dict]]:
    """Pull operator-filled data out of a previous model.json.

    Tolerates both the pre-convergence shape (entries keyed by "value") and
    the canonical shape (entries keyed by "name"). Unknown entries are
    dropped with a visible warning; nothing is ever invented.
    """
    where = f"{rec['lab']} / {rec['model']}"
    comp_name = composite_benchmark_name(rec)
    bench_cits: dict[str, list[str]] = {}
    rates: dict[str, dict] = {rid: {"amount": None, "citations": []} for rid in RATE_IDS}
    if prev is None:
        return bench_cits, rates

    prev_bench = prev.get("benchmarks")
    # an entry name may be the raw column (files from before the derived-name
    # rule) or a derived name — map either back to the column the operator
    # citations refer to
    derived_cols = {rec["benchmark_names"][col]: col for col in run.table_columns}
    if isinstance(prev_bench, list):
        for entry in prev_bench:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not isinstance(name, str):
                val = entry.get("value")
                if isinstance(val, str) and val in run.table_columns:
                    name = val  # pre-convergence shape: "value" held the name
                else:
                    run.warn(f"{where}: previous benchmarks entry {entry!r} is unrecognized and was dropped")
                    continue
            if name == comp_name:
                run.warn(
                    f"{where}: the composite {name!r} entry is derived from the "
                    "row's columns each run; operator edits to its citations "
                    "are not carried forward"
                )
                continue
            col = name if name in run.table_columns else derived_cols.get(name)
            if col is None:
                # a source id changed between runs: match on the trailing
                # task slug so a name change still carries citations forward
                # (a name change never drops operator edits)
                matches = [
                    c
                    for c in run.table_columns
                    if name == slugify(c) or name.endswith(f"-{slugify(c)}")
                ]
                if len(matches) == 1:
                    col = matches[0]
            if col is None:
                run.warn(f"{where}: unknown benchmark {name!r} in previous model.json was dropped")
                continue
            cits = [c for c in entry.get("citations", []) if isinstance(c, str)]
            if cits:
                bench_cits[col] = cits
    prev_rates = prev.get("rates")
    if isinstance(prev_rates, list):
        for entry in prev_rates:
            if not isinstance(entry, dict):
                continue
            name = entry.get("name")
            if not isinstance(name, str):
                val = entry.get("value")
                if isinstance(val, str) and val in RATE_IDS:
                    name = val
                else:
                    run.warn(f"{where}: previous rates entry {entry!r} is unrecognized and was dropped")
                    continue
            if name not in RATE_IDS:
                run.warn(f"{where}: unknown rate {name!r} in previous model.json was dropped")
                continue
            cits = [c for c in entry.get("citations", []) if isinstance(c, str)]
            raw_amount = entry.get("amount")
            if raw_amount is None:
                amount: float | None = None
            elif isinstance(raw_amount, (int, float)) and not isinstance(raw_amount, bool) and math.isfinite(raw_amount):
                amount = float(raw_amount)
            else:
                amount = None
                run.warn(
                    f"{where}: rate {name!r} has a non-numeric amount {raw_amount!r}; "
                    "treated as missing (the pipeline never invents values)"
                )
            rates[name] = {"amount": amount, "citations": cits}
    return bench_cits, rates


def stage_generate(run: Run) -> str:
    changed = 0
    for idx, rec in enumerate(run.models, start=1):
        path = run.repo_root / "taxonomy" / rec["lab_folder"] / rec["model_folder"] / "model.json"
        prev = _load_previous(path)
        if prev is None and (path.exists()):
            run.warn(f"{rec['lab']} / {rec['model']}: existing {path.relative_to(run.repo_root)} is not valid JSON; regenerating from sources")
        prev_bench_cits, prev_rates = _carry_forward(run, rec, prev)
        seed = DOCUMENTED_LAB_RATE_SEEDS.get((rec["lab"], rec["model"]))
        lab_rate = prev_rates["lab_per_million_generated_tokens"]
        if seed and lab_rate["amount"] is None and not lab_rate["citations"]:
            lab_rate["amount"], citation = seed
            lab_rate["citations"] = [citation]
        doc = {
            "lab": rec["lab"],
            "model": rec["model"],
            "budget": rec["budget"],
            "benchmarks": (
                [
                    {
                        "name": rec["composite"]["name"],
                        "value": rec["composite"]["value"],
                        "citations": [rec["citation"]],
                    }
                ]
                if rec["composite"]["value"] is not None
                else []
            )
            + [
                {
                    "name": rec["benchmark_names"][col],
                    "value": rec["scores"].get(col),
                    "citations": prev_bench_cits.get(col, [rec["citation"]]),
                }
                for col in run.table_columns
                if rec["scores"].get(col) is not None
            ],
            "rates": [
                {
                    "name": rid,
                    "amount": prev_rates[rid]["amount"],
                    "citations": prev_rates[rid]["citations"],
                }
                for rid in RATE_IDS
                if prev_rates[rid]["amount"] is not None or prev_rates[rid]["citations"]
            ],
        }
        rec["rates_data"] = prev_rates
        missing = [
            rid for rid in RATE_IDS if prev_rates[rid]["amount"] is None and not prev_rates[rid]["citations"]
        ]
        if missing:
            run.warn(
                f"{rec['lab']} / {rec['model']}: rate data unfilled for {', '.join(missing)} — "
                "cost cannot use those rates until amounts are provided"
            )
        written = run.promote_or_noop(path, canonical_json_bytes(doc), "generate")
        if written:
            changed += 1
        log(
            f"  generate [{idx}/{len(run.models)}] {rec['lab']} / {rec['model']}: "
            f"{'rewritten' if written else 'unchanged'}"
        )
    return f"{changed}/{len(run.models)} model.json files rewritten ({len(run.models) - changed} unchanged)"


# ---------------------------------------------------------------------------
# Stage 4: roll up lab.json + taxonomy.json (every time)
# ---------------------------------------------------------------------------
def stage_rollup(run: Run) -> str:
    """Embedding rollup: every parent file contains its children's full
    model.json documents, so the root taxonomy.json alone carries the
    whole tree's real data (benchmark values + citations, rate amounts +
    citations) at the top level.
    """
    tax = run.repo_root / "taxonomy"
    errors: list[str] = []
    disk_labs = {d.name for d in tax.iterdir() if d.is_dir()}
    expected_labs = {rec["lab_folder"] for rec in run.models}
    if disk_labs != expected_labs:
        errors.append(
            f"lab dirs on disk {sorted(disk_labs)} != labs from models.csv {sorted(expected_labs)}"
        )
    rate_ids = list(RATE_IDS)
    # read (and validate) the children that will be embedded
    model_docs: dict[str, dict] = {}
    for rec in run.models:
        p = tax / rec["lab_folder"] / rec["model_folder"] / "model.json"
        rp = rel(run.repo_root, p)
        try:
            doc = json.loads(p.read_bytes().decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            errors.append(f"rollup source missing or unparseable: {rp}")
            continue
        if not isinstance(doc, dict):
            errors.append(f"{rp}: model.json top level is not a JSON object")
            continue
        if doc.get("model") != rec["model"]:
            errors.append(
                f"{rp}: model name {doc.get('model')!r} does not match the "
                f"models.csv row {rec['model']!r}"
            )
        derived = [rec["composite"]["name"]] + list(rec["benchmark_names"].values())
        names = [b.get("name") for b in doc.get("benchmarks", []) if isinstance(b, dict)]
        if (any(n not in derived for n in names)
                or names != [n for n in derived if n in names]):
            errors.append(
                f"{rp}: benchmark names must be an in-order subset of the derived "
                f"benchmark names — the composite capability entry (source id "
                f"alone, e.g. 'livebench') followed by the per-column "
                f"`<source-id>-<task-slug>` names, all derived from the row's "
                f"livebench_source URL"
            )
        rids = [r.get("name") for r in doc.get("rates", []) if isinstance(r, dict)]
        if (any(r not in rate_ids for r in rids)
                or rids != [r for r in rate_ids if r in rids]):
            errors.append(f"{rp}: rates must be an in-order subset of {rate_ids}")
        model_docs[f"{rec['lab_folder']}/{rec['model_folder']}"] = doc
    if errors:
        raise PipelineError(errors, "rollup")
    if not model_docs:
        raise PipelineError(["no models to roll up (models.csv produced no rows)"], "rollup")

    # parents embed the exact documents read from disk this stage, built
    # from the same objects, so lab.json and taxonomy.json can never
    # disagree with each other or with the children
    lab_order: list[str] = []
    lab_model_docs: dict[str, list[dict]] = {}
    for rec in run.models:
        if rec["lab"] not in lab_model_docs:
            lab_order.append(rec["lab"])
            lab_model_docs[rec["lab"]] = []
        lab_model_docs[rec["lab"]].append(
            model_docs[f"{rec['lab_folder']}/{rec['model_folder']}"]
        )

    changed = 0
    for lab in lab_order:
        lab_folder = next(r["lab_folder"] for r in run.models if r["lab"] == lab)
        doc = {"lab": lab, "models": lab_model_docs[lab]}
        if run.promote_or_noop(tax / lab_folder / "lab.json", canonical_json_bytes(doc), "rollup"):
            changed += 1
    root_doc = {
        "labs": [{"lab": lab, "models": lab_model_docs[lab]} for lab in lab_order]
    }
    if run.promote_or_noop(tax / "taxonomy.json", canonical_json_bytes(root_doc), "rollup"):
        changed += 1
    return (
        f"embedded {len(run.models)} model.json docs into {len(lab_order)} lab.json "
        f"+ taxonomy.json ({changed} rewritten)"
    )


# ---------------------------------------------------------------------------
# Stage 5: cost (deterministic, in-memory)
# ---------------------------------------------------------------------------
def stage_cost(run: Run) -> str:
    with_cost = 0
    for rec in run.models:
        usable: list[tuple[float, str, list[str]]] = []
        for rid in RATE_IDS:
            d = rec["rates_data"][rid]
            amount = d["amount"]
            if amount is None:
                continue
            if amount == 0:
                run.warn(
                    f"{rec['lab']} / {rec['model']}: rate {rid!r} amount is 0 — "
                    "excluded from the cost minimum (it would poison the frontier)"
                )
                continue
            if amount < 0:
                run.warn(
                    f"{rec['lab']} / {rec['model']}: rate {rid!r} amount is negative ({amount}) — "
                    "excluded from the cost minimum"
                )
                continue
            usable.append((amount, rid, d["citations"]))
        if usable:
            best = min(usable, key=lambda t: t[0])
            amount, rid, cits = best
            tied_with = sorted(r for a, r, _ in usable if a == amount and r != rid)
            if tied_with:
                run.note(
                    f"{rec['lab']} / {rec['model']}: cost ties between {', '.join([rid] + tied_with)} "
                    f"at {amount}; first in canonical rate order wins ({rid})"
                )
            rec["cost"] = {"amount": amount, "rate": rid, "citations": cits}
            with_cost += 1
        else:
            rec["cost"] = None
            rec["skipped_reason"] = (
                "no usable rate amounts — fill 'amount' (USD per 1M generated tokens) "
                "and citations in this model's model.json"
            )
            run.skipped.append(
                {"model": f"{rec['lab']} / {rec['model']}", "reason": rec["skipped_reason"]}
            )
    return f"{with_cost}/{len(run.models)} models have a computed cost = min(usable rate amounts)"


# ---------------------------------------------------------------------------
# Stage 6: capability (deterministic; LiveBench official Global Average)
# ---------------------------------------------------------------------------
# Category -> table columns, copied verbatim from LiveBench/new-livebench
# scripts/generate_model_rows.py (CATEGORIES). The published overall is the
# equally-weighted mean of the seven category means — it is computed, never
# stored in the table CSV.
LIVEBENCH_CATEGORIES = {
    "math": ["AMPS_Hard", "integrals_with_game", "math_comp", "olympiad"],
    "coding": ["code_completion", "code_generation"],
    "data_analysis": ["consecutive_events", "tablejoin", "tablereformat"],
    "instruction_following": ["paraphrase", "simplify", "story_generation", "summarize"],
    "language": ["connections", "plot_unscrambling", "typos"],
    "reasoning": ["logic_with_navigation", "spatial", "theory_of_mind", "zebra_puzzle"],
    "agentic_coding": ["python", "javascript", "typescript"],
}

CAPABILITY_NOTE = (
    "LiveBench Global Average: equally-weighted mean of the 7 category means "
    "(math, coding, data_analysis, instruction_following, language, reasoning, "
    "agentic_coding) — matches the number the LiveBench site publishes; "
    "category -> column map in LIVEBENCH_CATEGORIES (copied from "
    "LiveBench/new-livebench scripts/generate_model_rows.py)"
)


def stage_capability(run: Run) -> str:
    run.note(CAPABILITY_NOTE)
    scored = 0
    for rec in run.models:
        vals = [v for v in rec["scores"].values() if v is not None]
        total = len(run.table_columns)
        value = derive_composite(rec)
        rec["composite"] = {"name": rec["composite"]["name"], "value": value}
        rec["capability"] = {
            "value": value,
            "method": "livebench_global_average",
            "parseable": len(vals),
            "total": total,
            "note": CAPABILITY_NOTE,
        }
        if value is not None:
            scored += 1
        elif not rec.get("skipped_reason"):
            rec["skipped_reason"] = "no parseable benchmark values in its livebench.csv row"
            run.skipped.append(
                {"model": f"{rec['lab']} / {rec['model']}", "reason": rec["skipped_reason"]}
            )
    return (
        f"{scored}/{len(run.models)} models have a capability score "
        "(LiveBench Global Average; stored as the derived composite entry "
        "in each model.json)"
    )


# ---------------------------------------------------------------------------
# Stage 7: pareto frontier + render (deterministic, timestamp-free)
# ---------------------------------------------------------------------------
def _nice_ticks_linear(lo: float, hi: float) -> list[float]:
    if hi <= lo:
        hi = lo + 1.0
    raw = (hi - lo) / 6.0
    mag = 10 ** math.floor(math.log10(raw))
    norm = raw / mag
    step = mag * (1 if norm < 1.5 else 2 if norm < 3 else 5 if norm < 7 else 10)
    out: list[float] = []
    v = math.ceil(lo / step) * step
    while v <= hi + step * 1e-6:
        out.append(v)
        v += step
    return out


def _nice_ticks_log(lo: float, hi: float) -> list[float]:
    e0 = math.floor(math.log10(lo))
    e1 = math.ceil(math.log10(hi))
    vals = [10.0 ** e for e in range(e0, e1 + 1)]
    vals = [v for v in vals if lo * (1 - 1e-9) <= v <= hi * (1 + 1e-9)]
    if len(vals) > 10:
        vals = vals[:: math.ceil(len(vals) / 8)]
    return vals


def _nice_ticks_log_decades(lo: float, hi: float) -> list[float]:
    # 1-2-5 multiples per decade, for log axes whose range is narrower than
    # two decades (plain powers of 10 would leave the axis bare).
    e0 = math.floor(math.log10(lo))
    e1 = math.ceil(math.log10(hi))
    vals = [m * 10.0 ** e for e in range(e0, e1 + 1) for m in (1.0, 2.0, 5.0)]
    return [v for v in vals if lo * (1 - 1e-9) <= v <= hi * (1 + 1e-9)]


def _fmt_num(v: float) -> str:
    return f"{v:g}"


def _symlog(value: float, threshold: float) -> float:
    """A non-negative, zero-inclusive logarithmic transform."""
    return math.log1p(max(0.0, value) / threshold)


def _nice_ticks_symlog(hi: float, threshold: float) -> list[float]:
    """Zero plus 1-2-5 ticks for a non-negative symlog domain."""
    vals = {0.0}
    start = math.floor(math.log10(threshold))
    end = math.ceil(math.log10(max(hi, threshold)))
    for exponent in range(start, end + 1):
        for multiple in (1.0, 2.0, 5.0):
            value = multiple * 10.0**exponent
            if value <= hi * (1 + 1e-9):
                vals.add(value)
    # For wide linear regions, retain useful interior ticks below the
    # transition rather than showing only zero and the threshold.
    if threshold >= 10.0:
        for fraction in (0.2, 0.5):
            value = threshold * fraction
            if value <= hi * (1 + 1e-9):
                vals.add(value)
    return sorted(vals)


def _render_plot_svg(points: list[dict]) -> str:
    W, H = 900, 560
    ML, MR, MT, MB = 90, 40, 40, 50
    xs = sorted(p["x"] for p in points)
    ys = sorted(p["y"] for p in points)
    xhi = max(xs[-1] * 1.08, 1.0)
    x_threshold, y_threshold = 1.0, 100.0
    ylo, yhi = 50.0, 100.0
    sx_max = _symlog(xhi, x_threshold)
    sy_lo, sy_hi = _symlog(ylo, y_threshold), _symlog(yhi, y_threshold)
    xticks = _nice_ticks_symlog(xhi, x_threshold)
    yticks = [50.0, 60.0, 70.0, 80.0, 90.0, 100.0]

    def sx(v: float) -> float:
        return ML + _symlog(v, x_threshold) / sx_max * (W - ML - MR)

    def sy(v: float) -> float:
        return MT + (1.0 - (_symlog(v, y_threshold) - sy_lo) / (sy_hi - sy_lo)) * (H - MT - MB)
    out: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" '
        'aria-label="Pareto frontier plot: USD per 1M generated tokens vs capability">'
    ]
    for tv in xticks:
        x = sx(tv)
        out.append(
            f'<line x1="{x:.1f}" y1="{MT}" x2="{x:.1f}" y2="{H - MB}" stroke="#d0d7de" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{x:.1f}" y="{H - MB + 18}" text-anchor="middle" '
            f'font-size="12" fill="#57606a">{_fmt_num(tv)}</text>'
        )
    for tv in yticks:
        y = sy(tv)
        out.append(
            f'<line x1="{ML}" y1="{y:.1f}" x2="{W - MR}" y2="{y:.1f}" stroke="#d0d7de" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{ML - 8}" y="{y + 4:.1f}" text-anchor="end" '
            f'font-size="12" fill="#57606a">{_fmt_num(tv)}</text>'
        )
    out.append(
        f'<line x1="{ML}" y1="{H - MB}" x2="{W - MR}" y2="{H - MB}" stroke="#1c1e21" stroke-width="1.5"/>'
    )
    out.append(
        f'<line x1="{ML}" y1="{MT}" x2="{ML}" y2="{H - MB}" stroke="#1c1e21" stroke-width="1.5"/>'
    )
    out.append(
        f'<text x="{(ML + W - MR) / 2:.1f}" y="{H - 8}" text-anchor="middle" '
        'font-size="13" fill="#1c1e21">USD per 1M generated tokens (zero-inclusive log scale)</text>'
    )
    out.append(
        f'<text x="18" y="{(MT + H - MB) / 2:.1f}" text-anchor="middle" '
        f'font-size="13" fill="#1c1e21" transform="rotate(-90 18 {(MT + H - MB) / 2:.1f})">'
        "capability (LiveBench Global Average; displayed range 50–100)</text>"
    )
    for p in points:
        x, y = sx(p["x"]), sy(p["y"])
        out.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#57606a" opacity="0.9"/>'
        )
    out.append("</svg>")
    return "".join(out)


def _render_html(run: Run, points: list[dict], has_points: bool) -> str:
    rate_rows = []
    for rec in run.models:
        cost = rec.get("cost")
        cap = rec["capability"]
        if rec.get("skipped_reason") and (not cost or cap["value"] is None):
            status = f"skipped: {rec['skipped_reason']}"
        elif rec.get("on_frontier") is True:
            status = "frontier (tied)" if rec.get("tied") else "frontier"
        else:
            status = "dominated (tied)" if rec.get("tied") else "dominated"
        if cost:
            cost_cell = _fmt_num(cost["amount"])
            won = escape(cost["rate"])
            cits = cost["citations"]
            cits_cell = (
                ", ".join(f'<a href="{escape(c)}">{escape(c)}</a>' for c in cits)
                if cits
                else "&#8212;"
            )
        else:
            cost_cell, won, cits_cell = "&#8212;", "&#8212;", "&#8212;"
        cap_cell = _fmt_num(cap["value"]) if cap["value"] is not None else "&#8212;"
        status_cls = ' class="frontier"' if status.startswith("frontier") else ""
        rate_rows.append(
            f"<tr><td>{escape(rec['lab'])}</td><td>{escape(rec['model'])}</td>"
            f'<td class="num">{cost_cell}</td><td>{won}</td><td>{cits_cell}</td>'
            f'<td class="num">{cap_cell}</td><td{status_cls}>{escape(status)}</td></tr>'
        )
    comp_col = (
        rec["composite"]["name"] if run.models else "livebench"
    )
    bench_head = (
        f'<th class="num">{escape(comp_col)}</th>'
        + "".join(f"<th>{escape(c)}</th>" for c in run.table_columns)
    )
    bench_rows = []
    for rec in run.models:
        cells = (
            f'<td class="num">{_fmt_num(rec["composite"]["value"]) if rec["composite"]["value"] is not None else "&#8212;"}</td>'
            + "".join(
                f'<td class="num">{_fmt_num(v) if v is not None else "&#8212;"}</td>'
                for v in (rec["scores"][c] for c in run.table_columns)
            )
        )
        bench_rows.append(f"<tr><td>{escape(rec['model'])}</td>{cells}</tr>")
    if has_points:
        plot = _render_plot_svg(points)
    else:
        plot = (
            '<div class="empty">No models currently plot: every model needs at least one '
            "rate <code>amount</code> (USD per 1M generated tokens) and a parseable "
            "LiveBench row to earn a point on this frontier. Fill the three rate amounts "
            "in each <code>taxonomy/**/model.json</code> and re-run the pipeline.</div>"
        )
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>LLM Pareto Frontier — inference cost vs capability</title>\n"
        "<style>\n"
        "body{font-family:Segoe UI,system-ui,Arial,sans-serif;margin:2rem auto;max-width:1200px;color:#1c1e21;background:#fff;padding:0 1rem}\n"
        "h1{font-size:1.5rem;margin-bottom:.2rem}\n"
        ".sub{color:#57606a;margin-top:0}\n"
        ".empty{border:1px solid #d0d7de;border-radius:8px;padding:2.5rem;text-align:center;color:#57606a;background:#f6f8fa}\n"
        "table{border-collapse:collapse;width:100%;margin-top:.5rem;font-size:.85rem}\n"
        "th,td{border:1px solid #d0d7de;padding:.35rem .5rem;text-align:left;vertical-align:top}\n"
        "th{background:#f6f8fa}\n"
        "td.num{text-align:right;font-variant-numeric:tabular-nums}\n"
        ".scroll{overflow-x:auto;margin-top:.5rem}\n"
        ".scroll table{min-width:1400px}\n"
        "td.frontier{color:#c8281e;font-weight:600}\n"
        ".foot{color:#57606a;font-size:.8rem;margin-top:1.5rem}\n"
        "</style>\n</head>\n<body>\n"
        "<h1>LLM Pareto Frontier</h1>\n"
        "<p class=\"sub\">Inference cost per 1M generated tokens (USD) vs capability "
        "(LiveBench Global Average — mean of the 7 category means, as "
        "published by LiveBench).</p>\n"
        f"{plot}\n"
        "<h2>Models</h2>\n"
        "<table>\n<thead><tr><th>Lab</th><th>Model</th><th>Cost (USD / 1M gen tokens)</th>"
        "<th>Winning rate</th><th>Rate citations</th><th>Capability (LiveBench Global Average)</th>"
        "<th>Status</th></tr></thead>\n<tbody>\n"
        + "\n".join(rate_rows)
        + "\n</tbody>\n</table>\n"
        "<h2>Benchmark values (LiveBench table)</h2>\n"
        '<div class="scroll"><table>\n<thead><tr><th>Model</th>'
        + bench_head
        + "</tr></thead>\n<tbody>\n"
        + "\n".join(bench_rows)
        + "\n</tbody>\n</table></div>\n"
        "<p class=\"foot\">Method: per-model cost is the <em>minimum</em> of the provided rate "
        "amounts — Jetson Thor home-electricity cost, OpenRouter list price, and the lab's "
        "price — all normalized to USD per million <strong>generated</strong> tokens "
        "(missing/zero amounts are excluded, never invented). A model is on the frontier "
        "when no other model is cheaper-or-equal <em>and</em> more-capable-or-equal with "
        "at least one strict. Capability is the LiveBench Global Average: the "
        "equally-weighted mean of the seven category means (math, coding, "
        "data_analysis, instruction_following, language, reasoning, "
        "agentic_coding; column map in scripts/pareto_pipeline.py), as published "
        "by LiveBench. This page is a deterministic function of models.csv and "
        "taxonomy/ (no timestamps) and is regenerated by scripts/pareto_pipeline.py on "
        "every run.</p>\n</body>\n</html>\n"
    )


def stage_frontier_render(run: Run) -> str:
    plottable = [
        rec for rec in run.models if rec.get("cost") and rec["capability"]["value"] is not None
    ]
    for rec in run.models:
        rec["on_frontier"] = False
        rec["tied"] = False
    for p in plottable:
        dominated = any(
            q is not p
            and q["cost"]["amount"] <= p["cost"]["amount"]
            and q["capability"]["value"] >= p["capability"]["value"]
            and (
                q["cost"]["amount"] < p["cost"]["amount"]
                or q["capability"]["value"] < p["capability"]["value"]
            )
            for q in plottable
        )
        rec_on = not dominated
        p["on_frontier"] = rec_on
    # exact (cost, capability) ties: keep both, flag the group
    groups: dict[tuple[float, float], list[dict]] = {}
    for p in plottable:
        key = (p["cost"]["amount"], p["capability"]["value"])
        groups.setdefault(key, []).append(p)
    for members in groups.values():
        if len(members) > 1:
            names = sorted(m["model"] for m in members)
            run.ties.append(names)
            for m in members:
                m["tied"] = True
    run.frontier = sorted(p["model"] for p in plottable if p["on_frontier"])
    points = [
        {
            "x": p["cost"]["amount"],
            "y": p["capability"]["value"],
            "label": p["model"],
            "frontier": p["on_frontier"],
            "tied": p["tied"],
            "access": "open" if _is_open_self_hosted_model(p) else "rentier",
        }
        for p in sorted(plottable, key=lambda r: (r["cost"]["amount"], r["model"]))
    ]
    html = _render_html(run, points, bool(points))
    out = run.repo_root / "artifacts" / "pareto-frontier.html"
    run.promote_or_noop(out, html.encode("utf-8"), "frontier_render")
    return (
        f"{len(plottable)}/{len(run.models)} models plottable, "
        f"{len(run.frontier)} frontier, {len(run.ties)} tie group(s) -> "
        "artifacts/pareto-frontier.html"
    )


# ---------------------------------------------------------------------------
# Stage 8: capability-cost svg chart (deterministic, timestamp-free)
# ---------------------------------------------------------------------------
def _render_capability_cost_svg(points: list[dict]) -> str:
    """Ranked cost/capability scatter with a ROC-style envelope.

    The area is descriptive, not classifier ROC AUC: it integrates the best
    available capability at each cost over the displayed, transformed axes.
    """
    plot_size = 1000
    ML, MR, MT = 88, 54, 132
    W = ML + plot_size + MR
    plot_bottom = MT + plot_size
    xs = sorted(p["x"] for p in points)
    ys = sorted(p["y"] for p in points)
    def centered_log_bounds(values: list[float]) -> tuple[float, float]:
        """Return positive bounds with data extrema at 10% and 90%."""
        lo, hi = values[0], values[-1]
        if lo <= 0:
            raise ValueError("positive logarithmic plot values are required")
        log_lo, log_hi = math.log(lo), math.log(hi)
        if math.isclose(log_lo, log_hi):
            log_lo -= math.log(1.25)
            log_hi += math.log(1.25)
        else:
            padding = (log_hi - log_lo) / 8.0
            log_lo -= padding
            log_hi += padding
        return math.exp(log_lo), math.exp(log_hi)

    xlo, xhi = centered_log_bounds(xs)
    ylo, yhi = centered_log_bounds(ys)
    log_xlo, log_xhi = math.log(xlo), math.log(xhi)
    log_ylo, log_yhi = math.log(ylo), math.log(yhi)
    xticks = _nice_ticks_log_decades(xlo, xhi)
    yticks = _nice_ticks_linear(ylo, yhi)

    def sx(v: float) -> float:
        return ML + (math.log(v) - log_xlo) / (log_xhi - log_xlo) * plot_size

    def sy(v: float) -> float:
        return MT + (1.0 - (math.log(v) - log_ylo) / (log_yhi - log_ylo)) * plot_size

    min_cost, max_cost = xs[0], xs[-1]
    min_cap, max_cap = ys[0], ys[-1]
    cost_span = max_cost - min_cost or 1.0
    cap_span = max_cap - min_cap or 1.0

    def coefficient(p: dict) -> float:
        cost_norm = (p["x"] - min_cost) / cost_span
        cap_norm = (p["y"] - min_cap) / cap_span
        return cap_norm / (1.0 + cost_norm)

    by_cost = sorted(points, key=lambda p: (p["x"], -p["y"], p["label"]))
    by_coefficient = sorted(points, key=lambda p: (-coefficient(p), p["label"]))
    envelope: list[tuple[float, float]] = []
    best_cap = ylo
    for p in by_cost:
        if p["y"] > best_cap:
            envelope.append((p["x"], p["y"]))
            best_cap = p["y"]
    previous_x, previous_cap, area = xlo, ylo, 0.0
    for cost, capability in [*envelope, (xhi, best_cap)]:
        area += ((sx(cost) - sx(previous_x)) / plot_size) * ((previous_cap - ylo) / (yhi - ylo))
        previous_x, previous_cap = cost, capability
    curve_parts = [f"M {sx(xlo):.1f},{sy(ylo):.1f}"]
    for cost, capability in envelope:
        curve_parts.extend((f"H {sx(cost):.1f}", f"V {sy(capability):.1f}"))
    curve_parts.append(f"H {sx(xhi):.1f}")
    curve_path = " ".join(curve_parts)
    linear_frontier_path = " ".join(
        ([f"M {sx(envelope[0][0]):.1f},{sy(envelope[0][1]):.1f}"] if envelope else [])
        + [f"L {sx(cost):.1f},{sy(capability):.1f}" for cost, capability in envelope[1:]]
    )
    label_y = plot_bottom + 82
    label_step = plot_size / len(by_coefficient)
    label_extent = max(340, max(len(f"{index + 1}. {p['label']}") for index, p in enumerate(by_coefficient)) * 7)
    H = label_y + label_extent + 42

    out: list[str] = [
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" '
        'aria-label="Capability-coefficient-ranked scatter with ROC-style envelope and normalized area">'
    ]
    out.append(
        "<style>"
        ".model{cursor:pointer;outline:none}"
        ".model-connector{stroke-width:.8;opacity:.23}"
        ".model-hit{stroke:transparent;stroke-width:16;pointer-events:stroke}"
        ".model-dot{stroke:#fff;stroke-width:1}"
        ".model-rentier .model-connector{stroke:#cf222e}"
        ".model-rentier .model-dot{fill:#cf222e}"
        ".model-rentier .model-label{fill:#cf222e}"
        ".model-open .model-connector{stroke:#1a7f37}"
        ".model-open .model-dot{fill:#1a7f37}"
        ".model-open .model-label{fill:#1a7f37}"
        ".model:hover .model-connector,.model:focus .model-connector{stroke-width:2.5;opacity:1}"
        ".model:hover .model-dot,.model:focus .model-dot{stroke-width:3}"
        ".model:hover .model-label,.model:focus .model-label{font-weight:700}"
        ".filter-control{cursor:pointer;outline:none}"
        ".filter-control:focus .filter-box{stroke:#0969da;stroke-width:2}"
        ".curve-control{cursor:pointer;outline:none}"
        ".curve-button{fill:#fff;stroke:#57606a;stroke-width:1}"
        ".curve-control.active .curve-button{fill:#ddf4ff;stroke:#0969da;stroke-width:2}"
        ".curve-control:focus .curve-button{stroke:#0969da;stroke-width:2}"
        "</style>"
    )
    out.append(
        f'<text x="{W / 2:.1f}" y="29" text-anchor="middle" '
        'font-size="18" fill="#1c1e21">Cost vs capability: coefficient-ranked models and best-available envelope</text>'
    )
    out.append(
        f'<text x="{W / 2:.1f}" y="51" text-anchor="middle" '
        f'font-size="12" fill="#57606a" id="curve-description" '
        f'data-budget-description="Best capability available by budget; area under curve = {area:.3f} (descriptive)">'
        f'Best capability available by budget; area under curve = {area:.3f} (descriptive)</text>'
    )
    out.append(
        '<text x="88" y="76" font-size="13" fill="#1c1e21">Curve:</text>'
        '<g id="curve-control-budget-step" class="curve-control active" data-curve="budget-step" '
        'role="radio" aria-checked="true" tabindex="0">'
        '<rect class="curve-button" x="132" y="61" width="218" height="23" rx="4"/>'
        '<text x="241" y="77" text-anchor="middle" font-size="12" fill="#1c1e21">Best capability by budget</text></g>'
        '<g id="curve-control-frontier-linear" class="curve-control" data-curve="frontier-linear" '
        'role="radio" aria-checked="false" tabindex="0">'
        '<rect class="curve-button" x="358" y="61" width="196" height="23" rx="4"/>'
        '<text x="456" y="77" text-anchor="middle" font-size="12" fill="#1c1e21">Pareto frontier (linear)</text></g>'
        '<g id="curve-control-none" class="curve-control" data-curve="none" '
        'role="radio" aria-checked="false" tabindex="0">'
        '<rect class="curve-button" x="562" y="61" width="94" height="23" rx="4"/>'
        '<text x="609" y="77" text-anchor="middle" font-size="12" fill="#1c1e21">Points only</text></g>'
    )
    out.append(
        '<g id="filter-rentier" class="filter-control" data-filter="rentier" '
        'role="checkbox" aria-label="Show rentier models" aria-checked="true" tabindex="0">'
        '<rect class="filter-box" x="284" y="91" width="16" height="16" rx="2" fill="#fff" stroke="#cf222e" stroke-width="1.5"/>'
        '<text id="filter-rentier-mark" x="292" y="104" text-anchor="middle" font-size="14" fill="#cf222e">&#10003;</text>'
        '<text x="307" y="104" font-size="12" fill="#cf222e">Rentier models</text></g>'
    )
    out.append(
        '<g id="filter-open" class="filter-control" data-filter="open" '
        'role="checkbox" aria-label="Show open self-hostable models" aria-checked="true" tabindex="0">'
        '<rect class="filter-box" x="605" y="91" width="16" height="16" rx="2" fill="#fff" stroke="#1a7f37" stroke-width="1.5"/>'
        '<text id="filter-open-mark" x="613" y="104" text-anchor="middle" font-size="14" fill="#1a7f37">&#10003;</text>'
        '<text x="628" y="104" font-size="12" fill="#1a7f37">Self-hostable models</text></g>'
    )
    for tv in xticks:
        x = sx(tv)
        out.append(
            f'<line x1="{x:.1f}" y1="{MT}" x2="{x:.1f}" y2="{plot_bottom}" stroke="#d0d7de" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{x:.1f}" y="{plot_bottom + 18}" text-anchor="middle" '
            f'font-size="12" fill="#57606a">{_fmt_num(tv)}</text>'
        )
    for tv in yticks:
        y = sy(tv)
        out.append(
            f'<line x1="{ML}" y1="{y:.1f}" x2="{W - MR}" y2="{y:.1f}" stroke="#d0d7de" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{ML - 8}" y="{y + 4:.1f}" text-anchor="end" '
            f'font-size="12" fill="#57606a">{_fmt_num(tv)}</text>'
        )
    out.append(
        f'<line x1="{ML}" y1="{plot_bottom}" x2="{W - MR}" y2="{plot_bottom}" stroke="#1c1e21" stroke-width="1.5"/>'
    )
    out.append(
        f'<line x1="{ML}" y1="{MT}" x2="{ML}" y2="{plot_bottom}" stroke="#1c1e21" stroke-width="1.5"/>'
    )
    out.append(
        f'<text x="{W / 2:.1f}" y="{plot_bottom + 42}" text-anchor="middle" '
        'font-size="13" fill="#1c1e21">cost (USD per 1M generated tokens; log scale)</text>'
    )
    out.append(
        f'<text x="{ML - 38}" y="{(MT + plot_bottom) / 2:.1f}" text-anchor="middle" '
        f'font-size="13" fill="#1c1e21" transform="rotate(-90 {ML - 38} {(MT + plot_bottom) / 2:.1f})">'
        "capability (LiveBench Global Average; log scale)</text>"
    )
    out.append(
        f'<g id="curve-budget-step" class="curve">'
        f'<path d="{curve_path} V {sy(ylo):.1f} Z" fill="#d0d7de" opacity="0.23"/>'
        f'<path d="{curve_path}" fill="none" stroke="#24292f" stroke-width="2.5"/>'
        "</g>"
    )
    out.append(
        f'<path id="curve-frontier-linear" class="curve" d="{linear_frontier_path}" '
        'fill="none" stroke="#24292f" stroke-width="2.5" stroke-dasharray="7 4" style="display:none"/>'
    )
    for index, p in enumerate(by_coefficient):
        label_x = ML + (index + 0.5) * label_step
        dot_x, dot_y = sx(p["x"]), sy(p["y"])
        access = p.get("access", "rentier")
        detail = (
            f'{p["label"]}: ${_fmt_num(p["x"])}/M; '
            f'{_fmt_num(p["y"])} capability; capability coefficient {coefficient(p):.3f}; {access}'
        )
        out.append(
            f'<g class="model model-{access}" data-access="{access}" tabindex="0">'
            f'<title>{escape(detail)}</title>'
            f'<line class="model-connector" x1="{dot_x:.1f}" y1="{dot_y:.1f}" '
            f'x2="{label_x:.1f}" y2="{label_y - 9}"/>'
            f'<line class="model-hit" x1="{dot_x:.1f}" y1="{dot_y:.1f}" '
            f'x2="{label_x:.1f}" y2="{label_y - 9}"/>'
            f'<circle class="model-dot" cx="{dot_x:.1f}" cy="{dot_y:.1f}" r="4.5"/>'
            f'<text class="model-label" x="{label_x:.1f}" y="{label_y}" '
            f'transform="rotate(90 {label_x:.1f} {label_y})" '
            f'font-size="11">{index + 1}. {escape(p["label"])}</text>'
            "</g>"
        )
    out.append(
        f'<text x="{W / 2:.1f}" y="{H - 28}" text-anchor="middle" '
        'font-size="11" fill="#57606a">'
        'names left-to-right: descending capability coefficient = min–max capability / (1 + min–max cost); both norms span 0–1 across plotted models</text>'
    )
    out.append(
        "<script><![CDATA[\n"
        "(() => {\n"
        "  const descriptions = {\n"
        "    'budget-step': document.getElementById('curve-description').dataset.budgetDescription,\n"
        "    'frontier-linear': 'Pareto frontier: straight segments connect consecutive non-dominated models',\n"
        "    none: 'Points only: no summary curve is displayed'\n"
        "  };\n"
        "  const setCurve = (selected) => {\n"
        "    document.getElementById('curve-budget-step').style.display = selected === 'budget-step' ? '' : 'none';\n"
        "    document.getElementById('curve-frontier-linear').style.display = selected === 'frontier-linear' ? '' : 'none';\n"
        "    document.getElementById('curve-description').textContent = descriptions[selected];\n"
        "    document.querySelectorAll('.curve-control').forEach((control) => {\n"
        "      const active = control.dataset.curve === selected;\n"
        "      control.classList.toggle('active', active);\n"
        "      control.setAttribute('aria-checked', String(active));\n"
        "    });\n"
        "  };\n"
        "  window.setCapabilityCurve = setCurve;\n"
        "  document.querySelectorAll('.curve-control').forEach((control) => {\n"
        "    const select = () => setCurve(control.dataset.curve);\n"
        "    control.addEventListener('click', select);\n"
        "    control.addEventListener('keydown', (event) => {\n"
        "      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); select(); }\n"
        "    });\n"
        "  });\n"
        "  const setFilter = (control, checked) => {\n"
        "    const kind = control.dataset.filter;\n"
        "    control.setAttribute('aria-checked', String(checked));\n"
        "    document.getElementById(`filter-${kind}-mark`).style.display = checked ? '' : 'none';\n"
        "    document.querySelectorAll(`.model-${kind}`).forEach((model) => { model.style.display = checked ? '' : 'none'; });\n"
        "  };\n"
        "  document.querySelectorAll('.filter-control').forEach((control) => {\n"
        "    const toggle = () => setFilter(control, control.getAttribute('aria-checked') !== 'true');\n"
        "    control.addEventListener('click', toggle);\n"
        "    control.addEventListener('keydown', (event) => {\n"
        "      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); toggle(); }\n"
        "    });\n"
        "  });\n"
        "})();\n]]></script>"
    )
    out.append("</svg>\n")
    return "".join(out)


def _render_capability_cost_html(svg: str) -> str:
    """Wrap the static SVG in browser controls for alternate curve views."""
    inline_svg = svg.split("?>\n", 1)[1]
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Interactive LLM cost-capability chart</title>\n<style>\n"
        "body{font-family:Segoe UI,system-ui,Arial,sans-serif;margin:2rem auto;max-width:1200px;color:#1c1e21;background:#fff;padding:0 1rem}\n"
        "h1{font-size:1.5rem;margin-bottom:.25rem}\n"
        ".sub{color:#57606a;margin-top:0}\n"
        ".controls{display:flex;align-items:center;gap:.6rem;margin:1.25rem 0}\n"
        "select{font:inherit;padding:.35rem .5rem}\n"
        ".chart{overflow:auto;border:1px solid #d0d7de;border-radius:8px;background:#fff}\n"
        ".chart svg{display:block;min-width:1142px;max-width:none}\n"
        "</style>\n</head>\n<body>\n<main>\n"
        "<h1>LLM cost-capability chart</h1>\n"
        "<p class=\"sub\">Switch the line without changing the model points, labels, or hover interactions.</p>\n"
        "<div class=\"controls\"><label for=\"curve-type\">Curve view</label>"
        "<select id=\"curve-type\">"
        "<option value=\"budget-step\">Best capability available by budget (step)</option>"
        "<option value=\"frontier-linear\">Pareto frontier (straight segments)</option>"
        "<option value=\"none\">Points only</option>"
        "</select></div>\n"
        f'<div class="chart">{inline_svg}</div>\n'
        "</main>\n<script>\n"
        "(() => {\n"
        "  const select = document.getElementById('curve-type');\n"
        "  const description = document.getElementById('curve-description');\n"
        "  const descriptions = {\n"
        "    'budget-step': description.dataset.budgetDescription,\n"
        "    'frontier-linear': 'Pareto frontier: straight segments connect consecutive non-dominated models',\n"
        "    none: 'Points only: no summary curve is displayed'\n"
        "  };\n"
        "  const setCurve = () => {\n"
        "    const selected = select.value;\n"
        "    if (window.setCapabilityCurve) { window.setCapabilityCurve(selected); return; }\n"
        "    document.getElementById('curve-budget-step').style.display = selected === 'budget-step' ? '' : 'none';\n"
        "    document.getElementById('curve-frontier-linear').style.display = selected === 'frontier-linear' ? '' : 'none';\n"
        "    description.textContent = descriptions[selected];\n"
        "  };\n"
        "  select.addEventListener('change', setCurve);\n"
        "  setCurve();\n"
        "})();\n</script>\n</body>\n</html>\n"
    )


def _render_capability_cost_svg_empty() -> str:
    W, H = 900, 240
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" '
        'aria-label="Capability-cost scatter: no plottable models">\n'
        f'<text x="{W / 2:.1f}" y="{H / 2:.1f}" text-anchor="middle" '
        'font-size="14" fill="#57606a">No models currently plot: every model needs a usable '
        "rate amount (USD per 1M generated tokens) and a parseable LiveBench row.</text>\n"
        "</svg>\n"
    )


def _render_capability_cost_svg_compact(points: list[dict]) -> str:
    """Render the expanded cohort without point labels or leader lines.

    Every dot retains its model/cost/score in a native SVG hover title. This
    scales to dense clusters without making nearby models unreadable.
    """
    W, H = 1000, 600
    ML, MR, MT, MB = 70, 30, 56, 96
    xs = sorted(p["x"] for p in points)
    ys = sorted(p["y"] for p in points)
    xhi, yhi = max(xs[-1] * 1.08, 1.0), max(ys[-1] * 2.0, 100.0)
    x_threshold, y_threshold = 1.0, 100.0
    sx_max, sy_max = _symlog(xhi, x_threshold), _symlog(yhi, y_threshold)
    xticks = _nice_ticks_symlog(xhi, x_threshold)
    yticks = _nice_ticks_symlog(yhi, y_threshold)

    def sx(v: float) -> float:
        return ML + _symlog(v, x_threshold) / sx_max * (W - ML - MR)

    def sy(v: float) -> float:
        return MT + (1.0 - _symlog(v, y_threshold) / sy_max) * (H - MT - MB)

    out = [
        '<?xml version="1.0" encoding="utf-8"?>\n',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Capability-cost scatter; hover a point for model details">',
        f'<text x="{(ML + W - MR) / 2:.1f}" y="26" text-anchor="middle" font-size="14" fill="#1c1e21">cost (USD per 1M generated tokens) vs capability (LiveBench Global Average)</text>',
    ]
    for tick in xticks:
        x = sx(tick)
        out.append(f'<line x1="{x:.1f}" y1="{MT}" x2="{x:.1f}" y2="{H - MB}" stroke="#d0d7de" stroke-width="1"/>')
        out.append(f'<text x="{x:.1f}" y="{H - MB + 18}" text-anchor="middle" font-size="12" fill="#57606a">{_fmt_num(tick)}</text>')
    for tick in yticks:
        y = sy(tick)
        out.append(f'<line x1="{ML}" y1="{y:.1f}" x2="{W - MR}" y2="{y:.1f}" stroke="#d0d7de" stroke-width="1"/>')
        out.append(f'<text x="{ML - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="12" fill="#57606a">{_fmt_num(tick)}</text>')
    out.extend([
        f'<line x1="{ML}" y1="{H - MB}" x2="{W - MR}" y2="{H - MB}" stroke="#1c1e21" stroke-width="1.5"/>',
        f'<line x1="{ML}" y1="{MT}" x2="{ML}" y2="{H - MB}" stroke="#1c1e21" stroke-width="1.5"/>',
        f'<text x="{(ML + W - MR) / 2:.1f}" y="{H - MB + 42}" text-anchor="middle" font-size="13" fill="#1c1e21">cost (USD per 1M generated tokens; zero-inclusive log scale)</text>',
        f'<text x="18" y="{(MT + H - MB) / 2:.1f}" text-anchor="middle" font-size="13" fill="#1c1e21" transform="rotate(-90 18 {(MT + H - MB) / 2:.1f})">capability (LiveBench Global Average; zero-inclusive log scale)</text>',
    ])
    for p in points:
        out.append(f'<circle cx="{sx(p["x"]):.1f}" cy="{sy(p["y"]):.1f}" r="5" fill="#57606a" opacity="0.9"/>')
    out.append(f'<text x="{(ML + W - MR) / 2:.1f}" y="{H - MB + 66}" text-anchor="middle" font-size="11" fill="#57606a">every dot is a model; hover for details. Cost = lowest documented rate; both axes use log1p zero-inclusive scaling.</text>')
    out.append("</svg>\n")
    return "".join(out)


def stage_capability_cost_chart(run: Run) -> str:
    plottable = [
        rec for rec in run.models if rec.get("cost") and rec["capability"]["value"] is not None
    ]
    points = [
        {
            "x": p["cost"]["amount"],
            "y": p["capability"]["value"],
            "label": p["model"],
            "frontier": p["on_frontier"],
            "tied": p["tied"],
            "access": "open" if _is_open_self_hosted_model(p) else "rentier",
        }
        for p in sorted(plottable, key=lambda r: (r["cost"]["amount"], r["model"]))
    ]
    svg = _render_capability_cost_svg(points) if points else _render_capability_cost_svg_empty()
    svg_out = run.repo_root / "artifacts" / "capability-cost.svg"
    html_out = run.repo_root / "artifacts" / "capability-cost.html"
    run.promote_or_noop(svg_out, svg.encode("utf-8"), "capability_cost_chart")
    if points:
        interactive_html = _render_capability_cost_html(svg)
    else:
        interactive_html = (
            "<!DOCTYPE html>\n<html lang=\"en\"><meta charset=\"utf-8\">"
            "<title>LLM cost-capability chart</title><p>No plottable models.</p></html>\n"
        )
    run.promote_or_noop(html_out, interactive_html.encode("utf-8"), "capability_cost_chart")
    return (
        f"{len(plottable)}/{len(run.models)} models plotted -> "
        "artifacts/capability-cost.svg + capability-cost.html"
    )


# ---------------------------------------------------------------------------
# Stage 9: report (checkpoint; also re-run best-effort on failure/interrupt)
# ---------------------------------------------------------------------------
def _write_report(run: Run) -> None:
    if run.report_written:
        return
    run.finished_utc = datetime.now(timezone.utc)
    models_out = []
    for rec in run.models:
        models_out.append(
            {
                "lab": rec["lab"],
                "model": rec["model"],
                "budget": rec["budget"],
                "path": f"taxonomy/{rec['lab_folder']}/{rec['model_folder']}/model.json",
                "livebench_row": rec["row_id"],
                "match_mode": rec["match_mode"],
                "capability": rec.get("capability"),
                "cost": rec.get("cost"),
                "plotted": bool(rec.get("cost") and rec.get("capability", {}).get("value") is not None),
                "on_frontier": bool(rec.get("on_frontier")),
                "tie_group": (
                    next((g for g in run.ties if rec["model"] in g), None)
                    if rec.get("tied")
                    else None
                ),
                "skipped_reason": rec.get("skipped_reason"),
            }
        )
    doc = {
        "pipeline_id": PIPELINE_ID,
        "run_id": run.run_id,
        "started_utc": run.started_utc.isoformat(),
        "finished_utc": run.finished_utc.isoformat(),
        "status": run.status,
        "stage_failed": run.stage_failed,
        "stages": {
            s: {
                "seconds": run.stage_seconds.get(s),
                "detail": run.stage_detail.get(s),
            }
            for s in MATERIAL_STAGES
        },
        "errors": run.errors,
        "warnings": run.warnings,
        "notes": run.notes,
        "changed_paths": run.changed_paths,
        "noop_paths": run.noop_paths,
        "models": models_out,
        "frontier": run.frontier,
        "ties": run.ties,
        "skipped": run.skipped,
    }
    report_dir = run.repo_root / "reports" / run.run_id
    atomic_write_bytes(report_dir / "run.json", (json.dumps(doc, indent=2) + "\n").encode("utf-8"))

    stage_lines = []
    for s in MATERIAL_STAGES:
        if s in run.stage_detail:
            mark = f"ok — {run.stage_detail[s]}"
        elif s == run.stage_failed:
            mark = (
                "interrupted (incomplete; partial work left at prior promoted bytes)"
                if run.status == "interrupted"
                else "failed (staged candidates not promoted)"
            )
        else:
            mark = "not reached"
        secs = run.stage_seconds.get(s)
        stage_lines.append(f"| {s} | {mark} | {secs if secs is not None else '—'} |")
    err_lines = "\n".join(f"- {e}" for e in run.errors) or "- none"
    skipped_lines = "\n".join(f"- {s['model']}: {s['reason']}" for s in run.skipped) or "- none"
    warn_lines = "\n".join(f"- {w}" for w in run.warnings) or "- none"
    changed_lines = "\n".join(f"- {p}" for p in run.changed_paths) or "- none (idempotent run)"
    frontier_line = ", ".join(run.frontier) if run.frontier else "- none (no model has both a cost amount and a capability score)"
    narrative = (
        f"# Run {run.run_id} — {run.status}\n\n"
        f"- pipeline: {PIPELINE_ID}\n"
        f"- started: {run.started_utc.isoformat()}\n"
        f"- finished: {run.finished_utc.isoformat()}\n\n"
        "## Stages\n\n"
        "| stage | detail | seconds |\n|---|---|---|\n"
        + "\n".join(stage_lines)
        + "\n\n## Errors\n\n" + err_lines + "\n\n"
        "## Result\n\n"
        f"- capability method: {CAPABILITY_NOTE}\n"
        f"- frontier: {frontier_line}\n"
        f"- tie groups: {('; '.join(', '.join(g) for g in run.ties)) or '- none'}\n\n"
        "## Skipped models\n\n" + skipped_lines + "\n\n"
        "## Warnings\n\n" + warn_lines + "\n\n"
        "## Source changes\n\n" + changed_lines + "\n\n"
        "## Next steps\n\n"
        "- Fill the missing rate `amount`s (USD per 1M generated tokens) in "
        "  `taxonomy/**/model.json`, each with a `citations` source; cost is the min of provided amounts.\n"
        "- Re-run the pipeline (VS Code: `Pareto Pipeline: Main`); model.json -> lab.json -> "
        "  taxonomy.json rolls up and `artifacts/pareto-frontier.html` re-renders.\n"
    )
    atomic_write_bytes(report_dir / "narrative.md", narrative.encode("utf-8"))
    run.report_written = True
    log(f"report persisted: reports/{run.run_id}/ (run.json + narrative.md)")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def _run_stages(run: Run) -> None:
    total = len(MATERIAL_STAGES)
    dispatch = {
        "discover": stage_discover,
        "whitepaper_md": stage_whitepaper_md,
        "generate": stage_generate,
        "rollup": stage_rollup,
        "cost": stage_cost,
        "capability": stage_capability,
        "frontier_render": stage_frontier_render,
        "capability_cost_chart": stage_capability_cost_chart,
        "report": stage_report,
    }
    for i, stage in enumerate(MATERIAL_STAGES):
        t0 = time.monotonic()
        run.stage = stage
        eta = (run.elapsed() / i) * (total - i - 1) if i else 0.0
        log(
            f"stage {i + 1}/{total}: {stage} ({i} completed, {total - i - 1} remaining after "
            f"this, elapsed {fmt_duration(run.elapsed())}, eta {fmt_duration(eta)})"
        )
        detail = dispatch[stage](run)
        secs = time.monotonic() - t0
        run.finish_stage(stage, detail, secs)
        log(
            f"       {stage} done in {fmt_duration(secs)} "
            f"(total {fmt_duration(run.elapsed())}); {detail}"
        )


def stage_report(run: Run) -> str:
    # Reached only when every earlier stage succeeded: terminal status here.
    run.status = "success" if run.changed_paths else "no-op"
    _write_report(run)
    return f"checkpoint written: reports/{run.run_id}/run.json + narrative.md"


def main() -> int:
    root = Path.cwd().resolve()
    run = Run(root)
    try:
        required = {
            "models.csv": (root / "models.csv").is_file(),
            "taxonomy/": (root / "taxonomy").is_dir(),
            "pipeline.yaml": (root / "pipeline.yaml").is_file(),
            "agentic-pipelines/AGENTS.md": (root / "agentic-pipelines" / "AGENTS.md").is_file(),
        }
        missing = [name for name, ok in required.items() if not ok]
        if missing:
            msg = (
                "refusing to run: the repo root must contain "
                + ", ".join(missing)
                + f" (cwd: {root}). For the framework: git submodule update --init agentic-pipelines"
            )
            log("error: " + msg)
            run.errors.append(msg)
            run.status = "failure"
            run.stage_failed = "bootstrap"
            return EXIT_FAIL
        log(f"run {run.run_id} starting (pipeline {PIPELINE_ID}, root {root})")
        _run_stages(run)
        run.status = "success" if run.changed_paths else "no-op"
    except KeyboardInterrupt:
        log(
            "interrupted (Ctrl+C): preserving truthful state of finished work only; "
            "unfinished work is NOT reported as successful"
        )
        run.status = "interrupted"
        if run.stage:
            run.stage_failed = run.stage
    except PipelineError as exc:
        log(f"error: stage {exc.stage} failed:")
        for m in exc.messages:
            log("  " + m)
        run.status = "failure"
        run.stage_failed = exc.stage
        run.errors.extend(exc.messages)
    except Exception as exc:  # unexpected: state must stay truthful
        msg = f"unexpected error in stage {run.stage!r}: {exc!r}"
        log("error: " + msg)
        run.status = "failure"
        if run.stage:
            run.stage_failed = run.stage
        run.errors.append(msg)
    finally:
        try:
            _write_report(run)
        except Exception as rex:
            log(f"error: failed to persist run report: {rex!r}")
    if run.status == "interrupted":
        return EXIT_INTERRUPTED
    if run.status == "failure":
        return EXIT_FAIL
    log(f"run {run.run_id} finished: {run.status}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
