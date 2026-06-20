# Task Specification
Build an event-driven automation using the Devin API (docs.devin.ai). 

# Objectives 
- Leverage Devin as core agentic backbone
- Provide clear observability (logs, metrics, tracing)
    - Do not overengineer; since Devin sessions are long-running async workflows, create an append-only log & a simple state table both keyed on a session ID
    - Maintain structured logs with every line tagged with session_id from JSON to stdout
    - Metrics: autonomy rate (% finished with human_msgs=0), outcome rate (status_detail=finished→success; waiting_for_user/approval→blocked; error/out_of_credits/usage_limit_exceeded→failed), updated_at -> created_at cycle time, ACUs used, failure breakdown 

# Overview
- Repository: github.com/apache/superset; identify and create issues in local fork (in root); focus on vulnerabilities, dependencies, code quality
- Use Devin to triage, research, and fix issues
- Focus on verifiable outcomes; always provide evidence (logs, diffs, test results)

# Deliverables
- Build automation that remediates issues that you created
    - MVP: start with dependency/audit findings running pip-audit and/or pnpm audit against Superset fork; for each deduped finding, create a GitHub issue on our fork (NOT the upstream); For each issue, create one Devin session with: issue URL, repo URL, branhc naming convention, requested fix, requested tests, expected PR output
# Requirements:
     - Be triggered by events (ex: webhook, repo activity, ticket creation, scan results, scheduled/periodic trigger)
     - Programatically initiate and manage Devin sessions
         - Architecture: scheduled dependency scan on the Superset fork -> open Github issues -> orchestrator fans out <=3 concurrent devin sessions that research + fix + PR on fork with max_acu_limit and indempotent dedup; each PR is gated with a targeted pytest + lint + SQlite state table + JSON logs -> metrics -> POST /runs + GET /runs/{id}
         - Spawn parallel research agents to investigate multiple issues simultaneously
     - Suggested focus areas:
        - Performance optimization (e.g., slow query, memory leak)
        - Security vulnerability (e.g., SQL injection, XSS)
        - Code quality improvement (e.g., refactoring, documentation)
        - Dependency update (e.g., CVE fix, version bump)
        - Use scanner (pip-audit/pnpm audit) to produce issues (low-hanging fruit)
     - Produce observable outputs/artificats for technical audience (PRs, issues, reports, status updates)
     - Docker compose for local deployment
     - Include a `structured_output_schema` requiring Devin to return:
        - Issue URL, summary, branch, pr_url, files_changed, tests_run, teset_result, evidence, needs_human
- Observability:
    - Minimum: status of active and completed tasks, success/failure signals, throughput or progerss tracking
- Interface:
    - Simple endpoint to start/monitor progress
    - Create a codegraph to explain the architecture and flow of the application as well as where changes were made
    - Simple interface to view metrics and logs
        - Metrics: status of active and completed tasks, success/failure signals, throughput or progerss tracking
        - Logs: structured logs with every line tagged with session_id from JSON to stdout
        - Tracing: maintain structured logs with every line tagged with session_id from JSON to stdout
        - Include links to the GitHub issues and PRs created (on the FORK, not the upstream)
        - Use frontend design skill; include visualizations and clear navigation; should be an Overview, Issues, Observability, and Codegraph page
        - Add a button to trigger a new run; include a button to refresh the page; include option to merge PRs; include option to delete runs; add search bar to find runs by session_id or issue_id or name; add filters to filter runs by status, date, etc.; also add a codegraph visualization to show the architecture and flow of the application per-run and show a diff of changes made

# Ontology (post-MVP)
- Include traces of all actions taken by Devin for each run as well as whether a human accepted the changes
- Add functionality to replay runs and compare different runs
- Add functionality to generate reports and summaries of runs

# Advanced
- Since Devin has collaborative sandboxes, allow multiple users to work on the same run simultaneously and coordinate their changes; a human reviwer can open a Devin session to inspect the shell history, review the diff in the IDE, run commands in teh same env, complete auth/manual steps, resume Devin with a structured message
scanner -> ticket -> Devin session -> live sandbox -> PR -> evidence -> optional human rescue -> resumed Devin
- On superset, create a dogfood interface that reviewers can run from zero against real scan/run data; do not seed mock issues into the dashboard
