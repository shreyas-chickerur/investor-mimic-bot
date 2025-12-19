# GitHub Branch Protection Setup Guide

Step-by-step guide to configure branch protection rules and automated testing on pull requests.

---

## Part 1: GitHub Actions CI (Already Configured)

Your CI workflow is already set up at `.github/workflows/ci.yml` and will:

**Trigger on:**
- Every push to `main` or `develop` branches
- Every pull request to `main` or `develop` branches
- When PRs are opened, updated, or reopened

**What it does:**
1. Sets up Python 3.8 environment
2. Starts PostgreSQL test database
3. Installs all dependencies
4. Runs Black formatting checks (must pass)
5. Runs Flake8 linting (must pass)
6. Runs unit tests with coverage (must pass)
7. Runs integration tests (allowed to fail)
8. Runs functional tests (allowed to fail)
9. Uploads coverage report to Codecov

**Required to pass:**
- Black formatting
- Flake8 linting
- Unit tests

**Optional (won't block merge):**
- Integration tests
- Functional tests

---

## Part 2: Configure Branch Protection Rules

### Step 1: Go to Repository Settings

1. Navigate to your GitHub repository: https://github.com/shreyas-chickerur/investor-mimic-bot
2. Click on **Settings** tab (top right)
3. In the left sidebar, click **Branches** (under "Code and automation")

### Step 2: Add Branch Protection Rule for `main`

1. Click **Add rule** or **Add branch protection rule**
2. In "Branch name pattern", enter: `main`

### Step 3: Configure Protection Settings

**Check these boxes:**

#### Protect matching branches
- ✅ **Require a pull request before merging**
  - ✅ Require approvals: `1` (or more if you have team members)
  - ✅ Dismiss stale pull request approvals when new commits are pushed
  - ✅ Require review from Code Owners (optional)

- ✅ **Require status checks to pass before merging**
  - ✅ Require branches to be up to date before merging
  - In the search box, type and select these status checks:
    - `test` (this is your CI workflow job name)
    - Or search for specific checks like:
      - `Run linting (Black)`
      - `Run linting (Flake8)`
      - `Run unit tests`

- ✅ **Require conversation resolution before merging**
  - Ensures all PR comments are resolved

- ✅ **Require signed commits** (optional but recommended)
  - Adds extra security

- ✅ **Require linear history** (optional)
  - Prevents merge commits, requires rebase or squash

- ✅ **Include administrators**
  - Even admins must follow these rules

#### Rules applied to everyone including administrators
- ✅ **Allow force pushes** - Leave UNCHECKED (prevents force push)
- ✅ **Allow deletions** - Leave UNCHECKED (prevents branch deletion)

### Step 4: Save Changes

1. Scroll to bottom
2. Click **Create** or **Save changes**

### Step 5: Repeat for `develop` Branch (Optional)

If you use a `develop` branch:
1. Click **Add rule** again
2. Enter branch name: `develop`
3. Apply same settings as `main`
4. Click **Create**

---

## Part 3: Test the Setup

### Create a Test Pull Request

1. **Create a new branch:**
   ```bash
   git checkout -b test/branch-protection
   ```

2. **Make a small change:**
   ```bash
   echo "# Test" >> README.md
   git add README.md
   git commit -m "test: verify branch protection"
   git push -u origin test/branch-protection
   ```

3. **Create Pull Request:**
   - Go to GitHub repository
   - Click "Compare & pull request"
   - Set base branch to `main`
   - Click "Create pull request"

4. **Verify CI runs:**
   - You should see "Some checks haven't completed yet"
   - Wait for checks to complete
   - Should see: ✅ All checks have passed

5. **Try to merge:**
   - If checks pass, "Merge pull request" button will be green
   - If checks fail, button will be disabled with message: "Merging is blocked"

6. **Clean up:**
   - After testing, you can close the PR
   - Delete the test branch

---

## Part 4: What Happens Now

### When You Create a PR:

1. **Automatic CI Trigger**
   - GitHub Actions starts automatically
   - Runs all tests and checks
   - Takes ~2-5 minutes

2. **Status Checks Appear**
   - You'll see status checks in PR
   - Each check shows ✅ or ❌
   - Click "Details" to see logs

3. **Merge Button Behavior**
   - **All checks pass**: Button is green, can merge
   - **Any check fails**: Button is disabled
   - **Checks running**: Button shows "Merging is blocked"

4. **If Tests Fail**
   - Fix the issues in your branch
   - Commit and push fixes
   - CI automatically runs again
   - Repeat until all checks pass

### Example PR Flow:

```
1. Create feature branch
   ↓
2. Make changes and commit
   ↓
3. Push to GitHub
   ↓
4. Create Pull Request
   ↓
5. CI runs automatically (2-5 min)
   ↓
6. Review CI results
   ↓
   ├─ All pass → Can merge ✅
   └─ Some fail → Fix issues, push again, CI reruns
```

---

## Part 5: Viewing CI Results

### In Pull Request:

1. **Checks Tab**
   - Click "Checks" tab in PR
   - See all workflow runs
   - Click on job to see detailed logs

2. **Status Badges**
   - At bottom of PR description
   - Shows status of each check
   - Click to see details

3. **Commit Status**
   - Each commit shows check status
   - ✅ All checks passed
   - ❌ Some checks failed
   - 🟡 Checks in progress

### In Actions Tab:

1. Go to **Actions** tab in repository
2. See all workflow runs
3. Click on a run to see details
4. Click on job to see logs
5. Download artifacts if any

---

## Part 6: Troubleshooting

### Issue: Status checks not appearing in branch protection

**Solution:**
- Status checks only appear after they've run at least once
- Create a test PR first
- Wait for CI to complete
- Then add the status check name to branch protection

### Issue: Can't find the status check name

**Solution:**
1. Go to Actions tab
2. Click on a recent workflow run
3. The job name is what you need (e.g., "test")
4. Use this exact name in branch protection settings

### Issue: CI fails with "No module named X"

**Solution:**
- Add missing dependency to `requirements.txt`
- Or install in CI workflow with `pip install X`

### Issue: Tests pass locally but fail in CI

**Solution:**
- Check environment variables in CI
- Ensure test database is configured
- Check Python version matches (3.8)
- Review CI logs for specific errors

### Issue: CI takes too long

**Solution:**
- Current CI takes ~2-5 minutes
- Can optimize by:
  - Caching dependencies (already done)
  - Running tests in parallel
  - Skipping optional tests

---

## Part 7: Advanced Configuration

### Require Multiple Reviewers

In branch protection settings:
- Set "Required number of approvals before merging" to 2 or more

### Require Specific Reviewers

1. Create a `CODEOWNERS` file in repository root:
   ```
   # Require review from specific people
   * @shreyas-chickerur
   /ml/ @ml-team-member
   /services/ @backend-team-member
   ```

2. Enable "Require review from Code Owners" in branch protection

### Add More Status Checks

Edit `.github/workflows/ci.yml` to add:
- Security scanning
- Dependency checks
- Performance tests
- Documentation builds

### Require Signed Commits

1. Set up GPG key: https://docs.github.com/en/authentication/managing-commit-signature-verification
2. Enable "Require signed commits" in branch protection
3. All commits must be signed to merge

### Auto-merge When Checks Pass

1. Enable "Allow auto-merge" in repository settings
2. In PR, click "Enable auto-merge"
3. PR will merge automatically when all checks pass

---

## Part 8: Best Practices

### For Contributors:

1. **Always create a branch**
   - Never commit directly to `main`
   - Use descriptive branch names

2. **Run tests locally first**
   ```bash
   make test
   make lint
   ```

3. **Keep PRs small**
   - Easier to review
   - Faster CI runs
   - Less likely to have conflicts

4. **Write good PR descriptions**
   - What changed
   - Why it changed
   - How to test

5. **Respond to review comments**
   - Address all feedback
   - Mark conversations as resolved

### For Reviewers:

1. **Review code, not just tests**
   - CI passing doesn't mean code is good
   - Check for logic errors, security issues

2. **Test locally if needed**
   - Pull the branch
   - Run the code
   - Verify functionality

3. **Be constructive**
   - Suggest improvements
   - Explain reasoning
   - Approve when satisfied

---

## Part 9: Monitoring

### Check CI Health:

1. **Actions Tab**
   - See success/failure rates
   - Identify flaky tests
   - Monitor run times

2. **Insights → Actions**
   - Workflow usage statistics
   - Billing information (if applicable)
   - Performance metrics

3. **Set Up Notifications**
   - Settings → Notifications
   - Enable "Actions" notifications
   - Get alerts for failed runs

---

## Summary Checklist

### Setup (One-time):
- ✅ CI workflow exists (`.github/workflows/ci.yml`)
- ✅ Configure branch protection for `main`
- ✅ Require status checks to pass
- ✅ Require pull request reviews
- ✅ Test with a sample PR

### Every PR:
- ✅ Create branch from `main`
- ✅ Make changes and commit
- ✅ Run tests locally
- ✅ Push and create PR
- ✅ Wait for CI to pass
- ✅ Address review comments
- ✅ Merge when approved and checks pass

### Maintenance:
- ✅ Monitor CI performance
- ✅ Update dependencies regularly
- ✅ Fix flaky tests
- ✅ Keep CI fast (<5 minutes)

---

## Quick Reference

### Branch Protection URL:
```
https://github.com/shreyas-chickerur/investor-mimic-bot/settings/branches
```

### CI Workflow File:
```
.github/workflows/ci.yml
```

### Required Checks:
- `test` (main job name)
- Or specific: `Run linting (Black)`, `Run linting (Flake8)`, `Run unit tests`

### Test Commands:
```bash
# Run all tests
make test

# Run specific test types
make test-unit
make test-integration
make test-functional

# Run linting
make lint
make format
```

---

**Your repository is now protected! All code must pass tests before merging to `main`.**
