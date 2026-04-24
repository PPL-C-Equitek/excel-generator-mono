# Output Guidelines

Use this skill to produce a ready-to-paste PR description.

## Inputs
- Commit history from current branch relative to base branch.
- PR template in `.github/pull_request_template.md`.

## Output constraints
- English only.
- Concise summary derived from commit subjects and bodies.
- "How to Test" should be practical but not claim execution results.
- "Related Issues" should only include issue IDs explicitly found in commit messages.
- Keep `Author Checklist` unchecked by default.
- Write output to root `PR_DESCRIPTION.md` by default for easy copy/paste.
