#!/usr/bin/env python3
import argparse
import re
import subprocess
import sys
from pathlib import Path


TEMPLATE_PATH = Path('.github/pull_request_template.md')
DEFAULT_BASE_CANDIDATES = ['origin/main', 'main', 'origin/master', 'master']


def run_git(args):
    result = subprocess.run(
        ['git', *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or 'git command failed')
    return result.stdout.strip()


def resolve_base_ref(cli_base):
    if cli_base:
        run_git(['rev-parse', '--verify', cli_base])
        return cli_base

    for candidate in DEFAULT_BASE_CANDIDATES:
        try:
            run_git(['rev-parse', '--verify', candidate])
            return candidate
        except RuntimeError:
            continue

    raise RuntimeError(
        'Cannot find a base branch reference. Provide one with --base <ref>.'
    )


def parse_commit_records(raw):
    records = []
    for item in raw.split('\x1e'):
        item = item.strip()
        if not item:
            continue
        parts = item.split('\x1f')
        if len(parts) < 3:
            continue
        commit_hash, subject, body = parts[0].strip(), parts[1].strip(), parts[2].strip()
        records.append({'hash': commit_hash, 'subject': subject, 'body': body})
    return records


def get_commit_records(commit_range):
    raw = run_git(
        [
            'log',
            '--no-merges',
            '--reverse',
            '--pretty=format:%H%x1f%s%x1f%b%x1e',
            commit_range,
        ]
    )
    records = parse_commit_records(raw)
    if records:
        return records

    # Fallback for branches that only contain merge commits.
    raw_with_merges = run_git(
        [
            'log',
            '--reverse',
            '--pretty=format:%H%x1f%s%x1f%b%x1e',
            commit_range,
        ]
    )
    return parse_commit_records(raw_with_merges)


def get_changed_files(commit_range):
    out = run_git(['diff', '--name-only', commit_range])
    return [line.strip() for line in out.splitlines() if line.strip()]


def infer_task_types(commits, files):
    joined_subjects = ' '.join(c['subject'].lower() for c in commits)

    def any_file(pred):
        return any(pred(f) for f in files)

    checks = {
        'Data Processing (for tasks involving data handling or manipulation)': any_file(
            lambda f: 'data' in f.lower() or f.endswith(('.csv', '.xlsx', '.parquet'))
        ),
        'Model Training (for tasks involving model training)': any_file(
            lambda f: 'train' in f.lower() or 'model' in f.lower()
        ),
        'API Development (for developing or serving model via API)': any_file(
            lambda f: 'backend/' in f or '/api/' in f or f.endswith(('.go', '.py', '.ts'))
        ),
        'UI Development (for developing or improving user interface)': any_file(
            lambda f: 'frontend/' in f or f.endswith(('.tsx', '.jsx', '.css', '.scss', '.html'))
        ),
        'Testing (for writing or updating tests)': any_file(
            lambda f: 'test' in f.lower() or 'spec' in f.lower()
        ),
        'Debugging (for fixing errors or investigating issues)': any(
            c['subject'].lower().startswith('fix') or 'bug' in c['subject'].lower()
            for c in commits
        ),
        'Refactor (for code improvements without changing functionality)': 'refactor' in joined_subjects,
        'Performance Improvement / Optimization (for optimizations related to speed or efficiency)': any(
            token in joined_subjects for token in ['perf', 'optimiz', 'speed', 'latency']
        ),
        'Security (for tasks related to security updates or patches)': any(
            token in joined_subjects for token in ['security', 'auth', 'vuln', 'xss', 'csrf']
        ),
        'Documentation (for updating or improving documentation)': any_file(
            lambda f: f.lower().startswith('docs/') or f.lower().endswith('.md')
        ),
        'Monitoring (for adding or updating monitoring capabilities)': any(
            token in joined_subjects for token in ['monitor', 'metric', 'observab', 'logging']
        ),
    }

    if not any(checks.values()):
        checks['All'] = True
    else:
        checks['All'] = False

    return checks


def extract_related_issues(commits):
    issue_ids = set()
    pattern = re.compile(r'#(\d+)')
    for commit in commits:
        text = f"{commit['subject']}\n{commit['body']}"
        for match in pattern.findall(text):
            issue_ids.add(match)

    return sorted(issue_ids, key=lambda x: int(x))


def build_how_to_test(files):
    steps = [
        '1. Check out this branch and sync dependencies.',
        '2. Run the relevant project checks for changed areas.',
        '3. Verify the expected behavior for the changes below.',
    ]

    if any(f.startswith('frontend/') for f in files):
        steps.insert(2, '   - Frontend: run the frontend test/lint/build commands.')
    if any(f.startswith('backend/') for f in files):
        steps.insert(2, '   - Backend: run backend tests and local service checks.')

    return '\n'.join(steps)


def render_template(base_ref, commits, files):
    task_types = infer_task_types(commits, files)
    related_issues = extract_related_issues(commits)

    summary_lines = [
        f'- This PR includes {len(commits)} commit(s) from `{base_ref}..HEAD`.',
        '- Main changes:',
    ]
    for commit in commits:
        summary_lines.append(f"  - {commit['subject']}")

    related_block = (
        '\n'.join(f'- Related to #{issue_id}' for issue_id in related_issues)
        if related_issues
        else '- None referenced in commit messages.'
    )

    type_labels = [
        'Data Processing (for tasks involving data handling or manipulation)',
        'Model Training (for tasks involving model training)',
        'API Development (for developing or serving model via API)',
        'UI Development (for developing or improving user interface)',
        'Testing (for writing or updating tests)',
        'Debugging (for fixing errors or investigating issues)',
        'Refactor (for code improvements without changing functionality)',
        'Performance Improvement / Optimization (for optimizations related to speed or efficiency)',
        'Security (for tasks related to security updates or patches)',
        'Documentation (for updating or improving documentation)',
        'Monitoring (for adding or updating monitoring capabilities)',
        'All',
    ]

    type_checklist = '\n'.join(
        f"- [{'x' if task_types.get(label, False) else ' '}] {label}" for label in type_labels
    )

    return f"""## Summary

{'\n'.join(summary_lines)}

## How to Test

{build_how_to_test(files)}

## Related Issues

{related_block}

## Author Checklist

- [ ] Code follows team coding standards and style guide
- [ ] Self-reviewed the code changes
- [ ] Added/updated tests for new functionality
- [ ] All tests pass locally
- [ ] Code is properly documented
- [ ] Synced with latest `main` branch
- [ ] PR title follows conventional commit format
- [ ] Meaningful commit messages used

## Additional Notes

- Generated from commit history only.

## Type of task

{type_checklist}

## Reviewer(s)

- [ ] @username1
- [ ] @username2
- [ ] @username3
"""


def main():
    parser = argparse.ArgumentParser(
        description='Generate PR description from current branch commits.'
    )
    parser.add_argument('--base', help='Base ref for commit range, e.g. origin/main')
    parser.add_argument(
        '--template',
        default=str(TEMPLATE_PATH),
        help='Path to PR template (checked for existence).',
    )
    parser.add_argument(
        '--output',
        default='PR_DESCRIPTION.md',
        help='Output markdown file path (default: PR_DESCRIPTION.md).',
    )
    parser.add_argument(
        '--stdout',
        action='store_true',
        help='Also print generated content to stdout.',
    )
    args = parser.parse_args()

    template_file = Path(args.template)
    if not template_file.exists():
        print(f'Error: template file not found: {template_file}', file=sys.stderr)
        return 1

    try:
        base_ref = resolve_base_ref(args.base)
        commit_range = f'{base_ref}..HEAD'
        commits = get_commit_records(commit_range)

        if not commits:
            print(
                f'No commits found in range {commit_range}. '
                'Provide another base via --base if needed.',
                file=sys.stderr,
            )
            return 2

        files = get_changed_files(commit_range)
        content = render_template(base_ref, commits, files)
        output_path = Path(args.output)
        output_path.write_text(content + '\n', encoding='utf-8')
        print(f'Wrote PR description to {output_path}')
        if args.stdout:
            print()
            print(content)
        return 0
    except RuntimeError as err:
        print(f'Error: {err}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
