# e2e-runsession-systest
This codebundle performs a `task-search` from a configured query, and then creates a runsession from the resulting tasks. The idea here is that this can be used for consistent validation of our "Cart Service is Down" demo / flow, but can also easily be re-configured for other tests. It will use SLX tags to help determine which SLXs should be passed in the original RunSession `scope`, as well as which SLXs should be visited in the RunSession. It does *not* have the ability to verify the output of the specified verified tasks, as that would make it unable to be reused for other use cases, thought we could consider an extension. 

For the `Cart Service is Down` validation flow; 
- Each of our environments has an "Online Boutique" Validation Workspace (e.g. `t-t-z-online-boutique` in the Test environment)
- The `Online Boutique Namespace Health` SLX is tagged with `systest:scope`, and is included in the original `task-search` query
- A `task-seach` is perfomed with the configured query and the SLX scope, returning a list of suggested tasks
- A runsession is started with the resulting tasks that are above the configured search confidence threshold
- The runsession is watched for changes to the runrequest length - as it stablizes out for a period of time, we assume is is "complete"
- We analyze all SLXs / Tasks in the RunSession and check if the SLX that was tagged with `systest:validate` exists in the RunSession (if it exists, we assume success)

Issues can be raised along the way for unhealthy indexes, no task results, and so on. Additional error checking and issue generation can be added on. 

> TODO: Validate across the different index and runsession json payloads, as BETA appeared slightly different than newer environments. Differents in the index-status response were observed during authoring, along with differences in whether slxName or slxShortName were being passed to the runsession (as well as a couple other response nuances)