# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views import IssueWorkflowTransitionsEndpoint, ProjectWorkflowEndpoint


urlpatterns = [
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/workflow/",
        ProjectWorkflowEndpoint.as_view(),
        name="project-workflow",
    ),
    path(
        "workspaces/<str:slug>/projects/<uuid:project_id>/issues/<uuid:issue_id>/workflow-transitions/",
        IssueWorkflowTransitionsEndpoint.as_view(),
        name="issue-workflow-transitions",
    ),
]
