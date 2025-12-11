"""
GitHub event parser for extracting workflow parameters from webhook payloads.

This module provides functions to extract commit SHA, branch name, and other
metadata from GitHub webhook events for use in Argo Workflows.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class GitCommitInfo:
    """
    Represents extracted git commit information from a GitHub webhook event.
    """
    commit_sha: str
    branch: str
    repo_url: str
    repo_name: Optional[str] = None
    pusher: Optional[str] = None


def extract_commit_info(webhook_payload: Dict[str, Any]) -> GitCommitInfo:
    """
    Extract git commit information from a GitHub webhook payload.
    
    This function parses GitHub push event payloads and extracts the commit SHA,
    branch name, repository URL, and other metadata needed for workflow execution.
    
    Args:
        webhook_payload: The GitHub webhook event payload (JSON object)
        
    Returns:
        GitCommitInfo object containing extracted information
        
    Raises:
        KeyError: If required fields are missing from the payload
        ValueError: If the payload format is invalid
    """
    if not isinstance(webhook_payload, dict):
        raise ValueError("Webhook payload must be a dictionary")
    
    # Extract commit SHA from 'after' field (the commit SHA after the push)
    if 'after' not in webhook_payload:
        raise KeyError("Missing 'after' field in webhook payload")
    commit_sha = webhook_payload['after']
    
    if not commit_sha or not isinstance(commit_sha, str):
        raise ValueError("Invalid commit SHA in webhook payload")
    
    # Extract branch from 'ref' field (e.g., "refs/heads/main")
    if 'ref' not in webhook_payload:
        raise KeyError("Missing 'ref' field in webhook payload")
    ref = webhook_payload['ref']
    
    if not ref or not isinstance(ref, str):
        raise ValueError("Invalid ref in webhook payload")
    
    # Extract branch name from ref (remove "refs/heads/" prefix)
    if ref.startswith('refs/heads/'):
        branch = ref[len('refs/heads/'):]
    else:
        branch = ref
    
    # Extract repository information
    if 'repository' not in webhook_payload:
        raise KeyError("Missing 'repository' field in webhook payload")
    
    repository = webhook_payload['repository']
    
    if 'clone_url' not in repository:
        raise KeyError("Missing 'clone_url' in repository field")
    repo_url = repository['clone_url']
    
    if not repo_url or not isinstance(repo_url, str):
        raise ValueError("Invalid repository clone URL")
    
    # Extract optional fields
    repo_name = repository.get('full_name')
    
    # Extract pusher information if available
    pusher = None
    if 'pusher' in webhook_payload:
        pusher_info = webhook_payload['pusher']
        if isinstance(pusher_info, dict):
            pusher = pusher_info.get('name') or pusher_info.get('login')
    
    return GitCommitInfo(
        commit_sha=commit_sha,
        branch=branch,
        repo_url=repo_url,
        repo_name=repo_name,
        pusher=pusher
    )


def is_main_branch_push(webhook_payload: Dict[str, Any]) -> bool:
    """
    Check if the webhook event is a push to the main branch.
    
    Args:
        webhook_payload: The GitHub webhook event payload
        
    Returns:
        True if this is a push to main/master branch, False otherwise
    """
    try:
        ref = webhook_payload.get('ref', '')
        return ref in ['refs/heads/main', 'refs/heads/master']
    except (AttributeError, TypeError):
        return False
