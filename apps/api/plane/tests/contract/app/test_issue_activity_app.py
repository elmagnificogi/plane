# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""Contract coverage for the combined issue activity history endpoint."""

import pytest
from rest_framework import status

from plane.db.models import Issue, IssueActivity, IssueComment, Project, ProjectMember


@pytest.fixture
def project(db, workspace, create_user):
    project = Project.objects.create(
        name="Activity Project",
        identifier="ACT",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(
        project=project,
        member=create_user,
        workspace=workspace,
        role=20,
    )
    return project


@pytest.mark.contract
@pytest.mark.django_db
def test_combined_history_serializes_activities_and_comments(session_client, workspace, project, create_user):
    issue = Issue(name="Activity work item", project=project, workspace=workspace)
    issue.save(created_by_id=create_user.id)
    IssueActivity.objects.create(
        issue=issue,
        actor=create_user,
        verb="updated",
        field="state",
        old_value="Todo",
        new_value="In Progress",
        project=project,
        workspace=workspace,
    )
    IssueComment.objects.create(
        issue=issue,
        actor=create_user,
        comment_html="<p>Ready for review</p>",
        project=project,
        workspace=workspace,
    )

    response = session_client.get(f"/api/workspaces/{workspace.slug}/projects/{project.id}/issues/{issue.id}/history/")

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 2
    assert all(isinstance(entry, dict) for entry in response.data)
    assert all("created_at" in entry for entry in response.data)
    assert [entry["created_at"] for entry in response.data] == sorted(entry["created_at"] for entry in response.data)
