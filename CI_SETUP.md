# CI/CD Setup Documentation

## Overview

This project uses GitHub Actions for continuous integration and Dependabot for automated dependency management.

## GitHub Actions Workflows

### 1. CI Workflow (`.github/workflows/ci.yml`)

**Triggers:**
- Push to `main` branch
- All pull requests

**Jobs:**
1. **Lint and Test**
   - Sets up Python 3.11
   - Installs dependencies from `requirements-dev.txt`
   - Runs Ruff linter on `app/` and `tests/` directories
   - Runs pytest with coverage reporting
   - Uploads coverage to Codecov (optional)
   - Verifies app can import successfully

**Environment Variables:**
- Tests handle their own environment setup with mock/test values
- No GitHub secrets required for CI to pass

### 2. Dependabot Auto-Merge (`.github/workflows/dependabot-auto-merge.yml`)

**Triggers:**
- Dependabot pull requests (opened, synchronized, reopened)

**Jobs:**
1. **Auto-approve** - Automatically approves Dependabot PRs
2. **Auto-merge** - Waits for CI to pass, then auto-merges if successful

**How it works:**
- Dependabot creates PR → Auto-approved immediately
- Waits for "Lint and Test" CI job to complete
- If CI passes → Auto-merges with squash merge
- If CI fails → Adds comment to PR for manual review

**Permissions:**
- Requires `contents: write` and `pull-requests: write`
- Uses `GITHUB_TOKEN` (automatically provided)

## Dependabot Configuration

### Configuration (`.github/dependabot.yml`)

**Python Dependencies:**
- Checks weekly on Mondays at 9:00 AM
- Groups minor and patch updates together
- Separate groups for development and production dependencies
- Labels PRs with `dependencies` and `python`
- Commit message prefix: `chore`
- Maximum 10 open PRs

**GitHub Actions:**
- Checks weekly on Mondays at 9:00 AM
- Updates action versions automatically
- Labels PRs with `dependencies` and `github-actions`

**Security Updates:**
- Dependabot automatically creates PRs for security vulnerabilities
- These are prioritized and created immediately (not on schedule)

## Linting Configuration

### Ruff (`ruff.toml`)

**Settings:**
- Line length: 100 characters
- Target Python version: 3.11
- Selected rules:
  - pycodestyle errors and warnings (E, W)
  - pyflakes (F)
  - isort import sorting (I)
  - flake8-bugbear (B)
  - flake8-comprehensions (C4)
  - pyupgrade (UP)

**Ignored rules:**
- E501 (line too long - handled by formatter)
- B008 (function calls in argument defaults)
- C901 (complexity checks)

**Per-file ignores:**
- `__init__.py`: Unused imports allowed
- `tests/*`: Test-specific exceptions

## Testing

**Framework:** pytest with coverage

**Run tests locally:**
```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=app --cov-report=html
```

**Coverage reports:**
- Terminal summary (always shown)
- XML report (for Codecov)
- HTML report (optional, run `--cov-report=html`)

## Local Development

### Running the linter:
```bash
# Check code
ruff check app/ tests/

# Auto-fix issues
ruff check app/ tests/ --fix

# Check formatting
ruff format --check app/ tests/

# Auto-format
ruff format app/ tests/
```

### Pre-commit checks:
```bash
# Run all checks before committing
ruff check app/ tests/ --fix
pytest tests/ -v
```

## Workflow Status

**Check workflow status:**
- GitHub repository → Actions tab
- View all workflow runs
- Click on specific run to see detailed logs

**Status badges (add to README.md):**
```markdown
![CI](https://github.com/YOUR_USERNAME/meal-planner/workflows/CI/badge.svg)
```

## Troubleshooting

### CI failing on main branch:
1. Check workflow logs in Actions tab
2. Run tests locally: `pytest tests/ -v`
3. Run linter locally: `ruff check app/ tests/`
4. Fix issues and push again

### Dependabot PRs not auto-merging:
1. Check if CI passed on the PR
2. Verify "Lint and Test" job completed successfully
3. Check workflow logs for auto-merge job
4. Ensure repository has proper permissions enabled

### Linter errors:
```bash
# See what's wrong
ruff check app/ tests/

# Auto-fix what's possible
ruff check app/ tests/ --fix

# Format code
ruff format app/ tests/
```

## Security

**Dependabot Security Updates:**
- Automatically detects vulnerabilities in dependencies
- Creates PRs with security patches
- Prioritized over regular dependency updates
- Should be reviewed and merged quickly

**Best Practices:**
- Review Dependabot PRs regularly (even if auto-merged)
- Keep dependencies up to date
- Monitor GitHub Security tab for alerts
- Test thoroughly after dependency updates

## Maintenance

**Regular tasks:**
- Review auto-merged Dependabot PRs weekly
- Check CI workflow logs for any issues
- Update Python version in CI as needed (currently 3.11)
- Review and update Ruff rules as project evolves

**Updating CI:**
- Edit `.github/workflows/ci.yml`
- Test locally first
- Push to feature branch and verify before merging to main
