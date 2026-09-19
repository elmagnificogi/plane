# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.conf import settings
from django.db import models
from django.db.models import Q

from .base import BaseModel
from .project import ProjectBaseModel


class WorkflowRole(models.TextChoices):
    PRODUCT = "product", "Product"
    DEVELOPER = "developer", "Developer"
    TESTER = "tester", "Tester"
    PROJECT_MANAGER = "project_manager", "Project manager"


class ProjectWorkflowConfiguration(BaseModel):
    """Opt-in configuration for Plane's lightweight business workflow."""

    project = models.OneToOneField(
        "db.Project",
        on_delete=models.CASCADE,
        related_name="workflow_configuration",
    )
    workspace = models.ForeignKey(
        "db.Workspace",
        on_delete=models.CASCADE,
        related_name="workspace_workflow_configurations",
    )
    is_enabled = models.BooleanField(default=False)
    schema_version = models.PositiveSmallIntegerField(default=1)
    state_mapping = models.JSONField(default=dict)
    defect_label = models.ForeignKey(
        "db.Label",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="defect_workflow_configurations",
    )
    blocking_label = models.ForeignKey(
        "db.Label",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="blocking_workflow_configurations",
    )

    class Meta:
        db_table = "project_workflow_configurations"
        ordering = ("-created_at",)

    def save(self, *args, **kwargs):
        self.workspace_id = self.project.workspace_id
        super().save(*args, **kwargs)


class ProjectWorkflowRole(ProjectBaseModel):
    """A business role used for workflow transitions, separate from Plane access roles."""

    member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_workflow_roles",
    )
    role = models.CharField(max_length=32, choices=WorkflowRole.choices)

    class Meta:
        db_table = "project_workflow_roles"
        ordering = ("role", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=["project", "member", "role"],
                condition=Q(deleted_at__isnull=True),
                name="workflow_role_unique_active_assignment",
            )
        ]

    def __str__(self):
        return f"{self.member_id} {self.role} <{self.project_id}>"


class ProjectWorkflowTransition(ProjectBaseModel):
    """Synchronous audit record used to authorize a safe one-step reversal."""

    issue = models.ForeignKey(
        "db.Issue",
        on_delete=models.CASCADE,
        related_name="workflow_transition_records",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="project_workflow_transitions",
    )
    from_state = models.ForeignKey(
        "db.State",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    to_state = models.ForeignKey(
        "db.State",
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    track = models.CharField(max_length=16)
    required_role = models.CharField(
        max_length=32,
        choices=WorkflowRole.choices,
        null=True,
        blank=True,
    )
    is_reversal = models.BooleanField(default=False)

    class Meta:
        db_table = "project_workflow_transitions"
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=["issue", "-created_at"],
                name="workflow_transition_issue_idx",
            )
        ]

    def __str__(self):
        return f"{self.issue_id}: {self.from_state_id} -> {self.to_state_id}"
