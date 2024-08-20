# GitHub & JIRA PR Automation Script

This Python script automates the process of checking for open pull requests (PRs) in specified GitHub repositories and verifies if any of those PRs are linked to a JIRA issue with a "Blocker" priority. If such PRs exist and are mergeable, the script will automatically merge them.

## Features

- **Fetch Open PRs**: The script fetches all open PRs for a specified branch in a GitHub repository.
- **JIRA Integration**: It checks if the PRs are linked to JIRA issues and determines their priority.
- **Automatic Merging**: If a PR is linked to a JIRA issue with "Blocker" priority, the script will automatically merge the PR if it is mergeable.
- **Color-Coded Output**: The script uses color coding to clearly indicate the status of PRs and actions performed:
  - **Green**: Indicates success, such as finding and merging a PR.
  - **Red**: Indicates errors or issues, such as no PRs found or no "Blocker" priority PRs.

## Requirements

- **Python 3.x**
- **Git**
- **GitHub API Token**: Set as the environment variable `GITHUB_TOKEN`.
- **JIRA API Token**: Set as the environment variable `JIRA_API_TOKEN`.

## Script Workflow 

Run github-jira-auto-merger.yml from workflows

Checkout Branch: The script clones the repository and checks out the specified branch.
Fetch PRs: It fetches all open PRs for that branch.
Check for Blocker Priority:
If no PRs are found, the script exits with an error.
If PRs are found, the script checks if any are linked to a JIRA issue with "Blocker" priority.
If no "Blocker" PRs are found, the script exits with an error.
Merge PR: If a "Blocker" priority PR is found and is mergeable, it is automatically merged.