# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import patch

import pytest

from plane.db.models import (
    Issue,
    IssueLabel,
    ProjectMember,
    ProjectWorkflowRole,
    ProjectWorkflowTransition,
    State,
    WorkflowRole,
)
from plane.tests.factories import ProjectFactory, UserFactory, WorkspaceFactory
from plane.utils.workflow import (
    DEFECT_TRANSITIONS,
    MAIN_TRANSITIONS,
    WorkflowTransitionError,
    available_transitions,
    bootstrap_project_workflow,
    dispatch_workflow_transition,
    validate_issue_transition,
)


pytestmark = pytest.mark.django_db


@pytest.fixture
def workflow_project():
    owner = UserFactory()
    workspace = WorkspaceFactory(owner=owner)
    project = ProjectFactory(workspace=workspace, identifier="FLOW")
    ProjectMember.objects.create(project=project, member=owner, role=20)
    configuration = bootstrap_project_workflow(project, actor_id=owner.id)
    states = {key: State.objects.get(id=state_id) for key, state_id in configuration.state_mapping.items()}
    return owner, project, configuration, states


def assign_role(project, member, role):
    ProjectWorkflowRole.objects.create(project=project, member=member, role=role)


def create_issue(project, state, **kwargs):
    return Issue.objects.create(project=project, state=state, name=kwargs.pop("name", "Workflow issue"), **kwargs)


def test_bootstrap_is_additive_and_idempotent(workflow_project):
    owner, project, first_configuration, _states = workflow_project
    existing_ids = set(State.objects.filter(project=project).values_list("id", flat=True))

    second_configuration = bootstrap_project_workflow(project, actor_id=owner.id)

    assert second_configuration.id == first_configuration.id
    assert set(State.objects.filter(project=project).values_list("id", flat=True)) == existing_ids
    assert State.objects.filter(project=project, name="等待测试").exists()
    assert second_configuration.defect_label.name == "类型/缺陷"
    assert second_configuration.blocking_label.name == "阻断"


def test_main_flow_requires_the_business_role(workflow_project):
    owner, project, _configuration, states = workflow_project
    issue = create_issue(project, states["backlog"])

    with pytest.raises(WorkflowTransitionError) as exception:
        validate_issue_transition(issue=issue, target_state=states["todo"], actor_id=owner.id)

    assert exception.value.code == "WORKFLOW_ROLE_REQUIRED"
    assign_role(project, owner, WorkflowRole.PRODUCT)
    decision = validate_issue_transition(issue=issue, target_state=states["todo"], actor_id=owner.id)
    assert decision is not None
    assert decision.track == "main"
    assert decision.required_role == WorkflowRole.PRODUCT


def test_main_flow_rejects_skipped_states(workflow_project):
    owner, project, _configuration, states = workflow_project
    assign_role(project, owner, WorkflowRole.PRODUCT)
    issue = create_issue(project, states["backlog"])

    with pytest.raises(WorkflowTransitionError) as exception:
        validate_issue_transition(issue=issue, target_state=states["done"], actor_id=owner.id)

    assert exception.value.code == "TRANSITION_NOT_ALLOWED"


def test_main_policy_matches_the_specification():
    assert MAIN_TRANSITIONS == {
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


def test_defect_policy_matches_the_specification():
    assert DEFECT_TRANSITIONS == {
        ("test_rejected", "in_progress"): WorkflowRole.DEVELOPER,
        ("in_progress", "done"): WorkflowRole.TESTER,
        ("in_progress", "delayed_done"): WorkflowRole.PROJECT_MANAGER,
        ("in_progress", "suspended"): WorkflowRole.PROJECT_MANAGER,
        ("in_progress", "cancelled"): WorkflowRole.PRODUCT,
    }


def test_product_only_sees_todo_from_backlog(workflow_project):
    owner, project, _configuration, states = workflow_project
    assign_role(project, owner, WorkflowRole.PRODUCT)
    issue = create_issue(project, states["backlog"])

    assert [transition["state_key"] for transition in available_transitions(issue, owner.id)] == ["todo"]


def test_regular_roles_have_no_invented_exit_from_suspended(workflow_project):
    owner, project, configuration, states = workflow_project
    assign_role(project, owner, WorkflowRole.PRODUCT)
    issue = create_issue(project, states["suspended"])
    IssueLabel.objects.create(project=project, issue=issue, label=configuration.defect_label)

    assert available_transitions(issue, owner.id) == []


def test_project_manager_can_switch_between_all_managed_states(workflow_project):
    owner, project, configuration, states = workflow_project
    assign_role(project, owner, WorkflowRole.PROJECT_MANAGER)
    issue = create_issue(project, states["backlog"])

    for source_key, source_state in states.items():
        issue.state = source_state
        for target_key, target_state in states.items():
            if source_key == target_key:
                continue
            decision = validate_issue_transition(issue=issue, target_state=target_state, actor_id=owner.id)
            assert decision is not None
            assert decision.required_role == WorkflowRole.PROJECT_MANAGER

    issue.state = states["backlog"]
    visible_targets = {transition["state_key"] for transition in available_transitions(issue, owner.id)}
    assert visible_targets == set(configuration.state_mapping) - {"backlog"}


def test_defect_uses_regression_flow(workflow_project):
    owner, project, configuration, states = workflow_project
    assign_role(project, owner, WorkflowRole.TESTER)
    issue = create_issue(project, states["in_progress"])
    IssueLabel.objects.create(project=project, issue=issue, label=configuration.defect_label)

    decision = validate_issue_transition(issue=issue, target_state=states["done"], actor_id=owner.id)

    assert decision is not None
    assert decision.track == "defect"
    assert decision.required_role == WorkflowRole.TESTER


def test_open_blocking_child_prevents_main_completion(workflow_project):
    owner, project, configuration, states = workflow_project
    assign_role(project, owner, WorkflowRole.PRODUCT)
    parent = create_issue(project, states["testing"], name="Parent")
    child = create_issue(project, states["in_progress"], name="Blocking defect", parent=parent)
    IssueLabel.objects.create(project=project, issue=child, label=configuration.blocking_label)

    with pytest.raises(WorkflowTransitionError) as exception:
        validate_issue_transition(issue=parent, target_state=states["done"], actor_id=owner.id)

    assert exception.value.code == "BLOCKING_SUB_ISSUES_OPEN"
    child.state = states["done"]
    child.save(update_fields=["state"])
    decision = validate_issue_transition(issue=parent, target_state=states["done"], actor_id=owner.id)
    assert decision is not None


def test_actor_can_reverse_their_latest_transition(workflow_project):
    owner, project, _configuration, states = workflow_project
    assign_role(project, owner, WorkflowRole.PRODUCT)
    issue = create_issue(project, states["backlog"])

    forward = validate_issue_transition(issue=issue, target_state=states["todo"], actor_id=owner.id)
    issue.state = states["todo"]
    issue.save(update_fields=["state"])
    with patch("plane.bgtasks.webhook_task.workflow_transition_activity.delay"):
        dispatch_workflow_transition(forward, slug=project.workspace.slug, origin=None)

    reversal = validate_issue_transition(issue=issue, target_state=states["backlog"], actor_id=owner.id)

    assert reversal is not None
    assert reversal.is_reversal is True
    assert reversal.required_role is None
    assert ProjectWorkflowTransition.objects.filter(issue=issue, actor=owner).count() == 1
    assert any(
        transition["state_id"] == states["backlog"].id and transition["is_reversal"] is True
        for transition in available_transitions(issue, owner.id)
    )


def test_another_member_cannot_reverse_someone_elses_transition(workflow_project):
    owner, project, _configuration, states = workflow_project
    other_member = UserFactory(username="workflow-other-member")
    ProjectMember.objects.create(project=project, member=other_member, role=15)
    assign_role(project, owner, WorkflowRole.PRODUCT)
    issue = create_issue(project, states["backlog"])

    forward = validate_issue_transition(issue=issue, target_state=states["todo"], actor_id=owner.id)
    issue.state = states["todo"]
    issue.save(update_fields=["state"])
    with patch("plane.bgtasks.webhook_task.workflow_transition_activity.delay"):
        dispatch_workflow_transition(forward, slug=project.workspace.slug, origin=None)

    with pytest.raises(WorkflowTransitionError) as exception:
        validate_issue_transition(issue=issue, target_state=states["backlog"], actor_id=other_member.id)

    assert exception.value.code == "TRANSITION_NOT_ALLOWED"
