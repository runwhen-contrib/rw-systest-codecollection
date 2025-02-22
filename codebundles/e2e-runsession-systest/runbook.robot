*** Settings ***
Metadata          Author           stewartshea
Documentation     Run e2e RunSession Tests against onbline boutique resources 
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
    ${RW_API_URL}=    RW.Core.Import User Variable    RW_API_URL
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
    ...    example=Cartservice is down
    ...    default=Cartservice is down
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
    Set Suite Variable    ${RW_API_URL}    ${RW_API_URL}
    Set Suite Variable    ${ENVIRONMENT_NAME}    ${ENVIRONMENT_NAME}
    Set Suite Variable    ${WORKSPACE_NAME}    ${WORKSPACE_NAME}
    Set Suite Variable    ${QUERY}    ${QUERY}
    Set Suite Variable    ${ASSISTANT_NAME}    ${ASSISTANT_NAME}
    Set Suite Variable    ${STARTING_SCOPE_SLX_TAGS}    ${STARTING_SCOPE_SLX_TAGS}
    Set Suite Variable    ${VALIDATION_SLX_TAGS}    ${VALIDATION_SLX_TAGS}

*** Tasks ***

Check Index Health for `${WORKSPACE_NAME}`
    [Documentation]    Checks the index status of the specified workspace 
    [Tags]             systest    index
    ${index}=    RW.Systest.Get Workspace Index Status
    ...    rw_workspace=${WORKSPACE_NAME}
    ...    rw_api_url=${RW_API_URL}
    ...    api_token=${RW_API_TOKEN}
    Add Pre To Report    ${index}
    IF    "${index["status"]["indexingStatus"]}" != "green"
        RW.Core.Add Issue    
        ...    severity=2
        ...    next_steps=Review the index health from the json
        ...    actual=Index health is... not... green
        ...    expected=Workspace index health should be green 
        ...    title=Index status is unhealthy in `${WORKSPACE_NAME}` 
        ...    reproduce_hint=cURL the index-status endpoint
        ...    details=See the report details for index status. 
    END   

Validate E2E RunSession `${QUERY}` in `${WORKSPACE_NAME}` 
    [Documentation]    Validates a RunSession using the provided query in the specified workspace
    [Tags]             systest    runsession
    ${scope_slx_tags}=    Evaluate    [{'name': pair.split(':')[0], 'value': pair.split(':')[1]} for pair in ${STARTING_SCOPE_SLX_TAGS}]
    ${validation_slx_tags}=    Evaluate    [{'name': pair.split(':')[0], 'value': pair.split(':')[1]} for pair in ${VALIDATION_SLX_TAGS}]

    # Fetch the workspace SLX List
    ${workspace_slxs}=    RW.Systest.Get Workspace SLXs
    ...    rw_workspace=${WORKSPACE_NAME}
    ...    rw_api_url=${RW_API_URL}
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
        Append To List    ${slx_scope}    ${slx["name"]}        
    END
    Add To Report    Scoping Test to the following SLXs: ${slx_scope}
    
    ${validation_slxs}=    Create List
    FOR  ${slx}  IN  @{matched_validation_slxs}
        Append To List    ${validation_slxs}    ${slx["name"]}        
    END
    Add To Report    Validation will check that the following SLXs are in the RunSession: ${validation_slxs}


    # Get the list of suggested Tasks for the Runsession from the configured Query
    ${search_results}=    RW.Systest.Perform Task Search
    ...    rw_workspace=${WORKSPACE_NAME}
    ...    rw_api_url=${RW_API_URL}
    ...    api_token=${RW_API_TOKEN}
    ...    query=${QUERY}
    ...    slx_scope=${slx_scope}
    ...    persona=${WORKSPACE_NAME}--${ASSISTANT_NAME}
    Add Json To Report    ${search_results}

    IF    "$search_results" == "{'tasks': [], 'links': [], 'owners': []}"
        RW.Core.Add Issue    
        ...    severity=1
        ...    next_steps=Check Index Health for `${WORKSPACE_NAME}`
        ...    actual=Search returned no results
        ...    expected=Search should return at least one or more sets of tasks 
        ...    title=Search returned no results for `${QUERY}` in `${WORKSPACE_NAME}` 
        ...    reproduce_hint=Search `${QUERY}` in `${WORKSPACE_NAME}` in `${ENVIRONMENT_NAME}`
        ...    details=Search results are empty. Scoped search to ${slx_scope}
    END

    # Start the RunSession
    ${runsession}=    RW.Systest.Create RunSession from Task Search
    ...    search_response=${search_results}
    ...    rw_workspace=${WORKSPACE_NAME}
    ...    rw_api_url=${RW_API_URL}
    ...    api_token=${RW_API_TOKEN}
    ...    query=${QUERY}
    ...    persona_shortname=${ASSISTANT_NAME}
    ...    score_threshold=0.3

    ${runsession_status}=    RW.Systest.Wait for RunSession Tasks to Complete
    ...    rw_workspace=${WORKSPACE_NAME}
    ...    runsession_id=${runsession["id"]}
    ...    rw_api_url=${RW_API_URL}
    ...    api_token=${RW_API_TOKEN}
    ...    poll_interval=3
    ...    max_wait_seconds=10
    Add Json To Report    ${runsession_status}

    # Validate that the desired SLXs were visited in the RunSession
    ${runsession_tasks}=    RW.Systest.Get Visited SLX and Tasks from RunSession
    ...    runsession_data=${runsession_status}
    Add Pre To Report    SLXs Visited in this Runsession:\n${runsession_tasks}

    ${overlap}    Create List
    FOR    ${item}    IN    @{validation_slxs}
        IF    '$item' in '@runsession_tasks'
            Append To List    ${overlap}    ${item}
        END
    END

    Add Pre To Report     Desried SLXs visited in RunSession: ${overlap}
    ${runsession_url}=    Set Variable    ${RW_API_URL}/workspaces/${WORKSPACE_NAME}/runsessions/${runsession["id"]}
    Add Url To Report    ${runsession_url}

    IF    $overlap == []
        RW.Core.Add Issue    
        ...    severity=2
        ...    next_steps=Review [RunSession URL](${runsession_url})
        ...    actual=Desired Validation SLX not visited in RunSession
        ...    expected=Validation SLXs should be visited in RunSession
        ...    title=RunSession Validation Failed for `${QUERY}` in `${WORKSPACE_NAME}`
        ...    reproduce_hint=Search `${QUERY}` in `${WORKSPACE_NAME}` in `${ENVIRONMENT_NAME}`
        ...    details=All tasks visited in RunSession:\n${runsession_tasks}
    END