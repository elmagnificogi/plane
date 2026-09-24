---
cbd:
  target: apps/api/plane/app/views/issue/relation.py
  kind: file
---

# Cross-project work-item relations

Cross-project test tracking uses Plane's existing work-item relations and its existing "current project / workspace" search toggle. It does not add a project allowlist, a special validation relation, or a second project-settings workflow.

- Workspace search discovers work items from projects where the current user is an active member, matching Plane's native behavior.
- Relation creation remains workspace-scoped and supports many business work items relating to the same test ticket.
- Relation responses include the target project identifier and current state summary so the source project can show completion progress without loading editable target-project controls.
- A cross-project row in the source work item does not expose state, priority, assignee, edit, or delete-work-item actions. Removing the relation itself remains available.
- Direct access to or modification of the target work item still follows the target project's normal membership and permissions.
- Closing the source work item remains a manual decision; relations do not add workflow gates or automatic state transitions.
