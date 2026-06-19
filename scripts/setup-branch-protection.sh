#!/usr/bin/env bash
#
# setup-branch-protection.sh
# One-shot, idempotent branch protection for `main` via the GitHub API.
# Run once:  bash scripts/setup-branch-protection.sh
# Requires:  gh CLI authenticated with `repo` scope
#            (in this project, `export GH_TOKEN=$(grep ^GITHUB_TOKEN= .env | cut -d= -f2)`
#             works since the token has the repo scope).
#
# Branch protection on the GitHub Free plan only works on PUBLIC repos.
# If the repo is private on a free plan, this script tells you how to fix that.

set -euo pipefail

# --- detect repo -------------------------------------------------------------
REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
VIS="$(gh repo view --json visibility -q .visibility)"
echo "Repo: $REPO  (visibility: $VIS)"

# --- protection requires a PUBLIC repo on Free ------------------------------
if [ "$VIS" != "PUBLIC" ]; then
  cat <<EOF

[!] Branch protection is NOT available on PRIVATE repos on the GitHub Free plan.
    Pick one, then re-run this script:

      1) Make the repo public (recommended for a portfolio project -- also gives
         unlimited Actions minutes and free ghcr.io):

           gh repo edit $REPO --visibility public --accept-visibility-change-consequences

      2) Or upgrade to GitHub Pro/Team and keep it private.

    Exiting without changes.
EOF
  exit 1
fi

# --- apply protection (idempotent: safe to re-run) ---------------------------
# NOTE: the "contexts" strings MUST exactly match the job names in ci.yml.
echo "Applying branch protection to main..."
gh api -X PUT "repos/$REPO/branches/main/protection" \
  -H "Accept: application/vnd.github+json" \
  --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["Backend (lint, types, tests)", "ML (pipeline tests)"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": { "required_approving_review_count": 0 },
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON

# --- verify ------------------------------------------------------------------
echo ""
echo "[ok] Protection applied. Current state on main:"
gh api "repos/$REPO/branches/main/protection" -q \
  '"  required checks : \(.required_status_checks.contexts | join(", "))",
   "  up-to-date req. : \(.required_status_checks.strict)",
   "  PR required     : yes (\(.required_pull_request_reviews.required_approving_review_count) approvals)",
   "  force pushes    : \(.allow_force_pushes.enabled)",
   "  deletions       : \(.allow_deletions.enabled)"'

# --- let the open PR flow through (merges only once checks are green) --------
echo ""
PR="$(gh pr list --base main --state open --json number -q '.[0].number' 2>/dev/null || true)"
if [ -n "${PR:-}" ]; then
  echo "Enabling auto-merge on open PR #$PR (merges automatically once CI is green)..."
  gh pr merge "$PR" --auto --squash --delete-branch \
    || echo "  (Auto-merge couldn't be enabled automatically. Run: gh pr merge $PR --squash --delete-branch)"
else
  echo "No open PR against main -- nothing to merge."
fi

echo ""
echo "Done. main is protected; required checks must pass before any merge."
