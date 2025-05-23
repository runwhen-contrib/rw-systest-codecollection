*** Settings ***
Metadata          Author           stewartshea
Documentation     Run e2e RunSession Tests against onbline boutique resources. Push a score between 0 and 1. 1 = healthy. If any tasks generate issues, this value is reduced. 
Metadata          Supports         Systest   RunWhen
Metadata          Display Name     E2E RunSession Systest

Suite Setup       Suite Initialization

Library           BuiltIn
Library           Collections
Library           RW.Core
Library           RW.platform
Library           OperatingSystem
Library           RW.CLI
Library           RW.Workspace
Library           RW.Systest

*** Keywords ***
Suite Initialization
    ${RW_API_TOKEN}=    RW.Core.Import Secret    RW_API_TOKEN
    ...    type=string
    ...    description=The RunWhen API Token
    ...    pattern=\w*
    ${PAPI_URL}=    RW.Core.Import User Variable    PAPI_URL
    ...    type=string
    ...    description=PAPI Endpoint URL
    ...    pattern=\w*
    ...    example=https://papi.beta.runwhen.com/api/v3
    ...    default=https://papi.beta.runwhen.com/api/v3
    ${WORKSPACE_NAME}=    RW.Core.Import User Variable    WORKSPACE_NAME
    ...    type=string
    ...    description=The name of the workspace to interact with
    ...    pattern=\w*
    ...    example=t-online-boutique
    ...    default=t-online-boutique
    ${ENVIRONMENT_NAME}=    RW.Core.Import User Variable    ENVIRONMENT_NAME
    ...    type=string
    ...    description=The short name of the environment (just to be used in the title)
    ...    pattern=\w*
    ...    example=test
    ...    default=test
    ${QUERY}=    RW.Core.Import User Variable    QUERY
    ...    type=string
    ...    description=The Query to send to the Engineering Assistant
    ...    pattern=\w*
    ...    example="`Cartservice` is down"
    ...    default="`Cartservice` is down"
    ${ASSISTANT_NAME}=    RW.Core.Import User Variable    ASSISTANT_NAME
    ...    type=string
    ...    description=The name of the engineering assistant to attach to the runsession
    ...    pattern=\w*
    ...    example=eager-edgar
    ...    default=eager-edgar
    ${STARTING_SCOPE_SLX_TAGS}=    RW.Core.Import User Variable    STARTING_SCOPE_SLX_TAGS
    ...    type=string
    ...    description=A list of tags used to select SLX scope for the RunSession
    ...    pattern=\w*
    ...    example=["systest:scope"]
    ...    default=["systest:scope"]
    ${VALIDATION_SLX_TAGS}=    RW.Core.Import User Variable    VALIDATION_SLX_TAGS
    ...    type=string
    ...    description=A list of tags used to validate that specific SLXs were visited in the RunSession.
    ...    pattern=\w*
    ...    example=["systest:validate"]
    ...    default=["systest:validate"]
    ${TASK_SEARCH_CONFIDENCE}=    RW.Core.Import User Variable    TASK_SEARCH_CONFIDENCE
    ...    type=string
    ...    description=The search confidence threshold for running tasks. Expects a value between 0 and 1, representing a percentage.
    ...    pattern=\w*
    ...    example=0.8
    ...    default=0.3
    ${RUNSESSION_POLL_INTERVAL}=    RW.Core.Import User Variable    RUNSESSION_POLL_INTERVAL
    ...    type=string
    ...    description=How often, in seconds, to query the RunSession for status updates. 
    ...    pattern=\w*
    ...    example=30
    ...    default=30
    ${RUNSESSION_MAX_TIMEOUT}=    RW.Core.Import User Variable    RUNSESSION_MAX_TIMEOUT
    ...    type=string
    ...    description=The RunSession polling timeout, in seconds.  
    ...    pattern=\w*
    ...    example=300
    ...    default=600
    Set Suite Variable    ${PAPI_URL}    ${PAPI_URL}
    Set Suite Variable    ${ENVIRONMENT_NAME}    ${ENVIRONMENT_NAME}
    Set Suite Variable    ${WORKSPACE_NAME}    ${WORKSPACE_NAME}
    Set Suite Variable    ${QUERY}    ${QUERY}
    Set Suite Variable    ${ASSISTANT_NAME}    ${ASSISTANT_NAME}
    Set Suite Variable    ${STARTING_SCOPE_SLX_TAGS}    ${STARTING_SCOPE_SLX_TAGS}
    Set Suite Variable    ${VALIDATION_SLX_TAGS}    ${VALIDATION_SLX_TAGS}
    Set Suite Variable    ${TASK_SEARCH_CONFIDENCE}    ${TASK_SEARCH_CONFIDENCE}
    Set Suite Variable    ${RUNSESSION_POLL_INTERVAL}    ${RUNSESSION_POLL_INTERVAL}
    Set Suite Variable    ${RUNSESSION_MAX_TIMEOUT}    ${RUNSESSION_MAX_TIMEOUT}


*** Tasks ***
Check Index Health for `${WORKSPACE_NAME}`
    [Documentation]    Checks the index status of the specified workspace 
    [Tags]             systest    index
    ${index_status}    ${response}=    RW.Systest.Get Workspace Index Status
    ...    rw_workspace=${WORKSPACE_NAME}
    ...    rw_api_url=${PAPI_URL}
    ...    api_token=${RW_API_TOKEN}
    IF    "${index_status}" == "complete" or "${index_status}" == "green"
        ${index_health_score}=    Set Variable    1
    ELSE
        ${index_health_score}=    Set Variable    0
    END   
    Set Global Variable    ${index_health_score}    ${index_health_score}

Validate E2E RunSession `${QUERY}` in `${WORKSPACE_NAME}` 
    [Documentation]    Validates a RunSession using the provided query in the specified workspace
    [Tags]             systest    runsession
    ${e2e_runsession_validation_score}=    Set Variable    0
    ${scope_slx_tags}=    Evaluate    [{'name': pair.split(':')[0], 'value': pair.split(':')[1]} for pair in ${STARTING_SCOPE_SLX_TAGS}]
    ${validation_slx_tags}=    Evaluate    [{'name': pair.split(':')[0], 'value': pair.split(':')[1]} for pair in ${VALIDATION_SLX_TAGS}]

    # Fetch the workspace SLX List
    ${workspace_slxs}=    RW.Systest.Get Workspace SLXs
    ...    rw_workspace=${WORKSPACE_NAME}
    ...    rw_api_url=${PAPI_URL}
    ...    api_token=${RW_API_TOKEN}

    # Get each list of SLXs that match the configured tags    
    ${matched_scope_slxs}=    RW.Systest.Get SLXs With Tags From Dict
    ...    tag_list=${scope_slx_tags}
    ...    slx_data=${workspace_slxs}
    ${matched_validation_slxs}=    RW.Systest.Get SLXs With Tags From Dict
    ...    tag_list=${validation_slx_tags}
    ...    slx_data=${workspace_slxs}

    ${slx_scope}=    Create List
    FOR  ${slx}  IN  @{matched_scope_slxs}
        Append To List    ${slx_scope}    ${slx["shortName"]}        
    END

    # A scope of a single SLX tends to present search issues. Add all SLXs from the same group if we only have one SLX.
    IF    len(@{slx_scope}) == 1
        ${config}=    RW.Systest.Get Workspace Config
        ...    rw_workspace=${WORKSPACE_NAME}
        ...    rw_api_url=${PAPI_URL}
        ...    api_token=${RW_API_TOKEN}

        ${nearby_slxs}=    RW.Systest.Get Nearby Slxs
        ...    workspace_config=${config}
        ...    slx_name=${slx_scope[0]}
        @{nearby_slx_list}    Convert To List    ${nearby_slxs}
        FOR    ${slx}    IN    @{nearby_slx_list}
            Append To List    ${slx_scope}    ${slx}
        END
    END

    ${validation_slxs}=    Create List
    FOR  ${slx}  IN  @{matched_validation_slxs}
        Append To List    ${validation_slxs}    ${slx["shortName"]}        
    END

    IF    ${slx_scope} == [] or ${validation_slxs} == []
        Log    "Skipping tests due to empty scope"
    ELSE
        # Get the list of suggested Tasks for the Runsession from the configured Query
        ${search_results}=    RW.Systest.Perform Task Search
        ...    rw_workspace=${WORKSPACE_NAME}
        ...    rw_api_url=${PAPI_URL}
        ...    api_token=${RW_API_TOKEN}
        ...    query=${QUERY}
        ...    slx_scope=${slx_scope}
        ...    persona=${WORKSPACE_NAME}--${ASSISTANT_NAME}

        IF    ${search_results} == {'tasks': [], 'links': [], 'owners': []} or ${search_results} == {'tasks': [], 'owners': []}            
            Log    "Skipping runsession test due to empty task results"
        ELSE
            # Start the RunSession
            ${runsession}=    RW.Systest.Create RunSession from Task Search
            ...    search_response=${search_results}
            ...    rw_workspace=${WORKSPACE_NAME}
            ...    rw_api_url=${PAPI_URL}
            ...    api_token=${RW_API_TOKEN}
            ...    query=${QUERY}
            ...    persona_shortname=${ASSISTANT_NAME}
            ...    score_threshold=${TASK_SEARCH_CONFIDENCE}

            ${runsession_status}=    RW.Systest.Wait for RunSession Tasks to Complete
            ...    rw_workspace=${WORKSPACE_NAME}
            ...    runsession_id=${runsession["id"]}
            ...    rw_api_url=${PAPI_URL}
            ...    api_token=${RW_API_TOKEN}
            ...    poll_interval=${RUNSESSION_POLL_INTERVAL}
            ...    max_wait_seconds=${RUNSESSION_MAX_TIMEOUT}

            # Validate that the desired SLXs were visited in the RunSession
            ${runsession_tasks}=    RW.Systest.Get Visited SLX and Tasks from RunSession
            ...    runsession_data=${runsession_status}

            ${overlap}    Create List
            FOR    ${item}    IN    @{validation_slxs}
                IF    '${item}' in @{runsession_tasks} or '${WORKSPACE_NAME}--${item}' in @{runsession_tasks}
                    Append To List    ${overlap}    ${item}
                END
            END

            ${runsession_url}=    Set Variable    ${PAPI_URL}/workspaces/${WORKSPACE_NAME}/runsessions/${runsession["id"]}

            IF    $overlap == []
                ${e2e_runsession_validation_score}=    Set Variable    0
            ELSE
                ${e2e_runsession_validation_score}=    Set Variable    1
            END
        END
    END
    Set Global Variable    ${e2e_runsession_validation_score}    ${e2e_runsession_validation_score}

Generate E2E RunSession Health Score
    ${score}=      Evaluate  (${index_health_score}+${e2e_runsession_validation_score})/2
    RW.Core.Push Metric    ${score}