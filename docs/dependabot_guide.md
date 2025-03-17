# Managing Dependabot PRs

This guide explains how to effectively manage Dependabot PRs in the Ranch project.

## Workflow Options

There are three main ways to handle Dependabot PRs:

1. **Process individually**: Test and merge each PR separately
2. **Batch processing**: Combine multiple PRs into a single update
3. **Automated approach**: Use the provided script to test and review PRs

## Individual PR Processing

For each Dependabot PR:

1. Check the PR details and the dependency being updated
2. Use the GitHub CLI to check out the PR branch:
   ```bash
   gh pr checkout <PR_NUMBER>
   ```
3. Run tests to ensure nothing breaks:
   ```bash
   python -m pytest -xvs
   ```
4. Check linting and type checking:
   ```bash
   flake8 ranch
   mypy ranch
   ```
5. If all tests pass, merge the PR:
   ```bash
   gh pr merge <PR_NUMBER> --squash
   ```

## Batch Processing

To combine multiple Dependabot PRs:

1. List all Dependabot PRs:
   ```bash
   gh pr list --author dependabot
   ```
2. Create a new integration branch:
   ```bash
   git checkout main
   git checkout -b dependabot-updates
   ```
3. Cherry-pick each Dependabot commit:
   ```bash
   git cherry-pick <COMMIT_SHA1> <COMMIT_SHA2> <COMMIT_SHA3>
   ```
4. Run tests on the combined changes:
   ```bash
   python -m pytest -xvs
   flake8 ranch
   mypy ranch
   ```
5. Create a new PR with all the changes:
   ```bash
   git push -u origin dependabot-updates
   gh pr create --title "Combine Dependabot updates" --body "Combined updates from multiple Dependabot PRs"
   ```
6. After merging the combined PR, close the individual Dependabot PRs:
   ```bash
   gh pr comment <PR_NUMBER> --body "@dependabot close"
   ```

## Automated Approach

Use our script to automate testing and reviewing Dependabot PRs:

1. To check all open Dependabot PRs:
   ```bash
   ./scripts/process_dependabot_prs.sh
   ```

2. To check a specific PR:
   ```bash
   ./scripts/process_dependabot_prs.sh <PR_NUMBER>
   ```

The script will:
- Verify the PR is from Dependabot
- Check out the PR branch
- Run tests and linting
- Provide instructions for merging if all checks pass

## Dependabot Commands

You can interact with Dependabot directly by commenting on PRs:

- `@dependabot rebase` - Rebase the PR
- `@dependabot merge` - Merge the PR after CI passes
- `@dependabot squash and merge` - Squash and merge after CI passes
- `@dependabot close` - Close the PR
- `@dependabot ignore this dependency` - Ignore this dependency going forward

## Tips for Reviewing Dependabot PRs

1. **Check Breaking Changes**: Review changelogs and release notes for breaking changes
2. **Validate Tests**: Make sure all tests pass after the update
3. **Review CI Results**: Check CI pipeline results before merging
4. **Combine Related Updates**: Group updates to the same ecosystem or related packages
5. **Update Documentation**: Update any documentation that references specific versions

By following these guidelines, we can maintain up-to-date dependencies while ensuring code quality and stability.