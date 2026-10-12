# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from plane.db.models import (
    Issue,
    IssueLabel,
    Label,
    Project,
    ProjectMember,
    ProjectWorkflowConfiguration,
    ProjectWorkflowRole,
    ProjectWorkflowTransition,
    State,
    StateGroup,
    WorkflowRole,
)


WORKFLOW_SCHEMA_VERSION = 1

STATE_DEFINITIONS = {
    "backlog": {"name": "需求完善", "group": StateGroup.BACKLOG, "color": "#60646C"},
    "todo": {"name": "待做", "group": StateGroup.UNSTARTED, "color": "#60646C"},
    "in_progress": {"name": "开发中", "group": StateGroup.STARTED, "color": "#F59E0B"},
    "delayed": {"name": "延期中", "group": StateGroup.CANCELLED, "color": "#D97706"},
    "waiting_for_test": {"name": "开发完成", "group": StateGroup.STARTED, "color": "#8B5CF6"},
    "testing": {"name": "测试中", "group": StateGroup.STARTED, "color": "#3B82F6"},
    "test_rejected": {"name": "测试打回", "group": StateGroup.STARTED, "color": "#EF4444"},
    "suspended": {"name": "挂起", "group": StateGroup.CANCELLED, "color": "#78716C"},
    "done": {"name": "完成", "group": StateGroup.COMPLETED, "color": "#46A758"},
    "delayed_done": {"name": "延期完成", "group": StateGroup.COMPLETED, "color": "#0E7490"},
    "cancelled": {"name": "取消", "group": StateGroup.CANCELLED, "color": "#9AA4BC"},
}

# Names used before the Plan catalog became the default project states.
LEGACY_STATE_NAMES = {
    "backlog": ("Backlog",),
    "todo": ("Todo",),
    "in_progress": ("In Progress",),
    "waiting_for_test": ("等待测试", "等待测试/开发完成"),
    "done": ("Done",),
    "cancelled": ("Cancelled",),
}

LABEL_DEFINITIONS = {
    "defect": {"name": "类型/缺陷", "color": "#EF4444", "description": "使用缺陷状态流转"},
    "blocking": {"name": "阻断", "color": "#DC2626", "description": "阻止主任务完成的子任务"},
}


SKIP_DESCENDANT_STATE_KEYS = frozenset({"cancelled", "delayed", "delayed_done", "suspended"})

MAIN_TRANSITIONS = {
    ("backlog", "todo"): WorkflowRole.PRODUCT,
    ("todo", "in_progress"): WorkflowRole.DEVELOPER,
    ("in_progress", "waiting_for_test"): WorkflowRole.DEVELOPER,
    ("waiting_for_test", "testing"): WorkflowRole.TESTER,
    ("testing", "test_rejected"): WorkflowRole.TESTER,
    ("test_rejected", "in_progress"): WorkflowRole.DEVELOPER,
    ("testing", "done"): WorkflowRole.PRODUCT,
    ("testing", "delayed_done"): WorkflowRole.PROJECT_MANAGER,
    ("in_progress", "cancelled"): WorkflowRole.PRODUCT,
    ("waiting_for_test", "cancelled"): WorkflowRole.PRODUCT,
    ("testing", "cancelled"): WorkflowRole.PRODUCT,
}

DEFECT_TRANSITIONS = {
    ("test_rejected", "in_progress"): WorkflowRole.DEVELOPER,
    ("in_progress", "done"): WorkflowRole.TESTER,
    ("in_progress", "delayed_done"): WorkflowRole.PROJECT_MANAGER,
    ("in_progress", "suspended"): WorkflowRole.PROJECT_MANAGER,
    ("in_progress", "cancelled"): WorkflowRole.PRODUCT,
}


class WorkflowTransitionError(Exception):
    def __init__(self, code: str, message: str, **details):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def as_dict(self):
        return {"code": self.code, "message": self.message, **self.details}


@dataclass(frozen=True)
class WorkflowTransitionDecision:
    configuration_id: UUID
    schema_version: int
    issue_id: UUID
    project_id: UUID
    workspace_id: UUID
    track: str
    from_key: str | None
    to_key: str | None
    from_state_id: UUID | None
    to_state_id: UUID
    required_role: str | None
    actor_id: UUID
    is_reversal: bool = False


def _state_key(configuration: ProjectWorkflowConfiguration, state_id) -> str | None:
    state_id = str(state_id) if state_id else None
    return next(
        (key for key, mapped_state_id in configuration.state_mapping.items() if str(mapped_state_id) == state_id),
        None,
    )


def _member_roles(project_id, actor_id) -> set[str]:
    if not actor_id:
        return set()
    if not ProjectMember.objects.filter(
        project_id=project_id,
        member_id=actor_id,
        is_active=True,
    ).exists():
        return set()
    return set(
        ProjectWorkflowRole.objects.filter(
            project_id=project_id,
            member_id=actor_id,
        ).values_list("role", flat=True)
    )


def _is_defect(
    issue: Issue,
    configuration: ProjectWorkflowConfiguration,
    proposed_label_ids: Iterable[UUID] | None,
) -> bool:
    if not configuration.defect_label_id:
        return False
    if proposed_label_ids is not None:
        return str(configuration.defect_label_id) in {str(label_id) for label_id in proposed_label_ids}
    return IssueLabel.objects.filter(
        issue_id=issue.id,
        label_id=configuration.defect_label_id,
    ).exists()


def _unfinished_blockers(issue: Issue, configuration: ProjectWorkflowConfiguration):
    if not configuration.blocking_label_id:
        return Issue.objects.none()
    terminal_ids = [
        configuration.state_mapping.get(key)
        for key in ("done", "delayed_done", "cancelled")
        if configuration.state_mapping.get(key)
    ]
    return Issue.issue_objects.filter(
        parent_id=issue.id,
        label_issue__label_id=configuration.blocking_label_id,
    ).exclude(state_id__in=terminal_ids)


def _is_latest_transition_reversal(*, issue: Issue, target_state: State, actor_id) -> bool:
    """Return whether the actor is undoing their own latest accepted state change."""

    if not actor_id:
        return False
    latest_transition = (
        ProjectWorkflowTransition.objects.filter(issue_id=issue.id)
        .only("actor_id", "from_state_id", "to_state_id")
        .order_by("-created_at")
        .first()
    )
    if latest_transition is None:
        return False
    return (
        latest_transition.actor_id == actor_id
        and latest_transition.to_state_id == issue.state_id
        and latest_transition.from_state_id == target_state.id
    )


def validate_issue_transition(
    *,
    issue: Issue,
    target_state: State,
    actor_id,
    proposed_label_ids: Iterable[UUID] | None = None,
) -> WorkflowTransitionDecision | None:
    """Validate an issue state change when the project's workflow is enabled."""

    configuration = (
        ProjectWorkflowConfiguration.objects.filter(project_id=issue.project_id, is_enabled=True)
        .select_related("defect_label", "blocking_label")
        .first()
    )
    if configuration is None or issue.state_id == target_state.id:
        return None

    from_key = _state_key(configuration, issue.state_id)
    to_key = _state_key(configuration, target_state.id)
    track = "defect" if _is_defect(issue, configuration, proposed_label_ids) else "main"

    if _is_latest_transition_reversal(issue=issue, target_state=target_state, actor_id=actor_id):
        return WorkflowTransitionDecision(
            configuration_id=configuration.id,
            schema_version=configuration.schema_version,
            issue_id=issue.id,
            project_id=issue.project_id,
            workspace_id=issue.workspace_id,
            track=track,
            from_key=from_key,
            to_key=to_key,
            from_state_id=issue.state_id,
            to_state_id=target_state.id,
            required_role=None,
            actor_id=actor_id,
            is_reversal=True,
        )

    if to_key is None:
        raise WorkflowTransitionError(
            "TARGET_STATE_OUTSIDE_WORKFLOW",
            "目标状态不属于当前项目启用的状态流转。",
            target_state_id=str(target_state.id),
        )

    actor_roles = _member_roles(issue.project_id, actor_id)
    if WorkflowRole.PROJECT_MANAGER in actor_roles:
        required_role = WorkflowRole.PROJECT_MANAGER
    else:
        transitions = DEFECT_TRANSITIONS if track == "defect" else MAIN_TRANSITIONS

        # Imported/custom legacy states can enter the managed flow through Backlog.
        required_role = (
            WorkflowRole.PRODUCT if from_key is None and to_key == "backlog" else transitions.get((from_key, to_key))
        )
        if required_role is None:
            raise WorkflowTransitionError(
                "TRANSITION_NOT_ALLOWED",
                "当前状态不能直接流转到目标状态。",
                track=track,
                from_state=from_key,
                to_state=to_key,
            )

        if required_role not in actor_roles:
            raise WorkflowTransitionError(
                "WORKFLOW_ROLE_REQUIRED",
                "当前成员缺少执行此状态流转所需的业务角色。",
                required_role=required_role,
                actor_roles=sorted(actor_roles),
            )

    if track == "main" and to_key in {"done", "delayed_done"}:
        blockers = _unfinished_blockers(issue, configuration)
        if blockers.exists():
            raise WorkflowTransitionError(
                "BLOCKING_SUB_ISSUES_OPEN",
                "仍有未完成的阻断子任务，主任务不能完成。",
                blocking_issue_ids=[str(issue_id) for issue_id in blockers.values_list("id", flat=True)[:20]],
            )

    return WorkflowTransitionDecision(
        configuration_id=configuration.id,
        schema_version=configuration.schema_version,
        issue_id=issue.id,
        project_id=issue.project_id,
        workspace_id=issue.workspace_id,
        track=track,
        from_key=from_key,
        to_key=to_key,
        from_state_id=issue.state_id,
        to_state_id=target_state.id,
        required_role=required_role,
        actor_id=actor_id,
    )


def dispatch_workflow_transition(decision: WorkflowTransitionDecision, *, slug: str, origin: str | None):
    """Record the accepted transition and queue its webhook after commit."""

    from plane.bgtasks.webhook_task import workflow_transition_activity

    ProjectWorkflowTransition.objects.create(
        issue_id=decision.issue_id,
        actor_id=decision.actor_id,
        from_state_id=decision.from_state_id,
        to_state_id=decision.to_state_id,
        project_id=decision.project_id,
        workspace_id=decision.workspace_id,
        track=decision.track,
        required_role=decision.required_role,
        is_reversal=decision.is_reversal,
    )

    transaction.on_commit(
        lambda: workflow_transition_activity.delay(
            issue_id=str(decision.issue_id),
            actor_id=str(decision.actor_id),
            slug=slug,
            current_site=origin,
            transition={
                "configuration_id": str(decision.configuration_id),
                "schema_version": decision.schema_version,
                "track": decision.track,
                "from_key": decision.from_key,
                "to_key": decision.to_key,
                "from_state_id": str(decision.from_state_id) if decision.from_state_id else None,
                "to_state_id": str(decision.to_state_id),
                "required_role": decision.required_role,
                "is_reversal": decision.is_reversal,
            },
        ),
        robust=True,
    )


def _eligible_descendants(issue: Issue, configuration: ProjectWorkflowConfiguration) -> list[Issue]:
    """Return same-project descendants that a project manager may move to Done.

    Cancelled, delayed, delayed-done, suspended, and blocking-label issues stop their branch.
    An issue already in Done is left unchanged, and its other descendants are still visited.
    """

    done_state_id = str(configuration.state_mapping.get("done") or "")
    blocking_label_id = configuration.blocking_label_id
    eligible: list[Issue] = []
    frontier = [issue.id]
    seen = {issue.id}
    while frontier:
        children = list(
            Issue.issue_objects.filter(project_id=issue.project_id, parent_id__in=frontier).select_related("state")
        )
        if not children:
            break
        blocking_ids = set()
        if blocking_label_id:
            blocking_ids = set(
                IssueLabel.objects.filter(
                    issue_id__in=[child.id for child in children],
                    label_id=blocking_label_id,
                ).values_list("issue_id", flat=True)
            )
        next_frontier = []
        for child in children:
            if child.id in seen:
                continue
            seen.add(child.id)
            state_key = _state_key(configuration, child.state_id)
            if child.id in blocking_ids or state_key in SKIP_DESCENDANT_STATE_KEYS:
                continue
            if str(child.state_id) != done_state_id:
                eligible.append(child)
            next_frontier.append(child.id)
        frontier = next_frontier
    return eligible


def descendant_completion_preview(issue: Issue, actor_id, target_state: State) -> dict:
    """Tell the client whether completing this issue should ask about child items."""

    configuration = ProjectWorkflowConfiguration.objects.filter(project_id=issue.project_id, is_enabled=True).first()
    if configuration is None:
        return {"should_prompt": False, "eligible_count": 0}
    if _state_key(configuration, target_state.id) not in {"done", "delayed_done"}:
        return {"should_prompt": False, "eligible_count": 0}
    if WorkflowRole.PROJECT_MANAGER not in _member_roles(issue.project_id, actor_id):
        return {"should_prompt": False, "eligible_count": 0}
    try:
        validate_issue_transition(issue=issue, target_state=target_state, actor_id=actor_id)
    except WorkflowTransitionError:
        return {"should_prompt": False, "eligible_count": 0}
    eligible_count = len(_eligible_descendants(issue, configuration))
    return {"should_prompt": eligible_count > 0, "eligible_count": eligible_count}


def _record_descendant_state_change(*, child: Issue, old_state_id, new_state_id, actor_id, slug: str, origin):
    from plane.bgtasks.issue_activities_task import issue_activity
    from plane.bgtasks.webhook_task import model_activity

    current_instance = json.dumps(
        {"id": str(child.id), "state_id": str(old_state_id) if old_state_id else None},
        cls=DjangoJSONEncoder,
    )
    requested_data = {"state_id": str(new_state_id)}
    issue_activity.delay(
        type="issue.activity.updated",
        requested_data=json.dumps(requested_data),
        actor_id=str(actor_id),
        issue_id=str(child.id),
        project_id=str(child.project_id),
        current_instance=current_instance,
        epoch=int(timezone.now().timestamp()),
        notification=True,
        origin=origin,
    )
    model_activity.delay(
        model_name="issue",
        model_id=str(child.id),
        requested_data=requested_data,
        current_instance=current_instance,
        actor_id=actor_id,
        slug=slug,
        origin=origin,
    )


def complete_descendant_issues(*, issue: Issue, actor_id, slug: str, origin) -> dict | None:
    """Move eligible descendants to Done after a project manager completes the parent.

    Returns None when this actor or target state cannot cascade. Per-child failures stay
    in ``failed`` and do not undo siblings that already moved to Done.
    """

    configuration = ProjectWorkflowConfiguration.objects.filter(project_id=issue.project_id, is_enabled=True).first()
    if configuration is None:
        return None
    if _state_key(configuration, issue.state_id) not in {"done", "delayed_done"}:
        return None
    if WorkflowRole.PROJECT_MANAGER not in _member_roles(issue.project_id, actor_id):
        return None

    done_state_id = configuration.state_mapping.get("done")
    done_state = State.objects.filter(id=done_state_id, project_id=issue.project_id).first() if done_state_id else None
    if done_state is None:
        return {
            "completed_issue_ids": [],
            "failed": [{"id": str(issue.id), "name": issue.name, "message": "项目未配置完成状态。"}],
            "done_state_id": None,
        }

    completed = []
    failed = []
    for child in _eligible_descendants(issue, configuration):
        old_state_id = child.state_id
        try:
            decision = validate_issue_transition(issue=child, target_state=done_state, actor_id=actor_id)
        except WorkflowTransitionError as error:
            failed.append({"id": str(child.id), "name": child.name, "message": error.message})
            continue
        child.state = done_state
        child.save(update_fields=["state", "updated_at"])
        if decision:
            dispatch_workflow_transition(decision, slug=slug, origin=origin)
        _record_descendant_state_change(
            child=child,
            old_state_id=old_state_id,
            new_state_id=done_state.id,
            actor_id=actor_id,
            slug=slug,
            origin=origin,
        )
        completed.append(str(child.id))
    return {
        "completed_issue_ids": completed,
        "failed": failed,
        "done_state_id": str(done_state.id),
    }


def _matching_workflow_state(project: Project, key: str, definition: dict) -> State | None:
    names = (definition["name"], *LEGACY_STATE_NAMES.get(key, ()))
    query = Q()
    for name in names:
        query |= Q(name__iexact=name)
    matches = list(State.objects.filter(project=project).filter(query))
    for name in names:
        for state in matches:
            if state.name.lower() == name.lower():
                return state
    return None


@transaction.atomic
def bootstrap_project_workflow(project: Project, *, actor_id) -> ProjectWorkflowConfiguration:
    """Create only missing states/labels and return an enabled configuration."""

    state_mapping = {}
    for key, definition in STATE_DEFINITIONS.items():
        state = _matching_workflow_state(project, key, definition)
        if state is None:
            state = State.objects.create(
                project=project,
                name=definition["name"],
                group=definition["group"],
                color=definition["color"],
                created_by_id=actor_id,
            )
        state_mapping[key] = str(state.id)

    labels = {}
    for key, definition in LABEL_DEFINITIONS.items():
        label = Label.objects.filter(project=project, name__iexact=definition["name"]).first()
        if label is None:
            label = Label.objects.create(
                project=project,
                name=definition["name"],
                color=definition["color"],
                description=definition["description"],
                created_by_id=actor_id,
            )
        labels[key] = label

    configuration, _ = ProjectWorkflowConfiguration.objects.update_or_create(
        project=project,
        defaults={
            "workspace": project.workspace,
            "is_enabled": True,
            "schema_version": WORKFLOW_SCHEMA_VERSION,
            "state_mapping": state_mapping,
            "defect_label": labels["defect"],
            "blocking_label": labels["blocking"],
        },
    )
    return configuration


def available_transitions(issue: Issue, actor_id) -> list[dict]:
    configuration = ProjectWorkflowConfiguration.objects.filter(project_id=issue.project_id, is_enabled=True).first()
    if configuration is None:
        return []

    from_key = _state_key(configuration, issue.state_id)
    track = "defect" if _is_defect(issue, configuration, None) else "main"
    transitions = DEFECT_TRANSITIONS if track == "defect" else MAIN_TRANSITIONS
    actor_roles = _member_roles(issue.project_id, actor_id)
    states = {str(state.id): state for state in State.objects.filter(id__in=configuration.state_mapping.values())}
    results = []
    if WorkflowRole.PROJECT_MANAGER in actor_roles:
        for target, state_id in configuration.state_mapping.items():
            target_state = states.get(str(state_id))
            if target_state is None or target_state.id == issue.state_id:
                continue
            try:
                decision = validate_issue_transition(issue=issue, target_state=target_state, actor_id=actor_id)
            except WorkflowTransitionError:
                continue
            results.append(
                {
                    "state_key": target,
                    "state_id": state_id,
                    "required_role": decision.required_role if decision else WorkflowRole.PROJECT_MANAGER,
                    "track": track,
                    "is_reversal": decision.is_reversal if decision else False,
                }
            )
        return results

    for (source, target), required_role in transitions.items():
        if source != from_key or required_role not in actor_roles:
            continue
        state_id = configuration.state_mapping.get(target)
        target_state = states.get(str(state_id))
        if target_state is None:
            continue
        try:
            validate_issue_transition(issue=issue, target_state=target_state, actor_id=actor_id)
        except WorkflowTransitionError:
            continue
        results.append(
            {
                "state_key": target,
                "state_id": state_id,
                "required_role": required_role,
                "track": track,
                "is_reversal": False,
            }
        )
    if from_key is None and WorkflowRole.PRODUCT in actor_roles:
        results.append(
            {
                "state_key": "backlog",
                "state_id": configuration.state_mapping.get("backlog"),
                "required_role": WorkflowRole.PRODUCT,
                "track": track,
                "is_reversal": False,
            }
        )
    latest_transition = (
        ProjectWorkflowTransition.objects.filter(issue_id=issue.id)
        .only("actor_id", "from_state_id", "to_state_id")
        .order_by("-created_at")
        .first()
    )
    if (
        latest_transition is not None
        and latest_transition.actor_id == actor_id
        and latest_transition.to_state_id == issue.state_id
        and latest_transition.from_state_id is not None
        and all(str(result["state_id"]) != str(latest_transition.from_state_id) for result in results)
    ):
        reversal_state = State.objects.filter(
            id=latest_transition.from_state_id,
            project_id=issue.project_id,
        ).first()
        if reversal_state is not None:
            results.append(
                {
                    "state_key": _state_key(configuration, reversal_state.id),
                    "state_id": reversal_state.id,
                    "required_role": None,
                    "track": track,
                    "is_reversal": True,
                }
            )
    return results
