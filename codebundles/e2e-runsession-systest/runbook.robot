*** Settings ***
Metadata          Author           stewartshea
Documentation     Run e2e RunSession Tests against onbline boutique resources 
Metadata          Supports         Systest   RunWhen
Metadata          Display Name     E2E RunSession Systest

Suite Setup       Suite Initialization

Library           BuiltIn
Library           RW.Core
Library           RW.platform
Library           OperatingSystem
Library           RW.CLI
Library           RW.Workspace
Library           RW.RunSession
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
    Set Suite Variable    ${RW_API_URL}    ${RW_API_URL}
    Set Suite Variable    ${ENVIRONMENT_NAME}    ${ENVIRONMENT_NAME}
    Set Suite Variable    ${WORKSPACE_NAME}    ${WORKSPACE_NAME}
    Set Suite Variable    ${QUERY}    ${QUERY}
    Set Suite Variable    ${ASSISTANT_NAME}    ${ASSISTANT_NAME}


    # # Get the current RunSession details from the workspace
    # ${CURRENT_SESSION}=      RW.Workspace.Import Runsession Details
    # # Check if there is a "related" RunSession to fetch instead
    # ${RELATED_RUNSESSION}=   RW.Workspace.Import Related RunSession Details    ${CURRENT_SESSION}

    # # Prefer the related session if it’s available, else fall back to the current one
    # IF    $RELATED_RUNSESSION != None
    #     Set Suite Variable    ${SESSION}   ${RELATED_RUNSESSION}
    # ELSE
    #     Set Suite Variable    ${SESSION}   ${CURRENT_SESSION}
    # END

*** Tasks ***
Run E2E RunSession `${QUERY}` in `${WORKSPACE_NAME}` 
    [Documentation]    Creates a RunSession in the validation workspace, 
    [Tags]             systest    runsession
    ${search_results}=    RW.RunSession.Perform Task Search
    ...    rw_workspace=${WORKSPACE_NAME}
    ...    rw_api_url=${RW_API_URL}
    ...    api_token=${RW_API_TOKEN}
    ...    query=${QUERY}
    ...    persona=${WORKSPACE_NAME}--${ASSISTANT_NAME}
    ${runsession}=    RW.RunSession.Create RunSession from Task Search
    ...    search_response=${search_results}
    ...    rw_workspace=${WORKSPACE_NAME}
    ...    rw_api_url=${RW_API_URL}
    ...    api_token=${RW_API_TOKEN}
    ...    query=${QUERY}
    ...    persona_shortname=${ASSISTANT_NAME}
    ...    score_threshold=0.3
    ${runsession_status}=    RW.RunSession.Wait for RunSession Tasks to Complete
    ...    rw_workspace=${WORKSPACE_NAME}
    ...    runsession_id=${runsession["id"]}
    ...    rw_api_url=${RW_API_URL}
    ...    api_token=${RW_API_TOKEN}
    ...    poll_interval=30
    ...    max_wait_seconds=600
    


# Send Slack Notification to Channel `${SLACK_CHANNEL}` from RunSession
#     [Documentation]    Sends a Slack message containing the summarized details of the RunSession.
#     ...                Intended to be used as a final task in a workflow.
#     [Tags]             slack    final    notification    runsession

#     # Convert the session JSON (string) to a Python dictionary/list
#     ${session_list}=        Evaluate    json.loads(r'''${SESSION}''')    json

#     # Gather important information about open issues in the RunSession
#     ${open_issue_count}=    RW.RunSession.Count Open Issues    ${SESSION}
#     ${open_issues}=         RW.RunSession.Get Open Issues      ${SESSION}
#     ${issue_table}=         RW.RunSession.Generate Open Issue Markdown Table    ${open_issues}
#     ${users}=               RW.RunSession.Summarize RunSession Users   ${SESSION}
#     ${runsession_url}=      RW.RunSession.Get RunSession URL    ${session_list["id"]}
#     ${key_resource}=        RW.RunSession.Get Most Referenced Resource    ${SESSION}
#     ${source}=              RW.RunSession.Get RunSession Source    ${session_list}
#     ${title}=               Set Variable    [RunWhen] ${open_issue_count} open issue(s) from ${source} related to `${key_resource}`


#     ${blocks}    ${attachments}=    Create RunSession Summary Payload
#     ...    title=${title}
#     ...    open_issue_count=${open_issue_count}
#     ...    users=${users}
#     ...    open_issues=${open_issues}
#     ...    runsession_url=${runsession_url}

#     IF    $open_issue_count > 0
#         RW.Slack.Send Slack Message    
#         ...    webhook_url=${SLACK_WEBHOOK}   
#         ...    blocks=${blocks}    
#         ...    attachments=${attachments}    
#         ...    channel=${SLACK_CHANNEL}
    
#         # TODO Add http rsp code and open issue if rsp fails
#         Add To Report      Slack Message Sent with Open Issues
#         Add To Report      Open Issues Found in [RunSession ${session_list["id"]}](${runsession_url})

#     ELSE
#         Add To Report      No Open Issues Found in [RunSession ${session_list["id"]}](${runsession_url})
#     END