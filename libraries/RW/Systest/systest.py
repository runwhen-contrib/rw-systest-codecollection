import re, logging, json, jmespath, requests, os, time
from RW import platform
from RW.Core import Core
from datetime import datetime
from robot.libraries.BuiltIn import BuiltIn
from robot.api.deco import keyword
from robot.api import logger as robot_logger

from collections import Counter

def get_visited_slx_and_tasks_from_runsession(runsession_data: dict):
    """
    Return a dict of:
        {
          "restart-loadbalancer": [
            "Restart Resource with Labels `app=frontend`",
            "Get Resource Logs with Labels `app=frontend`",
            "Get Current Resource State with Labels `app=frontend`"
          ],
          "pagerduty-webhook-handler": [
            "Run SLX Tasks with matching PagerDuty Webhook Service ID"
          ],
          ...
        }
    """
    slx_map = {}
    run_requests = runsession_data.get("runRequests", [])
    for rr in run_requests:
        slx_name = rr.get("slxName")
        # Sometimes 'resolvedTaskTitles' might be empty or a single string.
        # Usually you can split on '||'.
        resolved_titles = rr.get("resolvedTaskTitles", "")
        # Split by || if it’s a multi-task
        tasks = resolved_titles.split("||") if resolved_titles else []
        slx_map[slx_name] = tasks
    return slx_map

def get_workspace_slxs(
    rw_api_url: str = "https://papi.beta.runwhen.com/api/v3",
    api_token: platform.Secret = None,
    rw_workspace: str = "my-workspace"
) -> str:
    """
    Get all SLXs in a RunWhen workspace.

    :param rw_api_url: Base URL to the RunWhen API.
    :param api_token: A platform.Secret token object containing your bearer token.
    :param rw_workspace: The short name of the workspace.
    :return: A JSON string containing all SLXs (the raw response from the API).
    """
    url = f"{rw_api_url}/workspaces/{rw_workspace}/slxs"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token.value}"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        # Return the raw JSON string so you can parse it later or pass around as needed
        return response.text
    except (requests.ConnectTimeout, requests.ConnectionError, json.JSONDecodeError) as e:
        warning_log(
            f"Exception while fetching SLXs in workspace '{rw_workspace}': {e}",
            str(e),
            str(type(e))
        )
        platform_logger.exception(e)
        return ""

def get_slxs_with_tags_from_dict(
    tag_list: list,
    slx_data: str
) -> list:
    """
    Given a list of tags and a JSON string of SLX data,
    return all SLXs that match at least one of the specified tags.

    :param tag_list: A list of dicts, e.g. [{'name': 'tagkey', 'value': 'tagval'}, ...].
    :param slx_data: A JSON string containing existing SLX data, typically from get_workspace_slxs().
    :return: A list of SLX dicts that match any of the given tags.
    """
    if not slx_data:
        return []

    try:
        all_slxs = json.loads(slx_data)  # Parse the JSON content
    except json.JSONDecodeError as e:
        warning_log(f"JSON decode error in slx_data: {e}")
        platform_logger.exception(e)
        return []

    # If the API returns a dict with a "results" list, we assume the actual SLXs are in that list.
    results = all_slxs.get("results", [])

    matching_slxs = []
    for slx in results:
        # spec->tags is usually something like [{"name": "...", "value": "..."}].
        tags = slx.get("spec", {}).get("tags", [])
        # Check if any of the SLX's tags match any tag in tag_list.
        for tag in tags:
            if any(
                tag_item["name"] == tag["name"] and tag_item["value"] == tag["value"]
                for tag_item in tag_list
            ):
                matching_slxs.append(slx)
                break  # Stop checking other tags for this SLX; we already found a match.

    return matching_slxs

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

def get_workspace_config(
    rw_api_url: str = "https://papi.beta.runwhen.com/api/v3",
    api_token: platform.Secret = None,
    rw_workspace: str = "my-workspace",
): 
    """Get the workspace.yaml (in json format)

    Returns: 
        workspace.yaml contents in json format
    """
    headers = {
        "Content-Type": "application/json", 
        "Authorization": f"Bearer {api_token.value}"
        }
    url = f"{rw_api_url}/workspaces/{rw_workspace}/branches/main/workspace.yaml?format=json"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() 
        workspace = response.json()  
        workspace_config = workspace.get("asJson", [])

        print(workspace_config)
        return workspace_config
    except (
        requests.ConnectTimeout,
        requests.ConnectionError,
        json.JSONDecodeError,
    ) as e:
        warning_log(
            f"Exception while trying to get workspace configuration for workspace {rw_workspace}: {e}",
            str(e),
            str(type(e)),
        )
        platform_logger.exception(e)
        return []

def get_nearby_slxs(workspace_config: dict, slx_name: str) -> list:
    """
    Given a RunWhen workspace config (in dictionary form) and the short name
    of a specific SLX (e.g. "rc-ob-grnsucsc1c-redis-health-a7c33f4e"),
    return all SLXs in the same slxGroup.

    :param workspace_config: Dict representing workspace.yaml as JSON.
    :param slx_name: The SLX short name to look for.
    :return: A list of SLX short names in the same slxGroup as `slx_name`.
             If no group is found containing `slx_name`, returns an empty list.
    """
    # Navigate to the "slxGroups" array under "spec".
    slx_groups = workspace_config.get("spec", {}).get("slxGroups", [])

    for group in slx_groups:
        slxs = group.get("slxs", [])
        if slx_name in slxs:
            # Return the entire list of slxs in this group.
            return slxs

    # If we don't find the slx in any group, return an empty list.
    return []

def get_workspace_index_status(
    rw_api_url: str = "https://papi.beta.runwhen.com/api/v3",
    api_token: platform.Secret = None,
    rw_workspace: str = "my-workspace"
):
    """
    Fetch and parse the "index-status" endpoint for a given workspace,
    returning both the indexing status (as a string, e.g. "green" or "indexing")
    and the full JSON response as a dictionary.

    :param rw_api_url: Base URL to the RunWhen API (default: https://papi.beta.runwhen.com/api/v3).
    :param api_token: A platform.Secret token object containing your bearer token.
    :param rw_workspace: The short name of the workspace you want to query.
    :return: A tuple (status_value, response_dict) where:
             - status_value is a string (e.g., "green", "indexing", or None if unknown).
             - response_dict is the entire parsed JSON from the endpoint.
    """
    url = f"{rw_api_url}/workspaces/{rw_workspace}/index-status"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token.value}"
    }

    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()

    # Attempt to find the 'actual status' in multiple places:
    # 1) data["status"]["indexingStatus"], if "status" sub-dict exists
    # 2) data["indexingStatus"] at top-level, or None if not present
    # Note: I think some of this has to do with various index status return details 
    # between different platform releases. There could be many variations
    status_value = None
    if isinstance(data.get("status"), dict) and "indexingStatus" in data["status"]:
        status_value = data["status"]["indexingStatus"]
    elif "indexingStatus" in data:
        status_value = data["indexingStatus"]

    # Return both the extracted status and the full JSON
    return status_value, data

def perform_task_search(
    rw_api_url: str = "https://papi.beta.runwhen.com/api/v3",
    api_token: platform.Secret = None,
    rw_workspace: str = "my-workspace",
    persona: str = None,
    query: str = "",
    slx_scope: list = None
):
    """
    Perform a task search in the given workspace with the specified persona and query.
    
    :param rw_api_url: Base URL to the RunWhen API.
    :param api_token: A platform.Secret token containing your bearer token.
    :param rw_workspace: Short name of the workspace.
    :param persona: Persona shortname or None to default to <rw_workspace>--eager-edgar
    :param query: The search query (string).
    :param slx_scope: A list of slxShortNames to limit the search scope (optional).
    
    :return: Parsed JSON response from the task-search endpoint.
    """
    if slx_scope is None:
        slx_scope = []
    if persona is None:
        persona = f"{rw_workspace}--eager-edgar"

    # Construct the POST URL and payload
    url = f"{rw_api_url}/workspaces/{rw_workspace}/task-search"
    payload = {
        "query": [query],
        "scope": slx_scope,
        "persona": persona
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token.value}"
    }

    # Build a cURL command for troubleshooting
    # (masking or not masking token is up to you)
    payload_json_str = json.dumps(payload)
    curl_cmd = (
        f"curl -X POST '{url}' \\\n"
        f"  -H 'Content-Type: application/json' \\\n"
        f"  -H 'Authorization: Bearer $RW_API_TOKEN' \\\n"
        f"  -d '{payload_json_str}'"
    )

    # Log the HTTP request details
    robot_logger.info(f"Performing task search POST:\n  URL: {url}\n  Payload: {payload}", html=False)
    robot_logger.info(f"Equivalent cURL:\n{curl_cmd}", html=False)

    resp = requests.post(url, json=payload, headers=headers)
    resp.raise_for_status()

    # Return the parsed JSON
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
    Create a RunSession from tasks in `search_response`, filtering by `score_threshold`.

    This version detects which structure is present:
      - New structure (workspaceTask + extra fields).
      - Old structure (top-level fields like slxShortName, taskName, etc.).

    :param search_response: Dict containing the "tasks" array in either structure.
    :param api_token: platform.Secret (token for auth)
    :param rw_api_url: Base URL for RunWhen
    :param rw_workspace: Short name of the workspace
    :param persona_shortname: Persona for the runsession
    :param query: The user query that led to these tasks
    :param score_threshold: Minimum score for tasks to include
    :param curl_script_filename: Name of the .sh file to write the curl command
    :return: JSON response from creating the RunSession
    """
    url = f"{rw_api_url}/workspaces/{rw_workspace}/runsessions"

    tasks = search_response.get("tasks", [])
    if not tasks:
        robot_logger.info("No tasks found in search_response.")
        return {}

    # --------------------------------------------------
    # 1) Detect which structure is being used
    # --------------------------------------------------
    first_task = tasks[0]
    # If it has workspaceTask, call that the NEW structure
    if "workspaceTask" in first_task:
        robot_logger.info("Detected **new** structure (workspaceTask).")
        is_new_structure = True
    else:
        robot_logger.info("Detected **old** structure (top-level slxShortName/taskName).")
        is_new_structure = False

    run_requests_map = {}

    for t in tasks:
        # --------------------------------------------------
        # 2) Skip if score below threshold
        # --------------------------------------------------
        if t.get("score", 0) < score_threshold:
            continue

        # --------------------------------------------------
        # 3) Extract fields from the correct location
        # --------------------------------------------------
        if is_new_structure:
            # The "new" structure has everything in workspaceTask
            ws_task = t.get("workspaceTask", {})
            # The keys might be slxShortName/slxName, plus unresolvedTitle/resolvedTitle
            slx_candidate = ws_task.get("slxShortName") or ws_task.get("slxName")
            task_candidate = ws_task.get("unresolvedTitle") or ws_task.get("resolvedTitle")
        else:
            # The "old" structure uses top-level fields
            slx_candidate = t.get("slxShortName") or t.get("slxName")
            task_candidate = t.get("taskName") or t.get("resolvedTaskName")

        # --------------------------------------------------
        # 4) Prepend workspace prefix if missing
        # --------------------------------------------------
        if slx_candidate and not slx_candidate.startswith(f"{rw_workspace}--"):
            slx_candidate = f"{rw_workspace}--{slx_candidate}"

        # Skip if we don't have enough info
        if not slx_candidate or not task_candidate:
            continue

        # --------------------------------------------------
        # 5) Accumulate run requests by slx
        # --------------------------------------------------
        if slx_candidate not in run_requests_map:
            run_requests_map[slx_candidate] = {
                "slxName": slx_candidate,
                "taskTitles": [],
                "fromSearchQuery": query,
                "fromIssue": None
            }
        run_requests_map[slx_candidate]["taskTitles"].append(task_candidate)

    # --------------------------------------------------
    # 6) Build final payload
    # --------------------------------------------------
    run_requests = list(run_requests_map.values())
    session_body = {
        "generateName": "automated-systest",
        "runRequests": run_requests,
        "personaShortName": persona_shortname,
        "active": True
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_token.value}"
    }

    # --------------------------------------------------
    # 7) Debugging: Build cURL command
    # --------------------------------------------------
    payload_json_str = json.dumps(session_body)
    curl_cmd = (
        f"curl -X POST '{url}' \\\n"
        f"  -H 'Content-Type: application/json' \\\n"
        f"  -H 'Authorization: Bearer $RW_API_TOKEN' \\\n"
        f"  -d '{payload_json_str}'"
    )
    robot_logger.info(
        f"Performing runsession creation POST:\n  URL: {url}\n  Payload: {session_body}",
        html=False
    )
    robot_logger.info(f"Equivalent cURL:\n{curl_cmd}", html=False)

    # --------------------------------------------------
    # 8) POST & return the RunSession response
    # --------------------------------------------------
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