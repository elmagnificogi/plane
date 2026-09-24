# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Contract tests for accepting intake work items into another project."""

from uuid import uuid4

import pytest
from rest_framework import status

from plane.db.models import (
    Cycle,
    CycleIssue,
    Intake,
    IntakeIssue,
    Issue,
    IssueAssignee,
    IssueComment,
    IssueLabel,
    IssueSequence,
    Label,
    Module,
    ModuleIssue,
    Project,
    ProjectMember,
    State,
    User,
    WorkspaceMember,
)


@pytest.fixture
def intake_projects(db, workspace, create_user):
    source_project = Project.objects.create(
        name="Intake Source",
        identifier="SRC",
        workspace=workspace,
        created_by=create_user,
    )
    target_project = Project.objects.create(
        name="Delivery Target",
        identifier="DST",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(project=source_project, member=create_user, role=20, is_active=True)
    ProjectMember.objects.create(project=target_project, member=create_user, role=20, is_active=True)

    source_default_state = State.objects.create(
        name="Source Todo",
        project=source_project,
        workspace=workspace,
        group="backlog",
        default=True,
    )
    source_triage_state = State.objects.create(
        name="Triage",
        project=source_project,
        workspace=workspace,
        group="triage",
        is_triage=True,
        default=False,
    )
    target_default_state = State.objects.create(
        name="Target Todo",
        project=target_project,
        workspace=workspace,
        group="backlog",
        default=True,
    )
    intake = Intake.objects.create(
        name="Source Intake",
        project=source_project,
        workspace=workspace,
        is_default=True,
    )
    issue = Issue.objects.create(
        name="Move me",
        project=source_project,
        workspace=workspace,
        state=source_triage_state,
        created_by=create_user,
    )
    intake_issue = IntakeIssue.objects.create(
        intake=intake,
        issue=issue,
        project=source_project,
        workspace=workspace,
        created_by=create_user,
    )

    return {
        "source": source_project,
        "target": target_project,
        "source_default_state": source_default_state,
        "target_default_state": target_default_state,
        "issue": issue,
        "intake_issue": intake_issue,
    }


@pytest.fixture(autouse=True)
def disable_intake_background_tasks(monkeypatch):
    monkeypatch.setattr("plane.app.views.intake.base.issue_activity.delay", lambda **kwargs: None)
    monkeypatch.setattr("plane.app.views.intake.base.issue_description_version_task.delay", lambda **kwargs: None)


@pytest.mark.contract
@pytest.mark.django_db
class TestIntakeCrossProjectAcceptance:
    @staticmethod
    def get_url(workspace_slug, project_id, issue_id):
        return f"/api/workspaces/{workspace_slug}/projects/{project_id}/inbox-issues/{issue_id}/"

    def test_accept_moves_work_item_and_clears_source_project_properties(
        self,
        session_client,
        workspace,
        create_user,
        intake_projects,
    ):
        source_project = intake_projects["source"]
        target_project = intake_projects["target"]
        issue = intake_projects["issue"]
        intake_issue = intake_projects["intake_issue"]

        # Reserve the first destination sequence so the moved work item must
        # receive a newly allocated destination key.
        Issue.objects.create(
            name="Existing target work item",
            project=target_project,
            workspace=workspace,
            state=intake_projects["target_default_state"],
            created_by=create_user,
        )

        source_label = Label.objects.create(
            name="Source only",
            color="#ff0000",
            project=source_project,
            workspace=workspace,
        )
        IssueLabel.objects.create(issue=issue, label=source_label, project=source_project, workspace=workspace)
        source_cycle = Cycle.objects.create(
            name="Source cycle",
            project=source_project,
            workspace=workspace,
            owned_by=create_user,
        )
        CycleIssue.objects.create(issue=issue, cycle=source_cycle, project=source_project, workspace=workspace)
        source_module = Module.objects.create(
            name="Source module",
            project=source_project,
            workspace=workspace,
            lead=create_user,
        )
        ModuleIssue.objects.create(issue=issue, module=source_module, project=source_project, workspace=workspace)

        IssueAssignee.objects.create(
            issue=issue,
            assignee=create_user,
            project=source_project,
            workspace=workspace,
        )
        outsider = User.objects.create(
            email=f"outsider-{uuid4().hex[:8]}@plane.so",
            username=f"outsider_{uuid4().hex[:8]}",
        )
        IssueAssignee.objects.create(
            issue=issue,
            assignee=outsider,
            project=source_project,
            workspace=workspace,
        )
        comment = IssueComment.objects.create(
            issue=issue,
            actor=create_user,
            comment_html="<p>Keep this comment</p>",
            project=source_project,
            workspace=workspace,
        )

        response = session_client.patch(
            self.get_url(workspace.slug, source_project.id, issue.id),
            {
                "status": 1,
                "target_project_id": str(target_project.id),
                "issue": {"name": "Moved and accepted"},
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK, response.data
        issue.refresh_from_db()
        intake_issue.refresh_from_db()
        comment.refresh_from_db()

        assert issue.project_id == target_project.id, response.data
        assert issue.state_id == intake_projects["target_default_state"].id
        assert issue.sequence_id == 2
        assert issue.name == "Moved and accepted"
        assert intake_issue.project_id == source_project.id
        assert intake_issue.status == 1
        assert response.data["issue"]["project_id"] == target_project.id

        assert not IssueLabel.objects.filter(issue=issue).exists()
        assert not CycleIssue.objects.filter(issue=issue).exists()
        assert not ModuleIssue.objects.filter(issue=issue).exists()
        assert not IssueAssignee.objects.filter(issue=issue, assignee=outsider).exists()
        assert IssueAssignee.objects.filter(
            issue=issue,
            assignee=create_user,
            project=target_project,
        ).exists()
        assert comment.project_id == target_project.id
        assert IssueSequence.objects.filter(issue=issue, project=target_project, sequence=2).exists()
        assert not IssueSequence.objects.filter(issue=issue, project=source_project).exists()

    def test_accept_without_target_keeps_original_project(
        self,
        session_client,
        workspace,
        intake_projects,
    ):
        source_project = intake_projects["source"]
        issue = intake_projects["issue"]
        intake_issue = intake_projects["intake_issue"]
        original_sequence = issue.sequence_id

        response = session_client.patch(
            self.get_url(workspace.slug, source_project.id, issue.id),
            {"status": 1},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK, response.data
        issue.refresh_from_db()
        intake_issue.refresh_from_db()
        assert issue.project_id == source_project.id
        assert issue.state_id == intake_projects["source_default_state"].id
        assert issue.sequence_id == original_sequence
        assert intake_issue.status == 1

    def test_accept_rejects_target_without_create_permission(
        self,
        session_client,
        workspace,
        create_user,
        intake_projects,
    ):
        source_project = intake_projects["source"]
        target_project = intake_projects["target"]
        issue = intake_projects["issue"]
        intake_issue = intake_projects["intake_issue"]
        ProjectMember.objects.filter(project=target_project, member=create_user).update(role=5)
        WorkspaceMember.objects.filter(workspace=workspace, member=create_user).update(role=15)

        response = session_client.patch(
            self.get_url(workspace.slug, source_project.id, issue.id),
            {"status": 1, "target_project_id": str(target_project.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN, response.data
        issue.refresh_from_db()
        intake_issue.refresh_from_db()
        assert issue.project_id == source_project.id
        assert intake_issue.status == -2

    def test_target_project_requires_accept_status(
        self,
        session_client,
        workspace,
        intake_projects,
    ):
        source_project = intake_projects["source"]
        target_project = intake_projects["target"]
        issue = intake_projects["issue"]
        intake_issue = intake_projects["intake_issue"]

        response = session_client.patch(
            self.get_url(workspace.slug, source_project.id, issue.id),
            {"target_project_id": str(target_project.id)},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.data
        issue.refresh_from_db()
        intake_issue.refresh_from_db()
        assert issue.project_id == source_project.id
        assert intake_issue.status == -2
