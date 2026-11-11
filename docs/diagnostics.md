# Diagnostics

From the Worker host CMD, after the normal Docker build:

```cmd
tools\diagnostics\diag.cmd health
tools\diagnostics\diag.cmd recent
tools\diagnostics\diag.cmd run RUN_ID
tools\diagnostics\diag.cmd run RUN_ID --json
tools\diagnostics\diag.cmd logs RUN_ID
tools\diagnostics\diag.cmd logs RUN_ID --errors
tools\diagnostics\diag.cmd logs RUN_ID --stage enrichment
tools\diagnostics\diag.cmd hh
tools\diagnostics\diag.cmd config
```

The toolkit is read-only. It redacts query strings, credential values, cookies, headers, HTML and vacancy descriptions. `run` combines the PipelineRun lifecycle snapshot with persisted preliminary outcomes, the durable backlog and safe failure samples when the Orchestrator is available. Missing historical or Worker-memory data is reported as unavailable rather than inferred. `logs` filters Worker container output by `pipeline_run_id`; it does not print secrets or request payloads.
