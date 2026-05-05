#!/usr/bin/env bash
# audit-stale-branches.sh — Detect and optionally clean up stale branches and open PRs.
#
# Usage:
#   ./scripts/audit-stale-branches.sh [--cleanup] [--stale-branch-hours N] [--stale-pr-hours N]
#
# Flags:
#   --cleanup              Actually merge green PRs and delete stale branches (default: dry-run)
#   --stale-branch-hours   Hours since last commit before a branch is considered stale (default: 48)
#   --stale-pr-hours       Hours an approved/green PR can sit unmerged before flagging (default: 24)
#
# Environment:
#   GITHUB_TOKEN           Required for gh CLI (set automatically in GitHub Actions)
#   PAPERCLIP_API_URL      Paperclip API base URL (optional, enables done/cancelled issue check)
#   PAPERCLIP_API_KEY      Paperclip API key (optional, used with PAPERCLIP_API_URL)
#   PAPERCLIP_COMPANY_ID   Paperclip company ID (optional, used with PAPERCLIP_API_URL)

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
CLEANUP=false
STALE_BRANCH_HOURS=48
STALE_PR_HOURS=24
TARGET_BRANCH="development"
BRANCH_PATTERN="^LSO-"

# ── Parse args ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cleanup)       CLEANUP=true; shift ;;
    --stale-branch-hours) STALE_BRANCH_HOURS="$2"; shift 2 ;;
    --stale-pr-hours)     STALE_PR_HOURS="$2"; shift 2 ;;
    *) echo "Unknown flag: $1" >&2; exit 1 ;;
  esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────
now_epoch=$(date +%s)

hours_since() {
  local iso_date="$1"
  local then_epoch
  then_epoch=$(date -d "$iso_date" +%s 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%S" "${iso_date%%Z*}" +%s 2>/dev/null || echo 0)
  echo $(( (now_epoch - then_epoch) / 3600 ))
}

section() {
  echo ""
  echo "═══════════════════════════════════════════════════════════════"
  echo "  $1"
  echo "═══════════════════════════════════════════════════════════════"
}

ISSUES_FOUND=0

# ── 1. Stale open PRs (green checks, open > threshold) ───────────────────────
section "Open PRs with passing checks (open > ${STALE_PR_HOURS}h)"

stale_prs=()
while IFS=$'\t' read -r pr_number pr_branch pr_updated pr_title; do
  [[ -z "$pr_number" ]] && continue
  age_h=$(hours_since "$pr_updated")
  if [[ $age_h -ge $STALE_PR_HOURS ]]; then
    # Check if all status checks pass
    check_status=$(gh pr checks "$pr_number" --json "state" --jq '[.[] | select(.state != "SUCCESS" and .state != "SKIPPED")] | length' 2>/dev/null || echo "unknown")
    if [[ "$check_status" == "0" ]]; then
      echo "  PR #${pr_number} (${pr_branch}) — open ${age_h}h, all checks green"
      echo "    Title: ${pr_title}"
      stale_prs+=("$pr_number")
      ISSUES_FOUND=$((ISSUES_FOUND + 1))
      if [[ "$CLEANUP" == "true" ]]; then
        echo "    → Merging PR #${pr_number} into ${TARGET_BRANCH}..."
        if gh pr merge "$pr_number" --merge --delete-branch; then
          echo "    ✓ Merged and branch deleted."
        else
          echo "    ✗ Merge failed (may need manual review)."
        fi
      fi
    fi
  fi
done < <(gh pr list --base "$TARGET_BRANCH" --state open --json number,headRefName,updatedAt,title \
  --jq '.[] | [.number, .headRefName, .updatedAt, .title] | @tsv' 2>/dev/null || true)

if [[ ${#stale_prs[@]} -eq 0 ]]; then
  echo "  None found."
fi

# ── 2. Feature branches with no open PR and no recent commits ─────────────────
section "Stale feature branches (no PR, no commits in ${STALE_BRANCH_HOURS}h)"

stale_branches=()
# Get all remote feature branches matching the pattern
while IFS= read -r ref; do
  branch="${ref#origin/}"
  [[ "$branch" == "development" || "$branch" == "main" || "$branch" == "HEAD" ]] && continue
  [[ ! "$branch" =~ $BRANCH_PATTERN ]] && continue

  # Check if there's an open PR for this branch
  pr_count=$(gh pr list --head "$branch" --state open --json number --jq 'length' 2>/dev/null || echo "0")
  if [[ "$pr_count" -gt 0 ]]; then
    continue
  fi

  # Check last commit age
  last_commit_date=$(git log -1 --format="%aI" "origin/$branch" 2>/dev/null || echo "")
  [[ -z "$last_commit_date" ]] && continue
  age_h=$(hours_since "$last_commit_date")

  if [[ $age_h -ge $STALE_BRANCH_HOURS ]]; then
    echo "  ${branch} — last commit ${age_h}h ago, no open PR"
    stale_branches+=("$branch")
    ISSUES_FOUND=$((ISSUES_FOUND + 1))

    if [[ "$CLEANUP" == "true" ]]; then
      echo "    → Deleting remote branch ${branch}..."
      if git push origin --delete "$branch" 2>/dev/null; then
        echo "    ✓ Deleted."
      else
        echo "    ✗ Delete failed."
      fi
    fi
  fi
done < <(git branch -r --format='%(refname:short)' 2>/dev/null)

if [[ ${#stale_branches[@]} -eq 0 ]]; then
  echo "  None found."
fi

# ── 3. Branches for done/cancelled Paperclip issues ──────────────────────────
section "Branches linked to done/cancelled Paperclip issues"

done_branches=()
if [[ -n "${PAPERCLIP_API_URL:-}" && -n "${PAPERCLIP_API_KEY:-}" && -n "${PAPERCLIP_COMPANY_ID:-}" ]]; then
  while IFS= read -r ref; do
    branch="${ref#origin/}"
    [[ "$branch" == "development" || "$branch" == "main" || "$branch" == "HEAD" ]] && continue
    [[ ! "$branch" =~ $BRANCH_PATTERN ]] && continue

    # Extract issue identifier (e.g., LSO-123) from branch name
    issue_id=$(echo "$branch" | grep -oE 'LSO-[0-9]+' | head -1)
    [[ -z "$issue_id" ]] && continue

    # Query Paperclip API for this issue
    response=$(curl -sf -H "Authorization: Bearer $PAPERCLIP_API_KEY" \
      "${PAPERCLIP_API_URL}/api/companies/${PAPERCLIP_COMPANY_ID}/issues?q=${issue_id}&status=done,cancelled" 2>/dev/null || echo "")

    if [[ -n "$response" ]]; then
      match_count=$(echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
items = data if isinstance(data, list) else data.get('items', data.get('issues', []))
print(sum(1 for i in items if i.get('identifier') == '$issue_id'))
" 2>/dev/null || echo "0")

      if [[ "$match_count" -gt 0 ]]; then
        echo "  ${branch} — issue ${issue_id} is done/cancelled"
        done_branches+=("$branch")
        ISSUES_FOUND=$((ISSUES_FOUND + 1))

        if [[ "$CLEANUP" == "true" ]]; then
          echo "    → Deleting remote branch ${branch}..."
          if git push origin --delete "$branch" 2>/dev/null; then
            echo "    ✓ Deleted."
          else
            echo "    ✗ Delete failed."
          fi
        fi
      fi
    fi
  done < <(git branch -r --format='%(refname:short)' 2>/dev/null)
else
  echo "  Skipped (PAPERCLIP_API_URL, PAPERCLIP_API_KEY, or PAPERCLIP_COMPANY_ID not set)."
fi

if [[ ${#done_branches[@]} -eq 0 && -n "${PAPERCLIP_API_URL:-}" ]]; then
  echo "  None found."
fi

# ── Summary ───────────────────────────────────────────────────────────────────
section "Summary"
echo "  Stale PRs (green, open > ${STALE_PR_HOURS}h):        ${#stale_prs[@]}"
echo "  Stale branches (no PR, > ${STALE_BRANCH_HOURS}h):      ${#stale_branches[@]}"
echo "  Done/cancelled issue branches:         ${#done_branches[@]}"
echo "  Total issues found:                    ${ISSUES_FOUND}"

if [[ "$CLEANUP" == "true" ]]; then
  echo ""
  echo "  Mode: CLEANUP (changes were applied)"
else
  echo ""
  echo "  Mode: DRY-RUN (no changes made, use --cleanup to apply)"
fi

exit 0
