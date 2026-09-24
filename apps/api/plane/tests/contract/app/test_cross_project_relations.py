# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from rest_framework import status

from plane.db.models import Issue, Project, ProjectMember, State


@pytest.fixture
def cross_project_relation_data(db, workspace, create_user):
    source = Project.objects.create(name="Business Project", identifier="BUS", workspace=workspace)
    target = Project.objects.create(name="Test Tickets", identifier="TS", workspace=workspace)
    ProjectMember.objects.create(project=source, member=create_user, role=20, is_active=True)
    target_membership = ProjectMember.objects.create(project=target, member=create_user, role=20, is_active=True)

    source_state = State.objects.create(
        name="In Progress",
        project=source,
        workspace=workspace,
        group="started",
        default=True,
    )
    target_state = State.objects.create(
        name="Cluster Testing",
        project=target,
        workspace=workspace,
        group="started",
        default=True,
    )
    source_issue = Issue.objects.create(
        name="Business task",
        project=source,
        workspace=workspace,
        state=source_state,
        created_by=create_user,
    )
    target_issue = Issue.objects.create(
        name="Cluster test ticket",
        project=target,
        workspace=workspace,
        state=target_state,
        created_by=create_user,
    )
    return source, target, source_issue, target_issue, target_membership


@pytest.fixture(autouse=True)
def disable_relation_background_tasks(monkeypatch):
    monkeypatch.setattr("plane.app.views.issue.relation.issue_activity.delay", lambda **kwargs: None)


@pytest.mark.contract
@pytest.mark.django_db
class TestCrossProjectRelations:
    def test_workspace_search_and_relation_use_plane_native_global_scope(
        self,
        session_client,
        workspace,
        cross_project_relation_data,
    ):
        source, target, source_issue, target_issue, target_membership = cross_project_relation_data
        search_url = f"/api/workspaces/{workspace.slug}/projects/{source.id}/search-issues/"
        relation_url = (
            f"/api/workspaces/{workspace.slug}/projects/{source.id}/issues/{source_issue.id}/issue-relation/"
        )

        response = session_client.get(
            search_url,
            {
                "workspace_search": "true",
                "issue_relation": "true",
                "issue_id": str(source_issue.id),
                "search": "Cluster",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert [str(item["id"]) for item in response.data] == [str(target_issue.id)]

        response = session_client.post(
            relation_url,
            {"relation_type": "relates_to", "issues": [str(target_issue.id)]},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data[0]["project_identifier"] == "TS"
        assert response.data[0]["state_name"] == "Cluster Testing"

        target_membership.is_active = False
        target_membership.save(update_fields=["is_active"])

        response = session_client.get(relation_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["relates_to"][0]["project_identifier"] == "TS"
        assert response.data["relates_to"][0]["state_name"] == "Cluster Testing"

        response = session_client.patch(
            f"/api/workspaces/{workspace.slug}/projects/{target.id}/issues/{target_issue.id}/",
            {"name": "Must not change"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
