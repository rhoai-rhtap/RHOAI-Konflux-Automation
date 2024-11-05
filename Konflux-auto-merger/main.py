import os
import json
import requests
import re
import subprocess
import argparse
import sys
import time
import yaml

# ANSI escape codes for color
GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'

# Get credentials from environment variables
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

# Hard-coded JIRA server URL
JIRA_SERVER = 'https://issues.redhat.com'

# GitHub API base URL
GITHUB_API_URL = 'https://api.github.com'

def load_config():
    try:
        with open('repos.json', 'r') as file:
            config = json.load(file)
        return config
    except FileNotFoundError:
        print(f"{RED}Error: 'repos.json' file not found.{RESET}")
        raise
    except json.JSONDecodeError:
        print(f"{RED}Error: 'repos.json' file is not a valid JSON.{RESET}")
        raise

def load_releases():
    try:
        with open('releases.yaml', 'r') as file:
            release_config = yaml.safe_load(file)
        return release_config.get('releases', [])
    except FileNotFoundError:
        print(f"{RED}Error: 'releases.yaml' file not found.{RESET}")
        raise
    except yaml.YAMLError:
        print(f"{RED}Error: 'releases.yaml' file is not a valid YAML.{RESET}")
        raise

def validate_branch(branch, allowed_releases):
    if branch not in allowed_releases:
        print(f"{RED}Branch '{branch}' is not in the list of allowed releases. Exiting.{RESET}")
        sys.exit(1)  # Exit with non-zero status if branch is not allowed
    else:
        print(f"{GREEN}Branch '{branch}' is valid and allowed to proceed.{RESET}")

def fetch_open_prs(org, repo, branch):
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    url = f'{GITHUB_API_URL}/repos/{org}/{repo}/pulls?state=open&base={branch}'
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    open_prs = response.json()
    return open_prs

def get_jira_id_from_pr(pr):
    title = pr.get('title', '')
    body = pr.get('body', '')

    # Ensure title and body are strings
    title = str(title)
    body = str(body)

    jira_id_pattern = r'[A-Z]+-\d+'
    
   # Check the title for a JIRA ID
    jira_id_match = re.search(jira_id_pattern, title)
    if jira_id_match:
        return jira_id_match.group(0)  # Return the found JIRA ID

    # Check the body for a JIRA ID
    jira_id_match = re.search(jira_id_pattern, body)
    if jira_id_match:
        return jira_id_match.group(0)  # Return the found JIRA ID

    # Return a message if no JIRA ID was found
    #return "No JIRA ID found in PR"
    return None

def get_jira_issue_details(jira_id, max_retries=3):
    headers = {
        'Authorization': f'Bearer {JIRA_API_TOKEN}'
    }
    url = f'{JIRA_SERVER}/rest/api/2/issue/{jira_id}'

    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            jira_details = response.json()
            return jira_details
        except requests.exceptions.HTTPError as err:
            if response.status_code == 403:
                print(f"{RED}HTTP error 403: Forbidden for JIRA ID {jira_id}. Skipping.{RESET}")
                return None
            elif response.status_code == 404:
                print(f"{RED}JIRA issue {jira_id} not found. Skipping.{RESET}")
                return None
            else:
                print(f"{RED}HTTP error occurred: {err} for JIRA ID {jira_id}. Retrying ({attempt + 1}/{max_retries})...{RESET}")
                time.sleep(2 ** attempt)  # Exponential backoff
        except Exception as err:
            print(f"{RED}Unexpected error: {err} for JIRA ID {jira_id}. Retrying ({attempt + 1}/{max_retries})...{RESET}")
            time.sleep(2 ** attempt)  # Exponential backoff

    print(f"{RED}Failed to retrieve JIRA details for ID {jira_id} after {max_retries} attempts.{RESET}")
    return None

def check_pr_mergeable(org, repo, pr_number):
    url = f'{GITHUB_API_URL}/repos/{org}/{repo}/pulls/{pr_number}'
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    pr_details = response.json()
    return pr_details.get('mergeable', False)

def merge_pr(org, repo, pr_number):
    url = f'{GITHUB_API_URL}/repos/{org}/{repo}/pulls/{pr_number}/merge'
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    data = {
        'commit_title': f'Merge PR #{pr_number}',
        'commit_message': 'Merged automatically because the linked JIRA issue has Blocker priority.'
    }

    response = requests.put(url, headers=headers, json=data)
    
    if response.status_code == 200:
        print(f"{GREEN}PR #{pr_number} in repo {repo} was successfully merged.{RESET}")

        # After merging, add a comment to the JIRA issue
        jira_id = get_jira_id_from_pr(pr)  # Obtain the JIRA ID from the PR
        if jira_id:
            pr_link = f"https://github.com/{org}/{repo}/pull/{pr_number}"  # Construct the PR link
            comment_on_jira_issue(jira_id, "The associated pull request has been merged.", pr_link)
    else:
        print(f"{RED}Failed to merge PR #{pr_number} in repo {repo}. Response: {response.status_code} - {response.json()}{RESET}")

def comment_on_jira_issue(jira_id, comment, pr_link, max_retries=3):
    headers = {
        'Authorization': f'Bearer {JIRA_API_TOKEN}',
        'Content-Type': 'application/json'
    }
    url = f'{JIRA_SERVER}/rest/api/2/issue/{jira_id}/comment'
    full_comment = f"{comment}\n\n[View Pull Request]({pr_link})"  # Add the PR link to the comment
    data = {
        'body': full_comment
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            print(f"{GREEN}Comment added to JIRA issue {jira_id}.{RESET}")
            return
        except requests.exceptions.HTTPError as err:
            print(f"{RED}Failed to add comment to JIRA issue {jira_id}: {err}{RESET}")
            time.sleep(2 ** attempt)  # Exponential backoff
        except Exception as err:
            print(f"{RED}Unexpected error while commenting on JIRA issue {jira_id}: {err}{RESET}")
            time.sleep(2 ** attempt)  # Exponential backoff

    print(f"{RED}Failed to add comment to JIRA issue {jira_id} after {max_retries} attempts.{RESET}")

def checkout_branch(org, repo, branch):
    try:
        subprocess.run(['git', 'clone', f'https://github.com/{org}/{repo}.git'], check=True)
        os.chdir(repo)
        subprocess.run(['git', 'checkout', branch], check=True)
    except subprocess.CalledProcessError as e:
        print(f"{RED}Error: Command '{e.cmd}' returned non-zero exit status {e.returncode}.{RESET}")
        print(f"{RED}Error: The branch '{branch}' does not exist in the repository '{repo}'.{RESET}")
        sys.exit(1)  # Exit with non-zero status to indicate failure

def is_user_in_org(org, username):
    headers = {'Authorization': f'token {GITHUB_TOKEN}'}
    url = f'{GITHUB_API_URL}/orgs/{org}/members/{username}'
    response = requests.get(url, headers=headers)
    return response.status_code == 204  # 204 No Content means the user is a member

def check_authors(org, pr):
    pr_author = pr['user']['login']  # Original PR author

    # Check if the PR author is a member of the organization
    if not is_user_in_org(org, pr_author):
        print(f"{RED}PR author '{pr_author}' is not a member of the '{org}' organization.{RESET}")
        return False  # Skip if the author is not in the organization

    # If PR author is valid, we don't need to check individual commits
    print(f"{GREEN}PR author '{pr_author}' is a valid member of the organization.{RESET}")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process GitHub repositories and JIRA issues.')
    parser.add_argument('--branch', required=True, help='Branch name to check out and process')
    args = parser.parse_args()

    branch_name = args.branch

    # Load allowed releases and validate branch
    allowed_releases = load_releases()
    validate_branch(branch_name, allowed_releases)

    # Load main configuration and proceed if branch is valid
    config = load_config()
    org = config['org']
    all_prs_found = False

    for component in config['components']:
        for repo in component['rhds_repos']:
            checkout_branch(org, repo, branch_name)
            open_prs = fetch_open_prs(org, repo, branch_name)

            if not open_prs:
                print(f"{RED}No open PRs found for repo: {repo}.{RESET}")
                continue

            for pr in open_prs:
                if not check_authors(org, pr):
                    print(f"{RED}Skipping PR #{pr['number']} due to author checks.{RESET}")
                    continue

                jira_id = get_jira_id_from_pr(pr)
                if jira_id:
                    jira_details = get_jira_issue_details(jira_id)
                    if jira_details and jira_details.get('fields', {}).get('priority', {}).get('name') == 'Blocker':
                        print(f"{GREEN}Merging PR #{pr['number']} in repo {repo} because JIRA {jira_id} is a Blocker issue.{RESET}")
                        if check_pr_mergeable(org, repo, pr['number']):
                            merge_pr(org, repo, pr['number'])
                        else:
                            print(f"{RED}PR #{pr['number']} is not mergeable.{RESET}")
                    else:
                        print(f"{RED}Skipping PR #{pr['number']} as the JIRA issue {jira_id} is not a Blocker.{RESET}")
                else:
                    print(f"{RED}No JIRA ID found in PR #{pr['number']}. Skipping.{RESET}")