# Pre-Commit Hook for Automatic ACTIONS.md Updates

This repository includes a pre-commit git hook that automatically updates the `ACTIONS.md` file whenever GitHub Actions workflow files are modified.

## How It Works

The pre-commit hook (`.git/hooks/pre-commit`) automatically:

1. **Detects workflow changes**: Monitors commits for changes to `.github/workflows/*.yml` files
2. **Regenerates truth table**: Runs `test_table.py` to create an updated execution matrix
3. **Auto-stages updates**: If `ACTIONS.md` changes, automatically adds it to the commit
4. **Provides feedback**: Shows clear messages about what's happening

## Setup

The hook is already configured and executable. When you commit changes to workflow files, you'll see output like:

```bash
$ git commit -m "Update build workflow"
GitHub Actions workflow files changed, updating ACTIONS.md...
Changed files: .github/workflows/build.yml
Analyzing codeql.yml:
  Events: ['push_master', 'pull_request']
Analyzing build.yml:
  Events: ['push_master', 'pull_request', 'merge_group', 'release', 'workflow_dispatch_amd64_only', 'workflow_dispatch_arm64_only', 'workflow_dispatch_both']
...
Generated truth table with 246 step executions
Output written to ACTIONS.md
✅ ACTIONS.md automatically updated and staged for commit
```

## Benefits

- **Always up-to-date**: `ACTIONS.md` stays synchronized with workflow changes
- **Zero overhead**: No manual steps required - runs automatically
- **Smart detection**: Only triggers when workflow files actually change
- **Safe operation**: Only adds `ACTIONS.md` to commit if it was actually updated

## Manual Usage

You can also run the script manually at any time:

```bash
python3 test_table.py
```

This generates the same truth table that the pre-commit hook creates automatically.

## Files

- `.git/hooks/pre-commit` - The pre-commit hook script
- `test_table.py` - The truth table generator
- `ACTIONS.md` - The generated execution truth table
