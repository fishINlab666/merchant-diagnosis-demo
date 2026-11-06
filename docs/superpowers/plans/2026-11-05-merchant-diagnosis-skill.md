# Merchant Diagnosis Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone AI merchant-diagnosis Skill that uses real Kimi calls for public diagnosis, arbitrary table mapping and full action plans, with deterministic source values and calculations.

**Architecture:** Python scripts use stdlib HTTP plus openpyxl for input. Three model stages produce structured JSON; only the mapping stage touches raw headers, while programs apply mappings to real cells and calculate scenarios. No production fallback answer exists.

**Tech Stack:** Python 3, openpyxl, Kimi Chat Completions JSON Mode, unittest, CSV/XLSX, SKILL.md packaging.

---

### Task 1: Real LLM client and skill scaffold

**Files:** Create `.agents/skills/merchant-diagnosis/SKILL.md`, `scripts/llm_client.py`, `references/methodology.md`, `references/schemas.md`, `evals/test_llm_client.py`.

- [ ] Write tests for JSON-mode HTTP payload, usage capture, malformed JSON and HTTP failure without fallback.
- [ ] Run tests and confirm import failure.
- [ ] Implement `LlmClient.complete_json(stage, payload)` using `KIMI_API_KEY`/`MOONSHOT_API_KEY`, `KIMI_BASE_URL`, `KIMI_MODEL`, and JSON Mode.
- [ ] Write the skill workflow and methodology without precomputed merchant answers.
- [ ] Run tests; expect PASS and commit `feat: add real Kimi skill client`.

### Task 2: File ingestion and AI mapping application

**Files:** Create `scripts/file_readers.py`, `scripts/pipeline.py`, `evals/test_pipeline.py`, `assets/demo-weekly.csv`, `assets/public-shop.txt`.

- [ ] Write failing tests for CSV header variants, XLSX multiple sheets, mapping application, missing fields, multi-store rejection and no fabricated values.
- [ ] Implement bounded table previews and AI mapping schema:

```python
{
  "mappings": [{"file_name": "x.csv", "sheet_name": "Sheet1", "grain": "store_week_tools", "fields": {"store_id": "门店编号", "spend": "推广费用"}],
  "missing_fields": ["week_start"],
  "notes": "..."
}
```

- [ ] Apply mappings only to whitelisted canonical fields, aggregate store/tool rows by store/week, and return missing-field warnings.
- [ ] Run ingestion tests; expect PASS and commit `feat: add AI-guided table normalization`.

### Task 3: Public and full diagnosis pipeline

**Files:** Modify `scripts/pipeline.py`; create `scripts/diagnose.py` and `evals/test_pipeline.py` additions.

- [ ] Write failing tests for public-stage model call, full-stage calculation, invalid tool/amount handling and one boundary note.
- [ ] Implement public diagnosis, AI full-plan generation, local scenario validation and Markdown rendering. Overwrite any model calculation with program calculation.
- [ ] Implement CLI `--public-file/--public-text --files --out`; public-only runs skip mapping, full runs execute all three model stages.
- [ ] Run pipeline tests and CLI offline checks; expect PASS and commit `feat: add AI merchant diagnosis workflow`.

### Task 4: Live EVALS and packaging

**Files:** Create `evals/live_smoke.py`, `evals/test_pipeline.py` additions, final `SKILL.md` updates.

- [ ] Run all offline tests and confirm real API errors are never masked.
- [ ] Run `evals/live_smoke.py` against synthetic public text and CSV; require three real model stages and token usage in `run-metadata.json`.
- [ ] Inspect actual public diagnosis, mapping preview and full report for usefulness, unsupported claims and repeated disclaimers; iterate with failing tests where needed.
- [ ] Package `.agents/skills/merchant-diagnosis` as `dist/merchant-diagnosis.skill` and inspect the archive.
- [ ] Report real-call evidence, remaining data limitations and exact run command; do not claim global installation.

## Self-review

- Every stage requested by the user uses the real model; no production preset answer path exists.
- Raw cell values and numeric calculations remain deterministic and independently testable.
- Public engagement, one-time boundary, full action plan, generic table mapping and run evidence map to Tasks 1–4.
- `LlmClient.complete_json`, `map_tables`, `apply_mappings`, `calculate_scenario`, and `run_pipeline` names stay consistent.
