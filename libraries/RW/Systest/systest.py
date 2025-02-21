import re, logging, json, jmespath, requests, os
from datetime import datetime
from robot.libraries.BuiltIn import BuiltIn
from collections import Counter

def create_new_runsession_from_query(workspace: str, query: str, rw_api_url: str, api_token: platform.Secret = None, assistant_name: str) -> dict:
    """
    Create a new RunSession via an API call.

    :param workspace_id: The ID of the workspace where the new RunSession will be created.
    :param payload: A dictionary containing the data for the new RunSession.
    :return: A dictionary with the newly created RunSession information if successful.
    """
    if not rw_api_url:
        raise EnvironmentError("RW_API_URL environment variable not set.")
    
    # Construct the payload
    payload={
        personaShortName={assistant_name},
        
    }
    # Construct the URL for creating a runsession
    endpoint = f"{rw_api_url}/workspaces/{workspace_id}/runsessions"

    # In some environments, you might need a token or API key
    # (e.g., Bearer token, Basic Auth, etc.). Adjust as needed:
    rw_api_key = os.getenv("RW_API_KEY")
    if not rw_api_key:
        raise EnvironmentError("RW_API_KEY environment variable not set.")

    headers = {
        "Authorization": f"Bearer {rw_api_key}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        # If the API returns JSON data for the new RunSession, parse and return it
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Failed to create new RunSession: {e}")
        raise e