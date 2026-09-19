# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import transaction
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import ROLE, allow_permission
from plane.app.views.base import BaseAPIView
from plane.db.models import (
    Issue,
    Project,
    ProjectMember,
    ProjectWorkflowConfiguration,
    ProjectWorkflowRole,
    State,
    WorkflowRole,
)
from plane.utils.workflow import (
    DEFECT_TRANSITIONS,
    MAIN_TRANSITIONS,
    available_transitions,
    bootstrap_project_workflow,
)


def _serialize_configuration(project: Project):
    configuration = ProjectWorkflowConfiguration.objects.filter(project=project).first()
    assignments = ProjectWorkflowRole.objects.filter(project=project).select_related("member")
    grouped_roles = {}
    for assignment in assignments:
        member = assignment.member
        entry = grouped_roles.setdefault(
            str(member.id),
            {
                "member_id": str(member.id),
                "email": member.email,
                "display_name": member.display_name,
                "roles": [],
            },
        )
        entry["roles"].append(assignment.role)

    for membership in ProjectMember.objects.filter(project=project, is_active=True).select_related("member"):
        member = membership.member
        if member is None:
            continue
        grouped_roles.setdefault(
            str(member.id),
            {
                "member_id": str(member.id),
                "email": member.email,
                "display_name": member.display_name,
                "roles": [],
            },
        )

    if configuration is None:
        return {
            "is_bootstrapped": False,
            "is_enabled": False,
            "schema_version": None,
            "state_mapping": {},
            "states": {},
            "labels": {"defect": None, "blocking": None},
            "assignments": list(grouped_roles.values()),
            "available_roles": [{"key": value, "label": label} for value, label in WorkflowRole.choices],
        }

    states = {
        str(state.id): {"id": str(state.id), "name": state.name, "group": state.group, "color": state.color}
        for state in State.objects.filter(id__in=configuration.state_mapping.values())
    }
    semantic_states = {key: states.get(str(state_id)) for key, state_id in configuration.state_mapping.items()}
    return {
        "is_bootstrapped": True,
        "is_enabled": configuration.is_enabled,
        "schema_version": configuration.schema_version,
        "state_mapping": configuration.state_mapping,
        "states": semantic_states,
        "labels": {
            "defect": str(configuration.defect_label_id) if configuration.defect_label_id else None,
            "blocking": str(configuration.blocking_label_id) if configuration.blocking_label_id else None,
        },
        "assignments": list(grouped_roles.values()),
        "available_roles": [{"key": value, "label": label} for value, label in WorkflowRole.choices],
        "policy": {
            "project_manager_can_transition_to_any_configured_state": True,
            "main": [
                {"from": source, "to": target, "role": role} for (source, target), role in MAIN_TRANSITIONS.items()
            ],
            "defect": [
                {"from": source, "to": target, "role": role} for (source, target), role in DEFECT_TRANSITIONS.items()
            ],
        },
    }


class ProjectWorkflowEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        return Response(_serialize_configuration(project), status=status.HTTP_200_OK)

    @allow_permission([ROLE.ADMIN])
    def post(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        bootstrap_project_workflow(project, actor_id=request.user.id)
        return Response(_serialize_configuration(project), status=status.HTTP_201_CREATED)

    @allow_permission([ROLE.ADMIN])
    def patch(self, request, slug, project_id):
        project = Project.objects.get(pk=project_id, workspace__slug=slug)
        configuration = ProjectWorkflowConfiguration.objects.filter(project=project).first()
        if configuration is None:
            return Response(
                {"error": "请先初始化项目状态流转。"},
                status=status.HTTP_409_CONFLICT,
            )

        assignments = request.data.get("assignments")
        valid_roles = set(WorkflowRole.values)
        normalized_assignments = []
        if assignments is not None:
            if not isinstance(assignments, list):
                return Response({"assignments": "必须是数组。"}, status=status.HTTP_400_BAD_REQUEST)

            seen_members = set()
            for assignment in assignments:
                member_id = str(assignment.get("member_id", ""))
                roles = assignment.get("roles", [])
                if member_id in seen_members:
                    return Response(
                        {"assignments": f"成员 {member_id} 重复。"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if not isinstance(roles, list) or any(role not in valid_roles for role in roles):
                    return Response(
                        {"assignments": f"成员 {member_id} 包含无效业务角色。"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                seen_members.add(member_id)
                normalized_assignments.append((member_id, sorted(set(roles))))

            active_members = set(
                str(member_id)
                for member_id in ProjectMember.objects.filter(
                    project=project,
                    is_active=True,
                    member_id__in=seen_members,
                ).values_list("member_id", flat=True)
            )
            missing_members = seen_members - active_members
            if missing_members:
                return Response(
                    {"assignments": f"以下成员不属于项目：{', '.join(sorted(missing_members))}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        with transaction.atomic():
            if "is_enabled" in request.data:
                if not isinstance(request.data["is_enabled"], bool):
                    return Response({"is_enabled": "必须是布尔值。"}, status=status.HTTP_400_BAD_REQUEST)
                configuration.is_enabled = request.data["is_enabled"]
                configuration.save(update_fields=["is_enabled", "updated_at"])

            if assignments is not None:
                ProjectWorkflowRole.objects.filter(project=project).delete()
                ProjectWorkflowRole.objects.bulk_create(
                    [
                        ProjectWorkflowRole(
                            project=project,
                            workspace=project.workspace,
                            member_id=member_id,
                            role=role,
                            created_by=request.user,
                        )
                        for member_id, roles in normalized_assignments
                        for role in roles
                    ]
                )

        return Response(_serialize_configuration(project), status=status.HTTP_200_OK)


class IssueWorkflowTransitionsEndpoint(BaseAPIView):
    @allow_permission([ROLE.ADMIN, ROLE.MEMBER, ROLE.GUEST])
    def get(self, request, slug, project_id, issue_id):
        issue = Issue.issue_objects.get(pk=issue_id, project_id=project_id, workspace__slug=slug)
        is_enabled = ProjectWorkflowConfiguration.objects.filter(
            project_id=project_id,
            is_enabled=True,
        ).exists()
        transitions = available_transitions(issue, request.user.id)
        state_ids = [transition["state_id"] for transition in transitions if transition.get("state_id")]
        state_details = {
            str(state.id): {"id": str(state.id), "name": state.name, "group": state.group, "color": state.color}
            for state in State.objects.filter(id__in=state_ids)
        }
        for transition in transitions:
            transition["state"] = state_details.get(str(transition["state_id"]))
        return Response(
            {
                "is_enabled": is_enabled,
                "transitions": transitions,
            },
            status=status.HTTP_200_OK,
        )
