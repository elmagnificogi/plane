# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Contract tests for project-scoped Intake template configuration."""

from uuid import uuid4

import pytest
from rest_framework import status

from plane.db.models import Intake, Project, ProjectMember, WorkspaceMember


@pytest.fixture
def template_intake(db, workspace, create_user):
    project = Project.objects.create(
        name="Template Project",
        identifier="TPL",
        workspace=workspace,
        created_by=create_user,
    )
    ProjectMember.objects.create(project=project, member=create_user, role=20, is_active=True)
    intake = Intake.objects.create(
        name="Default Intake",
        project=project,
        workspace=workspace,
        is_default=True,
    )
    return project, intake


@pytest.mark.contract
@pytest.mark.django_db
class TestIntakeTemplateConfig:
    @staticmethod
    def get_url(workspace_slug, project_id, intake_id=None):
        suffix = f"{intake_id}/" if intake_id else ""
        return f"/api/workspaces/{workspace_slug}/projects/{project_id}/intakes/{suffix}"

    def test_admin_can_save_and_member_can_read_templates(
        self,
        session_client,
        workspace,
        create_user,
        template_intake,
    ):
        project, intake = template_intake
        template_id = str(uuid4())
        payload = {
            "template_config": {
                "templates": [
                    {
                        "id": template_id,
                        "name": "Customer request",
                        "description": "## Background\n\nDescribe the expected outcome.",
                    }
                ],
                "default_template_id": template_id,
            }
        }

        response = session_client.patch(
            self.get_url(workspace.slug, project.id, intake.id),
            payload,
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["template_config"] == payload["template_config"]

        WorkspaceMember.objects.filter(workspace=workspace, member=create_user).update(role=15)
        ProjectMember.objects.filter(project=project, member=create_user).update(role=15)

        response = session_client.get(self.get_url(workspace.slug, project.id))
        assert response.status_code == status.HTTP_200_OK
        assert response.data["template_config"]["default_template_id"] == template_id

        response = session_client.patch(
            self.get_url(workspace.slug, project.id, intake.id),
            {"template_config": {"templates": [], "default_template_id": None}},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_rejects_invalid_default_and_duplicate_name(
        self,
        session_client,
        workspace,
        create_user,
        template_intake,
    ):
        project, intake = template_intake
        template_id = str(uuid4())
        config = {
            "templates": [
                {
                    "id": template_id,
                    "name": "Invalid",
                    "description": "## Background",
                }
            ],
            "default_template_id": str(uuid4()),
        }

        response = session_client.patch(
            self.get_url(workspace.slug, project.id, intake.id),
            {"template_config": config},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        config["default_template_id"] = template_id
        config["templates"].append(
            {"id": str(uuid4()), "name": "invalid", "description": "## Duplicate name"}
        )
        response = session_client.patch(
            self.get_url(workspace.slug, project.id, intake.id),
            {"template_config": config},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
