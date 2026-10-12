# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db import models
from django.template.defaultfilters import slugify
from django.db.models import Q

# Module imports
from .project import ProjectBaseModel
from plane.db.mixins import SoftDeletionManager

class StateGroup(models.TextChoices):
    BACKLOG = "backlog", "Backlog"
    UNSTARTED = "unstarted", "Unstarted"
    STARTED = "started", "Started"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"
    TRIAGE = "triage", "Triage"


# Default states for a newly created project. These follow the Plan status
# catalog. Triage stays hidden and is only used by intake.
DEFAULT_STATES = [
    {
        "name": "需求完善",
        "color": "#60646C",
        "sequence": 15000,
        "group": StateGroup.BACKLOG.value,
        "default": True,
    },
    {
        "name": "待做",
        "color": "#60646C",
        "sequence": 25000,
        "group": StateGroup.UNSTARTED.value,
    },
    {
        "name": "开发中",
        "color": "#F59E0B",
        "sequence": 35000,
        "group": StateGroup.STARTED.value,
    },
    {
        "name": "开发完成",
        "color": "#8B5CF6",
        "sequence": 45000,
        "group": StateGroup.STARTED.value,
    },
    {
        "name": "测试中",
        "color": "#3B82F6",
        "sequence": 55000,
        "group": StateGroup.STARTED.value,
    },
    {
        "name": "测试打回",
        "color": "#EF4444",
        "sequence": 65000,
        "group": StateGroup.STARTED.value,
    },
    {
        "name": "完成",
        "color": "#46A758",
        "sequence": 95000,
        "group": StateGroup.COMPLETED.value,
    },
    {
        "name": "延期完成",
        "color": "#0E7490",
        "sequence": 105000,
        "group": StateGroup.COMPLETED.value,
    },
    {
        "name": "取消",
        "color": "#9AA4BC",
        "sequence": 115000,
        "group": StateGroup.CANCELLED.value,
    },
    {
        "name": "延期中",
        "color": "#D97706",
        "sequence": 125000,
        "group": StateGroup.CANCELLED.value,
    },
    {
        "name": "挂起",
        "color": "#78716C",
        "sequence": 135000,
        "group": StateGroup.CANCELLED.value,
    },
    {
        "name": "Triage",
        "color": "#4E5355",
        "sequence": 145000,
        "group": StateGroup.TRIAGE.value,
    },
]


class StateManager(SoftDeletionManager):
    """Default manager - excludes triage states"""

    def get_queryset(self):
        return super().get_queryset().exclude(group=StateGroup.TRIAGE.value)


class TriageStateManager(SoftDeletionManager):
    """Manager for triage states only"""

    def get_queryset(self):
        return super().get_queryset().filter(group=StateGroup.TRIAGE.value)


class State(ProjectBaseModel):
    name = models.CharField(max_length=255, verbose_name="State Name")
    description = models.TextField(verbose_name="State Description", blank=True)
    color = models.CharField(max_length=255, verbose_name="State Color")
    slug = models.SlugField(max_length=100, blank=True)
    sequence = models.FloatField(default=65535)
    group = models.CharField(
        choices=StateGroup.choices,
        default=StateGroup.BACKLOG,
        max_length=20,
    )
    is_triage = models.BooleanField(default=False)
    default = models.BooleanField(default=False)
    external_source = models.CharField(max_length=255, null=True, blank=True)
    external_id = models.CharField(max_length=255, blank=True, null=True)

    objects = StateManager()
    all_state_objects = models.Manager()
    triage_objects = TriageStateManager()

    def __str__(self):
        """Return name of the state"""
        return f"{self.name} <{self.project.name}>"

    class Meta:
        unique_together = ["name", "project", "deleted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "project"],
                condition=Q(deleted_at__isnull=True),
                name="state_unique_name_project_when_deleted_at_null",
            )
        ]
        verbose_name = "State"
        verbose_name_plural = "States"
        db_table = "states"
        ordering = ("sequence",)

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        if self._state.adding:
            # Get the maximum sequence value from the database
            last_id = State.objects.filter(project=self.project).aggregate(largest=models.Max("sequence"))["largest"]
            # if last_id is not None
            if last_id is not None:
                self.sequence = last_id + 15000

        return super().save(*args, **kwargs)
