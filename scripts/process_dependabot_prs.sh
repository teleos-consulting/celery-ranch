#!/bin/bash
# Script to test and process dependabot PRs
# Usage: ./process_dependabot_prs.sh [pr_number]

set -e

# Function to check and validate a dependabot PR
check_pr() {
  local pr_number=$1
  echo "Checking PR #$pr_number..."
  
  # Get PR details
  pr_info=$(gh pr view $pr_number --json title,author,state,headRefName)
  title=$(echo $pr_info | jq -r '.title')
  author=$(echo $pr_info | jq -r '.author.login')
  state=$(echo $pr_info | jq -r '.state')
  branch=$(echo $pr_info | jq -r '.headRefName')
  
  # Check if PR is from dependabot
  if [[ "$author" != "dependabot"* ]]; then
    echo "PR #$pr_number is not from dependabot, skipping"
    return 1
  fi
  
  # Check if PR is open
  if [[ "$state" != "OPEN" ]]; then
    echo "PR #$pr_number is not open, skipping"
    return 1
  fi
  
  echo "Processing dependabot PR #$pr_number: $title"
  echo "Branch: $branch"
  
  # Checkout the PR branch
  git fetch origin $branch
  git checkout $branch
  
  # Run tests to validate the PR
  echo "Running tests..."
  python -m pytest -xvs
  
  # Check linting
  echo "Running linters..."
  flake8 --count --select=E9,F63,F7,F82 --show-source --statistics ranch
  
  # Check types
  echo "Running type checker..."
  mypy ranch
  
  echo "All checks passed for PR #$pr_number!"
  
  # Add instructions for merging
  echo "You can now merge this PR with: gh pr merge $pr_number --squash"
  
  return 0
}

# Function to process all dependabot PRs
process_all_prs() {
  echo "Listing all open dependabot PRs..."
  pr_list=$(gh pr list --author dependabot --json number --jq '.[].number')
  
  if [[ -z "$pr_list" ]]; then
    echo "No open dependabot PRs found"
    return 0
  fi
  
  for pr in $pr_list; do
    check_pr $pr
  done
}

# Check if PR number argument is provided
if [[ -n "$1" ]]; then
  check_pr $1
else
  process_all_prs
fi