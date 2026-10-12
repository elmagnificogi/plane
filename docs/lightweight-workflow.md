---
cbd:
  target: apps/api/plane/utils/workflow.py
  kind: file
---

# Lightweight project workflow

This extension adds an opt-in, fixed business workflow without changing Plane's
existing project, work-item, state, label, or import schemas. A newly created
project receives the status catalog below as its project states. Enabling the
workflow is still a separate step. Existing projects are not rewritten.

## Compatibility contract

- Configuration and business-role assignments live in additive tables.
- Bootstrap reuses matching project states and labels, and only creates missing
  records. It never renames or deletes imported Plane data. Earlier English
  names (`Backlog`, `Todo`, `In Progress`, `Done`, `Cancelled`) still match the
  current catalog and are left in place.
- Business roles are independent of Plane's Admin/Member/Guest access roles.
- Disabling the workflow immediately restores Plane's native unrestricted state
  editing while retaining the configuration for later reuse.
- The settings UI uses Plane's normal i18n loading path. English, Simplified
  Chinese, and Traditional Chinese have native copy for this extension; Plane's
  other supported locales use explicit English fallback copy, so translation
  keys are never exposed in the interface.

## Fixed states

New projects are created with `需求完善` (the default), `待做`, `开发中`,
`开发完成`, `测试中`, `测试打回`, `延期中`, `挂起`, `完成`, `延期完成`, and
`取消`, plus Plane's hidden `Triage` state. `开发完成` is the single name for
the state previously called `等待测试` or `等待测试/开发完成`. Bootstrap still
matches those older names and leaves them in place. `完成` is green (`#46A758`) and
`延期完成` is teal (`#0E7490`), so the two completed states are not the same green.
`延期中` and `挂起` belong to Plane's Cancelled group and are listed after `取消`.
They stay separate workflow states from `取消`.

The main flow is `需求完善 -> 待做 -> 开发中 -> 开发完成 -> 测试中 -> 完成`.
Testing can reject work to `测试打回`, which returns to `开发中`. The permitted
main-flow edges and the role that owns each target are:

- Product: `需求完善 -> 待做`, `测试中 -> 完成`, and `开发中`, `开发完成`, or
  `测试中 -> 取消`.
- Developer: `待做 -> 开发中`, `测试打回 -> 开发中`, and `开发中 -> 开发完成`.
- Tester: `开发完成 -> 测试中` and `测试中 -> 测试打回`.
- Project manager: workflow super-role. It may move an item from its current
  state to any other configured business-workflow state. Normal completion
  guards, such as unfinished blocking children, still apply.

`延期中` remains an additive state because it appears in the source status
catalog. Regular roles do not receive an inferred edge to it; the project
manager can select it through the super-role override.

Defects use `测试打回 -> 开发中`. From `开发中`, tester may select `完成`,
product may select `取消`, and project manager may select `挂起` or `延期完成`.
The specification draws no outbound edge from `挂起`, so none is invented for
regular roles. The project-manager super-role can still move suspended work. A
work item is treated as a defect when it has the configured defect label,
whether it is a main item or sub-item.

Closing a main item is blocked while a child item carrying the configured
blocking label is not completed or cancelled.

When a project manager moves a work item to 完成 or 延期完成, and the
existing blocking-child guard allows that move, the client asks whether to
mark eligible descendants 完成 as well. Declining or dismissing the prompt
completes only the selected item. Either answer leaves the side peek open, and
leaves the expanded or collapsed state of work-item rows and sections unchanged. Confirming walks the same-project subtree
and sets each eligible item to 完成. 取消, 延期中, 延期完成, and 挂起 items stop their
branch. An item with the blocking label also stops its branch. An item already
in 完成 stays there, and the walk continues through it. Related work items are
not part of the walk. A descendant that still has its own unfinished blocking
child is left unchanged and reported; siblings that already moved to 完成 stay
完成. Other roles never see the prompt.

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

The source explicitly says a defect reaches `完成` after regression succeeds but
does not repeat the actor in that sentence. Defect completion is assigned to the
tester because the action is the tester's regression result. No transition edge
is added where the source neither names one nor draws one.
