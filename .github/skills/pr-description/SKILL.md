---
name: pr-description
description: Generate a pull request description in English using the repository PR template and the current branch commit history. Use when the user asks things like "buatin pull request description", "create PR description", or requests a ready-to-paste PR body based on branch changes.
---

# PR Description From Commits

Generate a PR description directly from commit history on the current branch and format it to match `.github/pull_request_template.md`.

## Workflow

1. Run the helper script:

```bash
python3 .github/skills/pr-description-from-commits/scripts/build_pr_description.py
```

2. Copy content from root file `PR_DESCRIPTION.md` as the PR body.
3. Keep output in English.
4. Base the content on commit history in the branch (`base..HEAD`), not on unstaged working tree changes.
5. If needed, print content to terminal with `--stdout`.

## Rules

- Prefer commit range from `origin/main..HEAD`; fallback automatically to `main`, `origin/master`, or `master`.
- If no unique commits are found, report that clearly and ask for a target base branch.
- Keep the structure aligned with `.github/pull_request_template.md` sections.
- Do not invent issue IDs, reviewers, or test results.
- Keep checkbox items as checklist format.

## Resources

- Script: `scripts/build_pr_description.py`
- Notes: `references/output-guidelines.md`
