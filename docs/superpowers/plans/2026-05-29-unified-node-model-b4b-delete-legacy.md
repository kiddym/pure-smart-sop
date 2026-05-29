# B4b — Delete Legacy Chapter/Step Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove all legacy chapter/step machinery (services, routers, endpoints, models, schemas, tables, tests) now that B4a made every live path node-native — leaving `ProcedureNode` the sole persistence model.

**Architecture:** Deletion-style, **not** red-green TDD — the full suite staying green **is** the test (per spec §9). Each task deletes one cohesive slice, then runs `cd backend && .venv/bin/python -m pytest -q` (expect green) and a residual-reference grep (expect no matches), then commits. Deletions are ordered so each commit still compiles: consumers (endpoints/routers/tests) go before the modules they import. **Prerequisite: B4a is merged to `main`.** Spec: `docs/superpowers/specs/2026-05-29-unified-node-model-b4-contract-design.md` (§6).

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, pytest. Python interpreter: `backend/.venv/bin/python`.

**Conventions:**
- Test commands run from `backend/`. Full suite: `.venv/bin/python -m pytest -q`.
- All commits end with the trailer `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (omitted below for brevity).
- "Residual grep clean" = the given `grep -rn ... backend/app` returns nothing.
- `git add` is always scoped to a `backend/...` path — never `git add -A` at repo root (the worktree's `frontend/node_modules` symlink must never be staged; this caused a real incident on `main`).

---

## Deletion order (each step compiles)

1. Dead endpoints in `procedures.py` (apply-marks / apply-layer-roles)
2. Legacy routers (`chapters.py`, `steps.py`) + registration
3. Legacy tests (so the suite stops importing soon-to-be-deleted modules)
4. Orphaned services (chapter/step/conversion/mark/layer/editor)
5. `numbering_service` + `node_sync`
6. Schemas + `get_detail`
7. Models + `Procedure` relationships + `models/__init__` + `conftest`
8. `_invariants` cleanup
9. Migration drop + `dev.db` rebuild
10. Final verification + finish branch

---

## Task 1: Delete apply-marks / apply-layer-roles endpoints

**Files:**
- Modify: `backend/app/routers/procedures.py` (delete handlers at lines 261-286 + imports)

- [ ] **Step 1: Delete the two handlers**

In `backend/app/routers/procedures.py` delete the `apply_marks` handler (`@router.post("/{procedure_id}/apply-marks" ...)`) and the `apply_layer_roles` handler (`@router.post("/{procedure_id}/apply-layer-roles" ...)`) in full.

- [ ] **Step 2: Remove now-unused imports**

Remove `mark_service`, `layer_apply_service` from the `app.services` import group, and `ApplyMarksResult`, `LayerApplyIn`, `LayerApplyResult` from the `app.schemas.node` import. Confirm:

```bash
grep -nE "mark_service|layer_apply_service|ApplyMarksResult|LayerApplyIn|LayerApplyResult|apply-marks|apply-layer-roles" backend/app/routers/procedures.py
```
Expected: no matches.

- [ ] **Step 3: Verify + commit**

```bash
cd backend && .venv/bin/python -m pytest -q     # expect green
git add backend/app/routers/procedures.py
git commit -m "chore(api): delete apply-marks + apply-layer-roles endpoints (B4b)"
```

---

## Task 2: Delete legacy chapters/steps routers

**Files:**
- Delete: `backend/app/routers/chapters.py`, `backend/app/routers/steps.py`
- Modify: wherever they are registered (find it)

- [ ] **Step 1: Find the registration site**

```bash
grep -rn "chapters\|steps" backend/app/main.py backend/app/routers/__init__.py
```
Note the `include_router(...)` lines for the chapters and steps routers.

- [ ] **Step 2: Delete the routers + their registration**

```bash
git rm backend/app/routers/chapters.py backend/app/routers/steps.py
```
Remove the two `include_router(...)` lines (and any `from app.routers import chapters, steps`-style import) found in Step 1.

- [ ] **Step 3: Verify**

```bash
grep -rn "routers.chapters\|routers.steps\|import chapters\|import steps" backend/app   # expect no matches
cd backend && .venv/bin/python -m pytest -q
```
Expected: the app imports cleanly and the suite is green. (Integration tests that hit `/chapters` or `/steps` are deleted in Task 3; if any fail here on import, jump to Task 3 first, then return — but service-level tests still pass because the services remain.)

- [ ] **Step 4: Commit**

```bash
git add -A backend/app
git commit -m "chore(api): delete legacy chapters + steps routers + registration (B4b)"
```

---

## Task 3: Delete legacy tests

**Files:**
- Delete the purely-legacy test modules.

- [ ] **Step 1: Inventory every test that touches a doomed symbol**

```bash
grep -rln "chapter_service\|step_service\|conversion_service\|mark_service\|layer_apply_service\|numbering_service\|node_sync\|editor_service\|convert-to-\|apply-marks\|apply-layer-roles" backend/tests
grep -rln '"/api/v1/chapters\|"/api/v1/steps\|/chapters\|/steps' backend/tests
```

- [ ] **Step 2: Delete the legacy-only test files**

```bash
git rm \
  backend/tests/unit/services/test_chapter_service.py \
  backend/tests/unit/services/test_step_service.py \
  backend/tests/unit/services/test_conversion_service.py \
  backend/tests/unit/services/test_mark_service.py \
  backend/tests/unit/services/test_layer_apply_service.py \
  backend/tests/unit/services/test_numbering_service.py \
  backend/tests/unit/services/test_node_sync.py \
  backend/tests/unit/services/test_editor_service.py \
  backend/tests/integration/test_node_sync_dualwrite.py
```
Also `git rm` any chapters/steps **router integration** test files surfaced by Step 1 (e.g. `backend/tests/integration/test_chapters.py`, `test_steps.py`) that exist. Do not delete `test_import_service.py`, `test_version_flow_service.py`, `test_procedure_service.py`, `test_node_service.py`, or `test_editor.py` — those were made node-native in B4a.

- [ ] **Step 3: Verify + commit**

```bash
cd backend && .venv/bin/python -m pytest -q     # expect green (no collection-import errors)
git add -A backend/tests
git commit -m "test: delete legacy chapter/step/conversion/mark/layer/numbering/node_sync/editor tests (B4b)"
```

---

## Task 4: Delete orphaned legacy services

**Files:**
- Delete: `chapter_service.py`, `step_service.py`, `conversion_service.py`, `mark_service.py`, `layer_apply_service.py`, `editor_service.py`

- [ ] **Step 1: Confirm no importers remain**

```bash
grep -rnE "chapter_service|step_service|conversion_service|mark_service|layer_apply_service|editor_service" backend/app
```
Expected: matches only inside the files about to be deleted (and possibly each other). If any **other** module imports one of them, stop and resolve (it indicates a missed live path).

- [ ] **Step 2: Delete**

```bash
git rm \
  backend/app/services/chapter_service.py \
  backend/app/services/step_service.py \
  backend/app/services/conversion_service.py \
  backend/app/services/mark_service.py \
  backend/app/services/layer_apply_service.py \
  backend/app/services/editor_service.py
```
If `backend/app/services/__init__.py` re-exports any of these names, remove those entries.

- [ ] **Step 3: Verify + commit**

```bash
grep -rnE "chapter_service|step_service|conversion_service|mark_service|layer_apply_service|editor_service" backend/app   # expect no matches
cd backend && .venv/bin/python -m pytest -q     # expect green
git add -A backend/app
git commit -m "chore(services): delete legacy chapter/step/conversion/mark/layer/editor services (B4b)"
```

---

## Task 5: Delete numbering_service + node_sync

**Files:**
- Delete: `backend/app/services/numbering_service.py`, `backend/app/services/node_sync.py`

- [ ] **Step 1: Confirm no importers**

```bash
grep -rnE "numbering_service|node_sync" backend/app
```
Expected: matches only inside the two files themselves. (`node_numbering` is a different, live module — do not touch it.)

- [ ] **Step 2: Delete**

```bash
git rm backend/app/services/numbering_service.py backend/app/services/node_sync.py
```
Remove any `__init__.py` re-exports of these names.

- [ ] **Step 3: Verify + commit**

```bash
grep -rnE "\bnumbering_service\b|\bnode_sync\b" backend/app   # expect no matches
cd backend && .venv/bin/python -m pytest -q     # expect green
git add -A backend/app
git commit -m "chore(services): delete numbering_service + node_sync dual-write scaffold (B4b)"
```

---

## Task 6: Delete legacy schemas + node-free get_detail

**Files:**
- Modify: `backend/app/services/procedure_service.py` (`get_detail`, imports)
- Modify: `backend/app/schemas/procedure.py` (`ProcedureSaveIn`, `ProcedureSaveResult`, `ProcedureDetail`, import)
- Modify: `backend/app/schemas/node.py` (delete legacy classes)

- [ ] **Step 1: Strip chapter/step assembly from `procedure_service`**

In `backend/app/services/procedure_service.py`:
- Delete the functions `_build_chapter_tree` (lines 597-625) and `_load_steps` (lines 628-636).
- In `get_detail`, remove the `chapters=_build_chapter_tree(db, proc_id),` and `steps=_load_steps(db, proc_id),` keyword arguments from the `ProcedureDetail(...)` call.
- Remove imports `from app.schemas.node import ChapterTreeNode, StepOut` (line 33), `from app.models.chapter import ProcedureChapter` (line 26), `from app.models.step import ProcedureStep` (line 30). **Keep** `from app.models.node import ProcedureNode` (added in B4a).

- [ ] **Step 2: Trim procedure schemas**

In `backend/app/schemas/procedure.py`:
- Delete the `from app.schemas.node import ChapterTreeNode, ChapterUpsert, StepOut, StepUpsert` line (line 15).
- Delete the `ProcedureSaveIn` class (lines 46-56) and the `ProcedureSaveResult` class (lines 219-222).
- In `ProcedureDetail` (lines 240-248), remove the `chapters: list[ChapterTreeNode] = ...` and `steps: list[StepOut] = ...` fields. Keep `procedure`, `attachments`, `fields`, `has_source_docx`.

- [ ] **Step 3: Delete legacy node schemas**

First find remaining importers of `app.schemas.node`:

```bash
grep -rn "from app.schemas.node import" backend/app
```

In `backend/app/schemas/node.py`, delete the legacy classes: `ChapterCreate`, `ChapterUpdate`, `ChapterMoveIn`, `ChapterOut`, `ChapterTreeNode`, `StepCreate`, `StepUpdate`, `StepMoveIn`, `StepOut`, `ChapterUpsert`, `StepUpsert`, `ApplyMarksResult`, `LayerApplyIn`, `LayerApplyResult`, `ConversionResult`. **Keep** any symbol still imported by live code per the grep above — in particular `FORM_TYPES` if it is referenced (check `grep -rn "FORM_TYPES" backend/app`; if used by `_invariants`/`node_service`, keep it). If the file ends up empty, `git rm` it and remove its (now-dead) imports.

- [ ] **Step 4: Verify + commit**

```bash
grep -rnE "ProcedureSaveIn|ProcedureSaveResult|ChapterTreeNode|ChapterUpsert|StepUpsert|\bStepOut\b" backend/app   # expect no matches
cd backend && .venv/bin/python -m pytest -q     # expect green
git add -A backend/app
git commit -m "chore(schemas): drop legacy chapter/step schemas + node-free get_detail (B4b)"
```

---

## Task 7: Delete legacy models + fixtures

**Files:**
- Delete: `backend/app/models/chapter.py`, `backend/app/models/step.py`
- Modify: `backend/app/models/procedure.py` (relationships), `backend/app/models/__init__.py` (exports), `backend/tests/conftest.py` (imports + factory methods)

- [ ] **Step 1: Confirm tests no longer use the legacy factories**

```bash
grep -rnE "factory\.chapter\(|factory\.step\(|\.chapter\(|\.step\(" backend/tests
grep -rnE "ProcedureChapter|ProcedureStep" backend/tests
```
Any remaining usage (outside `conftest.py`) must be converted to `factory.node(...)` / `ProcedureNode` first — there should be none after B4a + Task 3.

- [ ] **Step 2: Remove the relationships + exports + fixtures**

- In `backend/app/models/procedure.py`, delete the `chapters: Mapped[list[ProcedureChapter]] = relationship(...)` and `steps: Mapped[list[ProcedureStep]] = relationship(...)` lines (~59-61) and any `ProcedureChapter`/`ProcedureStep` imports there.
- In `backend/app/models/__init__.py`, remove the `from app.models.chapter import ProcedureChapter`, `from app.models.step import ProcedureStep` imports and their `__all__` entries.
- In `backend/tests/conftest.py`, remove `ProcedureChapter` and `ProcedureStep` from the `from app.models import (...)` block, and delete the `Factory.chapter(...)` and `Factory.step(...)` methods.

- [ ] **Step 3: Delete the model files**

```bash
git rm backend/app/models/chapter.py backend/app/models/step.py
```

- [ ] **Step 4: Verify + commit**

```bash
grep -rnE "ProcedureChapter|ProcedureStep" backend/app backend/tests   # expect no matches
cd backend && .venv/bin/python -m pytest -q     # expect green
git add -A backend/app backend/tests
git commit -m "chore(models): delete ProcedureChapter/ProcedureStep models, relationships, fixtures (B4b)"
```

---

## Task 8: `_invariants` cleanup

**Files:**
- Modify: `backend/app/services/_invariants.py`

- [ ] **Step 1: Check `enforce_content_kind_invariant` callers**

```bash
grep -rn "enforce_content_kind_invariant" backend/app
```
After Tasks 4-6 the only match should be its definition in `_invariants.py`.

- [ ] **Step 2: Delete it if orphaned**

If no callers remain, delete the `enforce_content_kind_invariant` function from `backend/app/services/_invariants.py` (and any helper used only by it). **Keep** `enforce_node_invariants` (live, used by `node_service`). If it still has callers, skip this task.

- [ ] **Step 3: Verify + commit**

```bash
grep -rn "enforce_content_kind_invariant" backend/app   # expect no matches
cd backend && .venv/bin/python -m pytest -q     # expect green
git add backend/app/services/_invariants.py
git commit -m "chore(invariants): drop orphaned enforce_content_kind_invariant (B4b)"
```

---

## Task 9: Migration + dev.db rebuild

**Files:**
- Create: `backend/alembic/versions/20260529_0001_drop_legacy_chapter_step.py`

- [ ] **Step 1: Write the migration**

Create `backend/alembic/versions/20260529_0001_drop_legacy_chapter_step.py`:

```python
"""drop legacy chapter/step tables (B4)

ProcedureNode is the sole persistence model after B4. Removes tb_procedure_chapter /
tb_procedure_step. Dev-only; data is not migrated (dev.db rebuilt from head).
"""
from __future__ import annotations

from alembic import op

revision: str = "drop_legacy_chapter_step"
down_revision: str | None = "add_procedure_node"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("tb_procedure_step")      # FK chapter_id → tb_procedure_chapter: drop first
    op.drop_table("tb_procedure_chapter")


def downgrade() -> None:
    # Irreversible by design: pytest builds schema from ORM models (not migrations), so this
    # is never exercised; dev.db is rebuilt from head; no production data exists.
    raise NotImplementedError(
        "B4 removed the legacy chapter/step tables; downgrade past this revision is "
        "unsupported — rebuild dev.db from head."
    )
```

- [ ] **Step 2: Rebuild dev.db from head**

```bash
cd backend && rm -f dev.db && .venv/bin/alembic upgrade head
```
Expected: completes without error; `alembic current` shows `drop_legacy_chapter_step (head)`.

- [ ] **Step 3: Confirm the tables are gone**

```bash
.venv/bin/python -c "import sqlite3; c=sqlite3.connect('dev.db'); print(sorted(r[0] for r in c.execute(\"select name from sqlite_master where type='table'\")))"
```
Expected: list contains `tb_procedure_node` but NOT `tb_procedure_chapter` / `tb_procedure_step`.

- [ ] **Step 4: Verify suite + commit**

```bash
.venv/bin/python -m pytest -q     # expect green (tests build schema from models, unaffected)
git add backend/alembic/versions/20260529_0001_drop_legacy_chapter_step.py
git commit -m "feat(db): migration dropping tb_procedure_chapter + tb_procedure_step (B4b)"
```

---

## Task 10: Final verification + finish branch

- [ ] **Step 1: Full residual-reference sweep**

```bash
grep -rnE "ProcedureChapter|ProcedureStep|chapter_service|step_service|conversion_service|mark_service|layer_apply_service|numbering_service|node_sync|editor_service|apply-marks|apply-layer-roles|convert-to-|ProcedureSaveIn|ProcedureSaveResult" backend/app
```
Expected: **no matches** anywhere in `backend/app`.

- [ ] **Step 2: App boots on the rebuilt DB**

```bash
cd backend && .venv/bin/python -c "from app.main import app; print('import ok')"
```
Expected: `import ok` with no errors.

- [ ] **Step 3: Fresh migration round-trip from scratch**

```bash
cd backend && rm -f /tmp/b4check.db && DATABASE_URL="sqlite:////tmp/b4check.db" .venv/bin/alembic upgrade head && echo "alembic ok"
```
Expected: `alembic ok`. (If the project reads the DB URL from a different env var/config, use that; the point is a clean `upgrade head` on an empty DB.)

- [ ] **Step 4: Smoke the live node path via the dev stack**

Per `.claude/skills/running-smartsop-dev`: launch backend + frontend, then drive with chrome-devtools MCP — import a Word doc, edit it in the node editor, copy it, and confirm `/edit` + `/view` render with zero console errors and no 5xx in the network log.

- [ ] **Step 5: Final full suite**

```bash
cd backend && .venv/bin/python -m pytest -q     # expect all green
cd ../frontend && npm test                      # expect green (unaffected by B4b)
```

- [ ] **Step 6: Finish the branch**

Use **superpowers:finishing-a-development-branch** to verify tests, present merge options, and complete.

---

## Self-Review Notes

- **Compile-at-each-commit:** consumers are deleted before their dependencies (endpoints → routers → tests → services → numbering/node_sync → schemas/get_detail → models → invariants). Each task ends green.
- **Schema source of truth:** pytest builds schema via `Base.metadata.create_all` (conftest), so deleting the chapter/step models removes those tables from the test schema automatically; the Alembic drop keeps `dev.db` consistent with the models. No migration-vs-model drift.
- **Keep, don't delete:** `node_numbering` (≠ `numbering_service`), `enforce_node_invariants`, `schemas/node_v2.py`, `routers/nodes.py`, `node_service`, `node_tree`, and `FORM_TYPES` if still referenced.
- **Frontend untouched** (B4b is backend-only); the `updateProcedure` type was handled in B4a. Frontend `types/node.ts` Layer/Apply leftovers are out of scope (separate cleanup).
