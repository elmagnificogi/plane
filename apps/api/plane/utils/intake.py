# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Helpers for accepting intake work items into a project."""

from django.db import connection
from django.db.models import Max

from plane.db.models import (
    CommentReaction,
    CycleIssue,
    Description,
    FileAsset,
    GithubIssueSync,
    Issue,
    IssueActivity,
    IssueAssignee,
    IssueBlocker,
    IssueComment,
    IssueDescriptionVersion,
    IssueLabel,
    IssueLink,
    IssueMention,
    IssueReaction,
    IssueRelation,
    IssueSequence,
    IssueSubscriber,
    IssueVersion,
    IssueVote,
    ModuleIssue,
    Project,
    ProjectMember,
    ProjectWorkflowTransition,
    State,
)
from plane.db.models.issue import IssueAttachment
from plane.utils.uuid import convert_uuid_to_integer


class IntakeProjectMoveError(ValueError):
    """Raised when an intake work item cannot be moved safely."""


def get_target_project_default_state(target_project: Project) -> State:
    """Return the destination's default non-triage state."""

    default_state = State.objects.filter(project=target_project, default=True).exclude(is_triage=True).first()
    if default_state is None:
        raise IntakeProjectMoveError("Cannot accept intake issue: No default state found for the target project")
    return default_state


def _next_project_sequence(target_project: Project) -> int:
    """Reserve the next work-item sequence while the caller holds a DB transaction."""

    lock_key = convert_uuid_to_integer(target_project.id)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_key])

    last_sequence = IssueSequence.objects.filter(project=target_project).aggregate(largest=Max("sequence"))["largest"]
    return last_sequence + 1 if last_sequence else 1


def move_intake_issue_to_project(issue: Issue, target_project: Project) -> Issue:
    """Move an intake work item to another project without changing its UUID.

    Intake rows intentionally stay in their source project so the original
    intake retains its accepted-item history. Project-specific associations
    that cannot be valid in the destination are cleared; portable history and
    content are re-scoped to the destination project.

    The caller must wrap this operation in ``transaction.atomic()``.
    """

    if issue.project_id == target_project.id:
        return issue
    if issue.workspace_id != target_project.workspace_id:
        raise IntakeProjectMoveError("The target project must belong to the same workspace")

    target_state = get_target_project_default_state(target_project)
    next_sequence = _next_project_sequence(target_project)

    # Project-specific planning and workflow data cannot be carried across.
    IssueLabel.objects.filter(issue=issue).delete()
    CycleIssue.objects.filter(issue=issue).delete()
    ModuleIssue.objects.filter(issue=issue).delete()
    ProjectWorkflowTransition.objects.filter(issue=issue).delete()
    GithubIssueSync.objects.filter(issue=issue).delete()

    # Keep assignees only when they are active members of the destination.
    target_member_ids = ProjectMember.objects.filter(
        project=target_project,
        is_active=True,
        role__gte=15,
    ).values_list("member_id", flat=True)
    IssueAssignee.objects.filter(issue=issue).exclude(assignee_id__in=target_member_ids).delete()
    IssueAssignee.objects.filter(issue=issue, assignee_id__in=target_member_ids).update(project=target_project)

    # A parent or child relationship cannot span projects in Plane's editor.
    Issue.objects.filter(parent=issue).update(parent=None)

    comment_ids = list(IssueComment.objects.filter(issue=issue).values_list("id", flat=True))
    description_ids = list(
        IssueComment.objects.filter(issue=issue, description_id__isnull=False).values_list("description_id", flat=True)
    )

    # Portable work-item content and history continue to belong to the same UUID.
    for model in (
        IssueMention,
        IssueLink,
        IssueAttachment,
        IssueActivity,
        IssueComment,
        IssueSubscriber,
        IssueReaction,
        IssueVote,
        IssueVersion,
        IssueDescriptionVersion,
    ):
        model.objects.filter(issue=issue).update(project=target_project)

    IssueRelation.objects.filter(issue=issue).update(project=target_project)
    IssueBlocker.objects.filter(block=issue).update(project=target_project)
    if comment_ids:
        CommentReaction.objects.filter(comment_id__in=comment_ids).update(project=target_project)
        FileAsset.objects.filter(comment_id__in=comment_ids).update(project=target_project)
    if description_ids:
        Description.objects.filter(id__in=description_ids).update(project=target_project)
    FileAsset.objects.filter(issue=issue).update(project=target_project)

    # Retire the old key and allocate a new key in the destination project.
    IssueSequence.objects.filter(issue=issue).update(issue=None, deleted=True)
    issue.project = target_project
    issue.state = target_state
    issue.sequence_id = next_sequence
    issue.sort_order = 65535
    issue.parent = None
    issue.type = None
    issue.estimate_point = None
    issue.save(
        update_fields=[
            "project",
            "state",
            "sequence_id",
            "sort_order",
            "parent",
            "type",
            "estimate_point",
            "updated_at",
        ]
    )
    IssueSequence.objects.create(issue=issue, sequence=next_sequence, project=target_project)
    return issue
