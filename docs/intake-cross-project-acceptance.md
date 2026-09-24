---
cbd:
  target: apps/api/plane/utils/intake.py
  kind: file
---

# Cross-project intake acceptance

An administrator accepting an Intake work item can select any project in the
same workspace where they have work-item creation permission. Selecting the
current project preserves Plane's original acceptance behavior. Selecting a
different project keeps the work item's UUID but gives it a new destination
project key and moves it to that project's default non-triage state.

The Intake record remains attached to the source project. This preserves the
source Intake's accepted-item history while its nested work-item representation
points to the destination project.

Project-specific values are not copied blindly. Source labels, cycle and module
memberships, parent/child links, issue type, estimate, workflow-reversal records,
and GitHub synchronization are cleared. Assignees are retained only when they
are active members of the destination. Portable content such as comments,
attachments, links, reactions, and version history keeps the same work-item UUID
and is re-scoped to the destination project.

The API accepts `target_project_id` alongside `status: 1` on the existing Intake
work-item update endpoint. The move and acceptance run in one database
transaction. The target must belong to the same workspace, have a default
non-triage state, and grant the actor create permission. Calls without
`target_project_id` remain backward-compatible and accept into the source
project.
