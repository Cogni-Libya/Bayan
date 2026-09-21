# Contributing to Bayan — Team Cogni

## Golden rules

1. **Never push to `main`.** Every change goes through a pull request.
2. **Every PR is linked to an issue** (`Closes #N` in the PR description).
3. **At least one approving review** before merging. Code owners are requested automatically.
4. **Never commit secrets or restricted data:** no `.env` / API keys, no SAMER data, no datasets or model weights.

> GitHub cannot enforce branch protection on this private repository on the Free plan, so these rules
> depend on everyone following them.

## Workflow

### 1. Pick or open an issue
Use the **Task** template for planned work and **Bug report** for problems. Assign yourself.

### 2. Create a branch

| Prefix | Use for |
|---|---|
| `feat/` | New functionality (app, pipeline stage) |
| `fix/` | Bug fixes |
| `data/` | Data generation, annotation, dataset changes |
| `train/` | Training and model experiments |
| `eval/` | Evaluation and benchmarking |
| `docs/` | README, references, deliverables |
| `chore/` | Repository setup, dependencies |

Example: `data/12-annotation-guidelines` (issue number + short description).

**If you have Write access:**

```bash
git switch main && git pull
git switch -c feat/12-short-description
```

**If you have Read or Triage access** (you cannot push to this repository): fork it on GitHub, then

```bash
git clone https://github.com/<your-username>/Bayan.git
cd Bayan
git remote add upstream https://github.com/Cogni-Libya/Bayan.git
git switch -c feat/12-short-description
```

Before starting new work, sync your fork: `git fetch upstream && git switch main && git merge upstream/main && git push`.

### 3. Commit
Small, focused commits with imperative messages: `Add annotation guidelines for level 3–4 sentences`.

### 4. Open a pull request
Push your branch and open a PR into `Cogni-Libya/Bayan:main`. Fill in the template. Keep PRs small.

### 5. Review
- Reviewers respond within one working day.
- Resolve every review conversation before merging.
- If `main` moved, click **Update branch**.

### 6. Merge
The author merges with **Squash and merge** once approved (the only merge method enabled). The branch is
deleted automatically.

## Setup

```bash
uv sync
cp .env.example .env   # add your own API key
```

`uv sync` installs torch with its CUDA libraries on Linux. No NVIDIA GPU? Skip them by installing outside the lockfile,
and run with `--no-sync` afterwards (a plain `uv run` re-syncs to the lockfile):

```bash
uv venv
UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu UV_INDEX_STRATEGY=unsafe-best-match uv pip install -r pyproject.toml
uv run --no-sync python scripts/camel_readability.py
```

Data download instructions: [`data/README.md`](data/README.md).
