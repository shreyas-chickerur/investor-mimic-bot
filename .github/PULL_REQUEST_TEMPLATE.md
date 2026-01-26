## Description

<!-- Provide a clear and concise description of your changes -->

## Type of Change

<!-- Check all that apply -->

- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📝 Documentation update
- [ ] 🔧 Configuration change
- [ ] ♻️ Code refactoring
- [ ] ⚡ Performance improvement
- [ ] 🔒 Security fix

## Motivation and Context

<!-- Why is this change required? What problem does it solve? -->
<!-- If it fixes an open issue, please link to the issue here -->

Fixes #(issue)

## Changes Made

<!-- List the specific changes made in this PR -->

- 
- 
- 

## Testing

<!-- Describe the tests you ran to verify your changes -->

### Test Coverage

- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Component tests added/updated
- [ ] Manual testing performed

### Test Results

```bash
# Paste test results here
make test
```

### Coverage Report

```bash
# Paste coverage report here
make test-coverage
```

## Impact Analysis

### Affected Components

<!-- List components/modules affected by this change -->

- 
- 

### Risk Assessment

<!-- Low / Medium / High -->

**Risk Level:** 

**Justification:**

### Rollback Plan

<!-- How can this change be rolled back if issues arise? -->

## Checklist

### Code Quality

- [ ] Code follows the style guidelines (Black, Ruff)
- [ ] Self-review of code completed
- [ ] Comments added for complex logic
- [ ] No debugging code or print statements left
- [ ] No hardcoded values (use config/env vars)

### Testing

- [ ] All tests pass locally (`make test`)
- [ ] Code coverage ≥ 60% (`make test-coverage`)
- [ ] No new test failures introduced
- [ ] Edge cases tested

### Security

- [ ] No secrets or API keys in code
- [ ] Security scan passed (`bandit -r src/`)
- [ ] Dependency vulnerabilities checked (`safety check`)
- [ ] No SQL injection or XSS vulnerabilities

### Documentation

- [ ] README.md updated (if applicable)
- [ ] CHANGELOG.md updated (for user-facing changes)
- [ ] Docstrings added/updated
- [ ] Comments explain "why" not "what"

### CI/CD

- [ ] All GitHub Actions checks pass
- [ ] Pre-commit hooks pass (`pre-commit run --all-files`)
- [ ] No merge conflicts with `main`
- [ ] Branch is up to date with `main`

### Trading System Specific

- [ ] No changes to risk parameters without justification
- [ ] No breaking changes to strategy logic
- [ ] Data validation schemas updated (if applicable)
- [ ] Monitoring/alerting configured (if applicable)
- [ ] Tested in dry-run mode (`make run-dry`)

## Screenshots/Logs

<!-- If applicable, add screenshots or logs to help explain your changes -->

## Performance Impact

<!-- Does this change affect performance? Provide benchmarks if applicable -->

- [ ] No performance impact
- [ ] Performance improved
- [ ] Performance degraded (justified below)

**Benchmarks:**

```
# Paste benchmark results here
```

## Deployment Notes

<!-- Any special deployment considerations? -->

- [ ] Requires database migration
- [ ] Requires environment variable changes
- [ ] Requires dependency updates
- [ ] Requires configuration changes
- [ ] Can be deployed without downtime

## Reviewer Notes

<!-- Anything specific you want reviewers to focus on? -->

## Post-Merge Tasks

<!-- Tasks to complete after merging -->

- [ ] Update production environment variables
- [ ] Run database migrations
- [ ] Monitor system for 24 hours
- [ ] Update documentation site
- [ ] Notify stakeholders

---

**By submitting this PR, I confirm that:**

- [ ] I have read and followed the [CONTRIBUTING.md](../CONTRIBUTING.md) guidelines
- [ ] My code follows the project's code quality standards
- [ ] I have tested my changes thoroughly
- [ ] I understand this code will be used in a production trading system
