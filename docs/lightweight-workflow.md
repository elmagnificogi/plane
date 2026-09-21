---
cbd:
  target: apps/api/plane/utils/workflow.py
  kind: file
---

# Lightweight project workflow

This extension adds an opt-in, fixed business workflow without changing Plane's
existing project, work-item, state, label, or import schemas. Existing projects
remain unaffected until an administrator bootstraps and enables the workflow.

## Compatibility contract

- Configuration and business-role assignments live in additive tables.
- Bootstrap reuses matching project states and labels, and only creates missing
  records. It never renames or deletes imported Plane data.
- Business roles are independent of Plane's Admin/Member/Guest access roles.
- Disabling the workflow immediately restores Plane's native unrestricted state
  editing while retaining the configuration for later reuse.
- The settings UI uses Plane's normal i18n loading path. English, Simplified
  Chinese, and Traditional Chinese have native copy for this extension; Plane's
  other supported locales use explicit English fallback copy, so translation
  keys are never exposed in the interface.

## Fixed states

The main flow is `Backlog -> Todo -> In Progress -> Waiting for Test -> Testing
-> Done`. Testing can reject work to `Test Rejected`, which returns to `In
Progress`. The permitted main-flow edges and the role that owns each target are:

- Product: `Backlog -> Todo`, `Testing -> Done`, and `In Progress`, `Waiting for
Test`, or `Testing -> Cancelled`.
- Developer: `Todo -> In Progress`, `Test Rejected -> In Progress`, and `In
Progress -> Waiting for Test`.
- Tester: `Waiting for Test -> Testing` and `Testing -> Test Rejected`.
- Project manager: workflow super-role. It may move an item from its current
  state to any other configured business-workflow state. Normal completion
  guards, such as unfinished blocking children, still apply.

`Delayed` remains an additive state because it appears in the source status
catalog. Regular roles do not receive an inferred edge to it; the project
manager can select it through the super-role override.

Defects use `Test Rejected -> In Progress`. From `In Progress`, tester may select
`Done`, product may select `Cancelled`, and project manager may select
`Suspended` or `Delayed Done`. The specification draws no outbound edge from
`Suspended`, so none is invented for regular roles. The project-manager
super-role can still move suspended work. A work item is treated as a defect
when it has the configured defect label, whether it is a main item or sub-item.

Closing a main item is blocked while a child item carrying the configured
blocking label is not completed or cancelled.

The actor who performed the latest accepted state transition may reverse that
single transition back to its immediately previous state. The reversal is only
available while the work item is still in the state produced by that transition;
another actor's later transition supersedes it. Reversals are recorded
synchronously so an immediate correction does not depend on asynchronous Plane
activity processing.

The work-item state picker consumes the per-issue available-transitions API.
When the workflow is enabled it keeps the current state visible and hides every
target state the current actor cannot select. Projects without an enabled
workflow continue to expose Plane's complete state list.

The picker prefetches an issue's available transitions when its control receives
pointer hover or keyboard focus, deduplicates an in-flight request, and reuses
the result while the issue remains in the same state. While the first request is
pending, repeated clicks cannot immediately close the just-opened picker; the
menu remains open with a loading indicator until the permitted states arrive.
A short open debounce also prevents a double-click from being interpreted as
an immediate close after a prefetched response has already arrived.

## Webhook contract

Every accepted state transition continues to produce Plane's normal `issue`
webhook and additionally produces `issue.workflow_transition`. Its activity
contains the semantic state keys, concrete state records, workflow track,
required role, actor, schema version, and an `is_reversal` marker. Failed or
rejected transitions emit neither transition event.

For single-machine verification without Docker, use
`DJANGO_SETTINGS_MODULE=plane.settings.workflow_local`. This swaps Redis,
RabbitMQ, and S3 for in-process/local development backends and executes Celery
tasks eagerly. It also disables the Django debug toolbar, reduces per-request
console logging, and enables persistent database connections so Plane's parallel
workspace bootstrap requests remain responsive on Windows. Serve it through an
ASGI worker such as Uvicorn rather than Django's development server. Install
`apps/api/requirements/local.txt` so the in-memory Redis adapter is available.
It must not be used for a production or multi-process install. The local settings
trust the development frontend at `127.0.0.1:3000`, `localhost:3000`, and the
origin configured through `APP_BASE_URL` for credentialed CORS and
CSRF-protected sign-in. Set `APP_BASE_URL` to the machine's LAN URL and bind the
ASGI server to a LAN interface when another device needs to access the local
verification deployment.

## Deliberate assumption

The source explicitly says a defect reaches `Done` after regression succeeds but
does not repeat the actor in that sentence. Defect completion is assigned to the
tester because the action is the tester's regression result. No transition edge
is added where the source neither names one nor draws one.
