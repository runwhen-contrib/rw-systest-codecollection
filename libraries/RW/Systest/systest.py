import re, logging, json, jmespath, requests, os, time
from RW import platform
from RW.Core import Core
from datetime import datetime
from robot.libraries.BuiltIn import BuiltIn
from robot.api.deco import keyword

from collections import Counter

def get_slxs_with_tag(
    tag_list: list,
    rw_api_url: str = "https://papi.beta.runwhen.com/api/v3",
    api_token: platform.Secret = None,
    rw_workspace: str = "my-workspace",
) -> list:
    """Given a list of tags, return all SLXs in the workspace that have those tags.

    Args:
        tag_list (list): the given list of tags as dictionaries

    Returns:
        list: List of SLXs that match the given tags
    """
    url = f"{rw_api_url}/workspaces/{rw_workspace}/slxs"
    headers = {
        "Content-Type": "application/json", 
        "Authorization": f"Bearer {api_token.value}"
        }
    matching_slxs = []

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Ensure we raise an exception for bad responses
        all_slxs = response.json()  # Parse the JSON content
        results = all_slxs.get("results", [])

        for result in results:
            tags = result.get("spec", {}).get("tags", [])
            for tag in tags:
                if any(
                    tag_item["name"] == tag["name"]
                    and tag_item["value"] == tag["value"]
                    for tag_item in tag_list
                ):
                    matching_slxs.append(result)
                    break

        return matching_slxs
    except (
        requests.ConnectTimeout,
        requests.ConnectionError,
        json.JSONDecodeError,
    ) as e:
        warning_log(
            f"Exception while trying to get SLXs in workspace {rw_workspace}: {e}",
            str(e),
            str(type(e)),
        )
        platform_logger.exception(e)
        return []

def get_workspace_index_status(
    rw_api_url: str = "https://papi.beta.runwhen.com/api/v3",
    api_token: platform.Secret = None,
    rw_workspace: str = "my-workspace"
):
    """
    Example: 
    Get the index healfh of a workspace
    """
    url = f"{rw_api_url}/workspaces/{rw_workspace}/index-status"
    headers = {
        "Content-Type": "application/json", 
        "Authorization": f"Bearer {api_token.value}"
        }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()

def perform_task_search(
    rw_api_url: str = "https://papi.beta.runwhen.com/api/v3",
    api_token: platform.Secret = None,
    rw_workspace: str = "my-workspace",
    persona: str = None,
    query: str = "",
    slx_scope: list = []
):
    """
    Example: 
    Perform Task Search
    """

    if persona is None:
        # Now we construct persona from rw_workspace
        persona = f"{rw_workspace}--eager-edgar"
    url = f"{rw_api_url}/workspaces/{rw_workspace}/task-search"
    payload = {
        "query": [query],
        "scope": slx_scope,      
        # "start": "crt-ob-grnwhnnpr-depl-health",
        "persona": persona
    }
    headers = {
        "Content-Type": "application/json", 
        "Authorization": f"Bearer {api_token.value}"
        }
    resp = requests.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    return resp.json()

def create_runsession_from_task_search(
    search_response: dict,
    api_token,  # platform.Secret
    rw_api_url: str = "https://papi.beta.runwhen.com/api/v3",
    rw_workspace: str = "t-online-boutique",
    persona_shortname: str = "eager-edgar",
    query: str = "",
    score_threshold: float = 0.3,
    curl_script_filename: str = "create_runsession_curl.sh"
) -> dict:
    """
    Create a RunSession from the tasks in `search_response`, filtering by `score_threshold`.
    Then, generate a local shell script (`curl_script_filename`) with the curl command
    that can replicate this request.

    :param search_response: Dict from your "task-search" JSON
    :param api_token: platform.Secret wrapper around the token
    :param rw_api_url: Base URL for the RunWhen API
    :param rw_workspace: Short name of the workspace
    :param persona_shortname: Persona for the runsession
    :param query: The user query that led to these tasks
    :param score_threshold: Minimum score for tasks to include
    :param curl_script_filename: Name of the .sh file to write the curl command into
    :return: The JSON response from creating the RunSession
    """

    # Endpoint for creating a runsession
    url = f"{rw_api_url}/workspaces/{rw_workspace}/runsessions"

    tasks = search_response.get("tasks", [])
    # Build a map: slxName -> runRequest dict
    run_requests_map = {}

    for t in tasks:
        if t.get("score", 0) < score_threshold:
            continue

        ws_task = t.get("workspaceTask", {})
        slx = ws_task.get("slxName")
        task_name = ws_task.get("unresolvedTitle")
        if not slx or not task_name:
            # skip tasks if missing data
            continue

        if slx not in run_requests_map:
            run_requests_map[slx] = {
                "slxName": slx,
                "taskTitles": [],
                "fromSearchQuery": query,
                "fromIssue": None
            }
        run_requests_map[slx]["taskTitles"].append(task_name)

    # Convert map to list
    run_requests = list(run_requests_map.values())

    session_body = {
        "generateName": "automated-systest",
        "runRequests": run_requests,
        "personaShortName": persona_shortname,
        "active": True
    }

    # Prepare headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token.value}"
    }

    # # 1) Write out the curl command to a local file
    # #    We'll inline the JSON. For multiline readability, we might keep it short
    # #    or you can split it into a separate body.json file. This example does inline.
    # json_str = json.dumps(session_body)
    # curl_cmd = (
    #     f"#!/bin/bash\n\n"
    #     f"# This script replicates the request to create a RunSession.\n\n"
    #     f"curl -X POST '{url}' \\\n"
    #     f"  -H 'Content-Type: application/json' \\\n"
    #     f"  -H 'Authorization: Bearer {api_token.value}' \\\n"
    #     f"  -d '{json_str}'\n"
    # )

    # with open(curl_script_filename, "w", encoding="utf-8") as f:
    #     f.write(curl_cmd)
    
    # # Optionally make it executable
    # os.chmod(curl_script_filename, 0o755)

    # 2) Make the actual POST request in Python
    resp = requests.post(url, json=session_body, headers=headers)
    resp.raise_for_status()
    return resp.json()


def wait_for_runsession_tasks_to_complete(
    rw_workspace: str,
    runsession_id: int,
    rw_api_url: str,
    api_token: platform.Secret,
    poll_interval: float = 5.0,
    max_wait_seconds: float = 300.0
) -> dict:
    """
    Polls the RunSession until the number of runRequests stops growing
    for two consecutive checks, or until max_wait_seconds has passed.
    
    :param rw_workspace: The short name of the workspace (e.g. "t-online-boutique").
    :param runsession_id: The integer ID of the RunSession to monitor.
    :param rw_api_url: Base URL to the RunWhen API (e.g. "https://papi.test.runwhen.com/api/v3").
    :param api_token: The raw authorization token string.
    :param poll_interval: Seconds to wait between polls. Default 5s.
    :param max_wait_seconds: Stop polling after this many seconds. Default 300s (5 min).
    :return: The final RunSession JSON once stable, or the last JSON if timeout is reached.
    :raises TimeoutError: If we never see stability before max_wait_seconds.
    """
    endpoint = f"{rw_api_url}/workspaces/{rw_workspace}/runsessions/{runsession_id}"
    headers = {
        "Authorization": f"Bearer {api_token.value}",
        "Accept": "application/json"
    }
    
    start_time = time.time()
    stable_count = 0   # How many consecutive times the count has remained unchanged
    last_length = None
    
    while True:
        # 1) Fetch the RunSession JSON
        resp = requests.get(endpoint, headers=headers)
        resp.raise_for_status()
        session_data = resp.json()
        
        # 2) Count the runRequests
        run_requests = session_data.get("runRequests", [])
        current_length = len(run_requests)
        
        # 3) Compare with previous length
        if last_length is not None and current_length == last_length:
            stable_count += 1
        else:
            stable_count = 0
        
        last_length = current_length
        
        # 4) Check if stable for 2 consecutive polls
        if stable_count >= 3:
            # You could adjust logic to stable_count >= 2 if you really want 2 more polls.
            print(f"RunSession {runsession_id} is stable with {current_length} runRequests.")
            return session_data
        
        # 5) Check for timeout
        elapsed = time.time() - start_time
        if elapsed > max_wait_seconds:
            raise TimeoutError(
                f"RunSession {runsession_id} did not stabilize within {max_wait_seconds} seconds."
            )
        
        # 6) Sleep before next poll
        time.sleep(poll_interval)
    return session_data


def get_runsession_url(rw_runsession=None):
    """Return a direct link to the RunSession."""
    try:
        if not rw_runsession:
            rw_runsession = import_platform_variable("RW_SESSION_ID")
        rw_workspace = os.getenv("RW_WORKSPACE")
        rw_workspace_app_url = os.getenv("RW_FRONTEND_URL")
    except ImportError:
        BuiltIn().log(f"Failure getting required variables", level='WARN')
        return None

    runsession_url = f"{rw_workspace_app_url}/map/{rw_workspace}?selectedRunSessions={rw_runsession}"
    return runsession_url

def get_runsession_source(payload: dict) -> str:
    """
    Given a RunWhen payload dictionary, return the "source" string based on:
      1) If top-level "source" key exists, return that
      2) Otherwise, look at the first (earliest) runRequest by 'created' time, and
         check in order:
             fromSearchQuery, fromIssue, fromSliAlert, fromAlert
         Return the name of whichever key is non-null. 
      3) If nothing is found, return "Unknown".
    """

    # 1) Check for a top-level 'source' key
    if "source" in payload:
        return payload["source"]

    # 2) Otherwise, examine runRequests
    run_requests = payload.get("runRequests", [])
    if not run_requests:
        return "Unknown"

    # Sort runRequests by created time to find the earliest
    def _parse_iso_datetime(dt: str) -> datetime:
        # '2025-02-11T08:49:06.773513Z' -> parse with replacement of 'Z' to '+00:00'
        return datetime.fromisoformat(dt.replace("Z", "+00:00"))

    sorted_requests = sorted(run_requests, key=lambda rr: _parse_iso_datetime(rr["created"]))
    earliest_rr = sorted_requests[0]

    # 3) Check the relevant fields in the earliest runRequest
    source_keys = ["fromSearchQuery", "fromIssue", "fromSliAlert", "fromAlert"]
    for key in source_keys:
        val = earliest_rr.get(key)
        if val:
            # "fromSearchQuery" -> "searchQuery"
            # "fromIssue"       -> "issue"
            # "fromSliAlert"    -> "sliAlert"
            # "fromAlert"       -> "alert"
            stripped = key[4:]  # removes "from", leaving e.g. "SearchQuery"
            # optionally lowercase the first character:
            stripped = stripped[0].lower() + stripped[1:]
            return stripped
    # 4) If no source found
    return "Unknown"


def count_open_issues(data: str):
    """Return a count of issues that have not been closed."""
    open_issues = 0 
    runsession = json.loads(data) 
    for run_request in runsession.get("runRequests", []):
        for issue in run_request.get("issues", []): 
            if not issue["closed"]:
                open_issues+=1
    return(open_issues)

def get_open_issues(data: str):
    """Return a count of issues that have not been closed."""
    open_issue_list = []
    runsession = json.loads(data) 
    for run_request in runsession.get("runRequests", []):
        for issue in run_request.get("issues", []): 
            if not issue["closed"]:
                open_issue_list.append(issue)
    return open_issue_list

def generate_open_issue_markdown_table(data_list):
    """Generates a markdown report sorted by severity."""
    severity_mapping = {1: "🔥 Critical", 2: "🔴 High", 3: "⚠️ Medium", 4: "ℹ️ Low"}
    
    # Sort data by severity (ascending order)
    sorted_data = sorted(data_list, key=lambda x: x.get("severity", 4))
    
    markdown_output = "-----\n"
    for data in sorted_data:
        severity = severity_mapping.get(data.get("severity", 4), "Unknown")
        title = data.get("title", "N/A")
        next_steps = data.get("nextSteps", "N/A").strip()
        details = data.get("details", "N/A")
        
        markdown_output += f"#### {title}\n\n- **Severity:** {severity}\n\n- **Next Steps:**\n{next_steps}\n\n"
        markdown_output += f"- **Details:**\n```json\n- {details}\n```\n\n"
    
    return markdown_output

def get_open_issues(data: str):
    """Return a count of issues that have not been closed."""
    open_issue_list = []
    runsession = json.loads(data) 
    for run_request in runsession.get("runRequests", []):
        for issue in run_request.get("issues", []): 
            if not issue["closed"]:
                open_issue_list.append(issue)
    return open_issue_list

def summarize_runsession_users(data: str, output_format: str = "text") -> str:
    """
    Parse a JSON string representing a RunWhen 'runsession' object
    (with 'runRequests' entries), gather the unique participants and
    the engineering assistants involved, and return a summary in either
    plain text or Markdown format.

    :param data: JSON string with top-level 'runRequests' list, each item
                 possibly containing 'requester' and 'persona->spec->fullName'.
    :param output_format: "text" or "markdown" (default: "text").
    :return: A string summarizing the participants and engineering assistants.
    """
    try:
        runsession = json.loads(data)
    except json.JSONDecodeError:
        # If the payload is not valid JSON, handle or raise
        return "Error: Could not decode JSON from input."

    # Prepare sets to avoid duplicates
    participants = set()
    engineering_assistants = set()

    # Gather data from each runRequest if present
    for request in runsession.get("runRequests", []):
        # Extract persona full name
        persona = request.get("persona") or {}
        spec = persona.get("spec") or {}
        persona_full_name = spec.get("fullName", "Unknown")

        # Extract requester
        requester = request.get("requester")
        if not requester:
            requester = "Unknown"

        # Normalize system requesters
        if "@workspaces.runwhen.com" in requester:
            requester = "RunWhen System"

        # Add to sets
        participants.add(requester)
        engineering_assistants.add(persona_full_name)

    # Format output
    if output_format.lower() == "markdown":
        # Construct a Markdown list
        lines = ["#### Participants:"]
        # Participants
        for participant in sorted(participants):
            lines.append(f"- {participant}")
        # Engineering assistants
        lines.append("\n#### Engineering Assistants:")
        for assistant in sorted(engineering_assistants):
            lines.append(f"- {assistant}")
        return "\n".join(lines)
    else:
        # Plain text
        text_lines = []
        text_lines.append("Participants:")
        for participant in sorted(participants):
            text_lines.append(f"  - {participant}")
        text_lines.append("")
        text_lines.append("Engineering Assistants:")
        for assistant in sorted(engineering_assistants):
            text_lines.append(f"  - {assistant}")
        return "\n".join(text_lines)

def extract_issue_keywords(data: str):
    runsession = json.loads(data) 
    issue_keywords = set()
    
    for request in runsession.get("runRequests", []):
        issues = request.get("issues", [])
        
        for issue in issues:
            if not issue.get("closed", False):
                matches = re.findall(r'`(.*?)`', issue.get("title", ""))
                issue_keywords.update(matches)
    
    return list(issue_keywords)

def get_most_referenced_resource(data: str):
    runsession = json.loads(data) 
    
    keyword_counter = Counter()
    
    for request in runsession.get("runRequests", []):
        issues = request.get("issues", [])
        
        for issue in issues:
            matches = re.findall(r'`(.*?)`', issue.get("title", ""))
            keyword_counter.update(matches)
    
    most_common_resource = keyword_counter.most_common(1)
    
    return most_common_resource[0][0] if most_common_resource else "No keywords found"