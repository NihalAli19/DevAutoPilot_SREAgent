# Contributing & Workflow — DevAutoPilot

This file documents how the project is built. Following it is what turns "the repo
has CI files" into "this project genuinely practices CI/CD" — which is the thing
worth being able to claim.

## Branching model

`main` is always green and deployable. **Never commit directly to `main`.** Each
phase (or sub-feature) gets its own short-lived branch:

```
phase-0-scaffold
phase-1-ml-pipeline
phase-2-monitoring-agent
phase-3-agent-graph
phase-4-azure-deploy
phase-5-saas-polish
```

Workflow for every change:

1. `git checkout -b phase-N-short-description`
2. Build the slice (small, logical commits).
3. Push the branch and open a Pull Request into `main`.
4. CI runs automatically. Fix anything red.
5. Self-review the diff against the checklist below, then merge **only when green**.
6. Delete the branch after merge.

## Commit messages

Small commits, one logical change each. Conventional-commit style is encouraged:

```
feat(ml): add LSTM autoencoder training script
fix(api): handle empty telemetry payload in /score
test(agents): smoke test for monitoring agent
chore(ci): raise coverage gate to 60%
```

## Run the same checks CI runs — before you push

CI is just these commands. Run them locally so you never push a red build:

```bash
# backend
cd backend
ruff check .
ruff format --check .
mypy app
pytest -q --cov=app --cov-report=term-missing --cov-fail-under=50

# ml
cd ../ml
pytest -q
```

### One-time setup the CI assumes

`backend/requirements.txt` includes the CI tooling (`mypy`, `pytest-cov`) and
`ml/requirements.txt` includes `pytest`. The tool config lives in
`backend/pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]   # errors, pyflakes, isort, pyupgrade, bugbear

[tool.mypy]
python_version = "3.11"
ignore_missing_imports = true         # relax early; tighten as the project matures
disallow_untyped_defs = false         # set true once the stubs are filled in
```

> The coverage gate starts at **50%** so early phases aren't blocked by stub files.
> Raise it (60 -> 70 -> 80) as real code lands — bumping the gate per phase is itself
> a good CI/CD habit to show.

## Pre-commit hooks (optional but recommended)

`.pre-commit-config.yaml` is included in the repo. Install it once and ruff runs
automatically on every commit, catching issues before CI does:

```bash
pip install pre-commit
pre-commit install
```

> Honest caveat: the `detect-private-key` and large-file hooks are safety nets,
> not guarantees — they catch common mistakes, not every secret pattern. Still
> keep real keys in `.env` (git-ignored) and GitHub repo secrets.

## Required GitHub branch protection (do this once)

This is the step that makes CI non-optional. In your GitHub repo:

**Settings -> Rules -> Rulesets -> New branch ruleset** (or **Settings -> Branches ->
Add rule** for the classic UI), then:

1. **Target branch:** `main` (Default branch).
2. Enable **Require a pull request before merging.**
   - Require approvals: 1 (or 0 if you're solo — you can still require the PR + CI).
   - Require review from Code Owners: off (solo project).
3. Enable **Require status checks to pass before merging.**
   - Require branches to be up to date before merging: **on**.
   - Add the required checks (they appear in the list after CI has run once):
     - `Backend (lint, types, tests)`
     - `ML (pipeline tests)`
4. Enable **Block force pushes.**
5. Enable **Restrict deletions** (prevents deleting `main`).
6. Optional: **Require linear history** (keeps a clean, rebase-style history).
7. Save.

After this, a broken build literally cannot merge into `main`.

> Tip: the status-check names only show up in the dropdown **after** the CI
> workflow has run at least once on a PR. Open your first PR, let CI run, then come
> back and add the checks.

## Definition of done (per phase)

A phase is "done" only when all of these are true:

- [ ] Feature built on its own branch, opened as a PR.
- [ ] CI is green (lint, format, types, tests, coverage gate).
- [ ] New code has tests; the ML pipeline has an eval step with a metric gate.
- [ ] No secrets in code; `.env.example` updated if new config was added.
- [ ] PR self-reviewed against the plan; merged to `main`; branch deleted.

## Deployment (CD — arrives in Phase 4)

Production deploys happen **through the pipeline, not the Azure portal**: a merge
to `main` (or a tagged release) triggers a deploy workflow that builds the
container, pushes it, and updates Azure Container Apps. The ML model deploys via
`ml-pipeline.yml` only after passing its evaluation gate. Manual portal clicking
is for first-time resource creation only, never for shipping code.
