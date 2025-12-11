"""
Property-based tests for GitHub event parsing.

These tests verify that git commit information is correctly extracted from
GitHub webhook payloads across a wide range of valid inputs.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from github_event_parser import extract_commit_info, is_main_branch_push, GitCommitInfo


# Hypothesis strategies for generating GitHub webhook payloads

@st.composite
def valid_commit_sha(draw):
    """Generate a valid git commit SHA (40 character hex string)."""
    return draw(st.text(
        alphabet='0123456789abcdef',
        min_size=40,
        max_size=40
    ))


@st.composite
def valid_branch_name(draw):
    """Generate a valid git branch name."""
    # Branch names can contain alphanumeric, hyphens, underscores, slashes
    return draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789-_/',
        min_size=1,
        max_size=50
    ).filter(lambda s: not s.startswith('/') and not s.endswith('/')))


@st.composite
def valid_repo_url(draw):
    """Generate a valid repository clone URL."""
    org = draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789-',
        min_size=1,
        max_size=30
    ))
    repo = draw(st.text(
        alphabet='abcdefghijklmnopqrstuvwxyz0123456789-_',
        min_size=1,
        max_size=30
    ))
    
    # Generate either HTTPS or SSH URL
    url_type = draw(st.sampled_from(['https', 'ssh']))
    
    if url_type == 'https':
        return f"https://github.com/{org}/{repo}.git"
    else:
        return f"git@github.com:{org}/{repo}.git"


@st.composite
def valid_github_webhook_payload(draw):
    """Generate a valid GitHub push event webhook payload."""
    commit_sha = draw(valid_commit_sha())
    branch = draw(valid_branch_name())
    repo_url = draw(valid_repo_url())
    
    # Extract org and repo from URL for full_name
    if 'github.com/' in repo_url:
        parts = repo_url.split('github.com/')[1].replace('.git', '').split('/')
        full_name = f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else "org/repo"
    elif 'github.com:' in repo_url:
        parts = repo_url.split('github.com:')[1].replace('.git', '').split('/')
        full_name = f"{parts[0]}/{parts[1]}" if len(parts) >= 2 else "org/repo"
    else:
        full_name = "org/repo"
    
    payload = {
        'after': commit_sha,
        'ref': f'refs/heads/{branch}',
        'repository': {
            'clone_url': repo_url,
            'full_name': full_name
        }
    }
    
    # Optionally add pusher information
    if draw(st.booleans()):
        pusher_name = draw(st.text(
            alphabet='abcdefghijklmnopqrstuvwxyz0123456789-',
            min_size=1,
            max_size=20
        ))
        payload['pusher'] = {'name': pusher_name}
    
    return payload


@st.composite
def invalid_github_webhook_payload(draw):
    """Generate an invalid GitHub webhook payload that should fail parsing."""
    payload_type = draw(st.sampled_from([
        'missing_after',
        'missing_ref',
        'missing_repository',
        'missing_clone_url',
        'empty_commit_sha',
        'empty_ref',
        'invalid_commit_sha_type',
        'invalid_ref_type'
    ]))
    
    # Start with a valid payload
    base_payload = {
        'after': draw(valid_commit_sha()),
        'ref': f'refs/heads/{draw(valid_branch_name())}',
        'repository': {
            'clone_url': draw(valid_repo_url()),
            'full_name': 'org/repo'
        }
    }
    
    # Corrupt it based on the type
    if payload_type == 'missing_after':
        del base_payload['after']
    elif payload_type == 'missing_ref':
        del base_payload['ref']
    elif payload_type == 'missing_repository':
        del base_payload['repository']
    elif payload_type == 'missing_clone_url':
        del base_payload['repository']['clone_url']
    elif payload_type == 'empty_commit_sha':
        base_payload['after'] = ''
    elif payload_type == 'empty_ref':
        base_payload['ref'] = ''
    elif payload_type == 'invalid_commit_sha_type':
        base_payload['after'] = 123  # Not a string
    elif payload_type == 'invalid_ref_type':
        base_payload['ref'] = ['not', 'a', 'string']
    
    return base_payload


# Feature: aphex-pipeline, Property 1: Git commit extraction
@settings(max_examples=100)
@given(payload=valid_github_webhook_payload())
def test_property_1_git_commit_extraction(payload):
    """
    Property 1: Git commit extraction
    
    For any GitHub webhook payload, when a workflow is triggered, the system should
    extract and store both the commit SHA and branch name from the event data.
    
    Validates: Requirements 1.3
    """
    # Extract commit info from the payload
    commit_info = extract_commit_info(payload)
    
    # Verify commit SHA is extracted correctly
    assert commit_info.commit_sha == payload['after']
    assert isinstance(commit_info.commit_sha, str)
    assert len(commit_info.commit_sha) > 0
    
    # Verify branch name is extracted correctly
    # Branch should be extracted from ref (removing "refs/heads/" prefix)
    expected_branch = payload['ref'].replace('refs/heads/', '')
    assert commit_info.branch == expected_branch
    assert isinstance(commit_info.branch, str)
    assert len(commit_info.branch) > 0
    
    # Verify repository URL is extracted
    assert commit_info.repo_url == payload['repository']['clone_url']
    assert isinstance(commit_info.repo_url, str)
    assert len(commit_info.repo_url) > 0
    
    # Verify optional fields
    if 'full_name' in payload['repository']:
        assert commit_info.repo_name == payload['repository']['full_name']
    
    if 'pusher' in payload and 'name' in payload['pusher']:
        assert commit_info.pusher == payload['pusher']['name']


# Feature: aphex-pipeline, Property 1: Git commit extraction (negative test)
@settings(max_examples=100)
@given(payload=invalid_github_webhook_payload())
def test_property_1_git_commit_extraction_invalid_payload(payload):
    """
    Property 1: Git commit extraction (negative test)
    
    For any invalid GitHub webhook payload, the system should raise an appropriate
    error rather than silently failing or returning incorrect data.
    
    Validates: Requirements 1.3
    """
    # Extraction should raise either KeyError or ValueError
    with pytest.raises((KeyError, ValueError)):
        extract_commit_info(payload)


# Feature: aphex-pipeline, Property 1: Git commit extraction (branch filtering)
@settings(max_examples=100)
@given(
    branch=valid_branch_name(),
    commit_sha=valid_commit_sha(),
    repo_url=valid_repo_url()
)
def test_property_1_main_branch_filtering(branch, commit_sha, repo_url):
    """
    Property 1: Git commit extraction (branch filtering)
    
    For any GitHub webhook payload, the system should correctly identify whether
    the push is to the main branch for filtering purposes.
    
    Validates: Requirements 1.1, 1.2
    """
    # Create payload with the given branch
    payload = {
        'after': commit_sha,
        'ref': f'refs/heads/{branch}',
        'repository': {
            'clone_url': repo_url,
            'full_name': 'org/repo'
        }
    }
    
    # Check if it's correctly identified as main branch push
    is_main = is_main_branch_push(payload)
    
    # Should return True only for main or master branches
    expected_is_main = branch in ['main', 'master']
    assert is_main == expected_is_main


# Feature: aphex-pipeline, Property 1: Git commit extraction (ref format handling)
@settings(max_examples=100)
@given(
    branch=valid_branch_name(),
    commit_sha=valid_commit_sha(),
    repo_url=valid_repo_url()
)
def test_property_1_ref_format_handling(branch, commit_sha, repo_url):
    """
    Property 1: Git commit extraction (ref format handling)
    
    For any branch name, the system should correctly extract the branch name
    regardless of whether the ref includes the "refs/heads/" prefix.
    
    Validates: Requirements 1.3
    """
    # Test with full ref format
    payload_with_prefix = {
        'after': commit_sha,
        'ref': f'refs/heads/{branch}',
        'repository': {
            'clone_url': repo_url,
            'full_name': 'org/repo'
        }
    }
    
    commit_info = extract_commit_info(payload_with_prefix)
    assert commit_info.branch == branch
    
    # The branch name should not include the "refs/heads/" prefix
    assert not commit_info.branch.startswith('refs/heads/')


# Feature: aphex-pipeline, Property 1: Git commit extraction (commit SHA format)
@settings(max_examples=100)
@given(payload=valid_github_webhook_payload())
def test_property_1_commit_sha_format(payload):
    """
    Property 1: Git commit extraction (commit SHA format)
    
    For any valid GitHub webhook payload, the extracted commit SHA should be
    a valid git commit hash format (40 character hexadecimal string).
    
    Validates: Requirements 1.3
    """
    commit_info = extract_commit_info(payload)
    
    # Verify commit SHA format
    assert len(commit_info.commit_sha) == 40
    assert all(c in '0123456789abcdef' for c in commit_info.commit_sha.lower())
