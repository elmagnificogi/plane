# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
from uuid import UUID

# Third party frameworks
from rest_framework import serializers

# Module imports
from .base import BaseSerializer
from .issue import IssueIntakeSerializer, LabelLiteSerializer, IssueDetailSerializer
from .project import ProjectLiteSerializer
from .state import StateLiteSerializer
from .user import UserLiteSerializer
from plane.db.models import Intake, IntakeIssue, Issue, StateGroup, State


class IntakeSerializer(BaseSerializer):
    project_detail = ProjectLiteSerializer(source="project", read_only=True)
    pending_issue_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Intake
        fields = "__all__"
        read_only_fields = ["project", "workspace"]

    def validate_template_config(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("Template configuration must be an object.")

        templates = value.get("templates", [])
        default_template_id = value.get("default_template_id")
        if not isinstance(templates, list):
            raise serializers.ValidationError("Templates must be a list.")
        if len(templates) > 20:
            raise serializers.ValidationError("An intake can contain at most 20 templates.")

        normalized_templates = []
        template_ids = set()
        template_names = set()

        for raw_template in templates:
            if not isinstance(raw_template, dict):
                raise serializers.ValidationError("Each template must be an object.")

            try:
                template_id = str(UUID(str(raw_template.get("id"))))
            except (TypeError, ValueError, AttributeError) as exc:
                raise serializers.ValidationError("Each template must have a valid ID.") from exc
            if template_id in template_ids:
                raise serializers.ValidationError("Template IDs must be unique.")
            template_ids.add(template_id)

            name = raw_template.get("name", "")
            if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
                raise serializers.ValidationError("Template names must contain 1 to 100 characters.")
            name = name.strip()
            normalized_name = name.casefold()
            if normalized_name in template_names:
                raise serializers.ValidationError("Template names must be unique.")
            template_names.add(normalized_name)

            description = raw_template.get("description", "")
            if not isinstance(description, str) or len(description) > 20000:
                raise serializers.ValidationError("Template descriptions must be text up to 20,000 characters.")

            normalized_templates.append(
                {
                    "id": template_id,
                    "name": name,
                    "description": description,
                }
            )

        if default_template_id is not None:
            try:
                default_template_id = str(UUID(str(default_template_id)))
            except (TypeError, ValueError, AttributeError) as exc:
                raise serializers.ValidationError("Default template ID is invalid.") from exc
            if default_template_id not in template_ids:
                raise serializers.ValidationError("Default template must refer to an existing template.")

        return {"templates": normalized_templates, "default_template_id": default_template_id}


class IntakeIssueSerializer(BaseSerializer):
    issue = IssueIntakeSerializer(read_only=True)

    class Meta:
        model = IntakeIssue
        fields = [
            "id",
            "status",
            "duplicate_to",
            "snoozed_till",
            "source",
            "issue",
            "created_by",
        ]
        read_only_fields = ["project", "workspace"]

    def validate(self, attrs):
        """
        Validate that if status is being changed to accepted (1),
        the project has a default state to transition to.
        """

        # Check if status is being updated to accepted
        if attrs.get("status") == 1:
            intake_issue = self.instance
            issue = intake_issue.issue

            # Check if issue is in TRIAGE state
            if issue.state and issue.state.group == StateGroup.TRIAGE.value:
                # Verify default state exists before allowing the update
                default_state = State.objects.filter(
                    workspace=intake_issue.workspace, project=intake_issue.project, default=True
                ).first()

                if not default_state:
                    raise serializers.ValidationError(
                        {"status": "Cannot accept intake issue: No default state found for the project"}
                    )

        return attrs

    def update(self, instance, validated_data):
        # Update the intake issue
        instance = super().update(instance, validated_data)

        # If status is accepted (1), transition the issue state from TRIAGE to default
        if validated_data.get("status") == 1:
            issue = instance.issue
            if issue.state and issue.state.group == StateGroup.TRIAGE.value:
                # Get the default project state
                default_state = State.objects.filter(
                    workspace=instance.workspace, project=instance.project, default=True
                ).first()
                if default_state:
                    issue.state = default_state
                    issue.save()

        return instance

    def to_representation(self, instance):
        # Pass the annotated fields to the Issue instance if they exist
        if hasattr(instance, "label_ids"):
            instance.issue.label_ids = instance.label_ids
        return super().to_representation(instance)


class IntakeIssueDetailSerializer(BaseSerializer):
    issue = IssueDetailSerializer(read_only=True)
    duplicate_issue_detail = IssueIntakeSerializer(read_only=True, source="duplicate_to")

    class Meta:
        model = IntakeIssue
        fields = [
            "id",
            "status",
            "duplicate_to",
            "snoozed_till",
            "duplicate_issue_detail",
            "source",
            "issue",
        ]
        read_only_fields = ["project", "workspace"]

    def to_representation(self, instance):
        # Pass the annotated fields to the Issue instance if they exist
        if hasattr(instance, "assignee_ids"):
            instance.issue.assignee_ids = instance.assignee_ids
        if hasattr(instance, "label_ids"):
            instance.issue.label_ids = instance.label_ids

        return super().to_representation(instance)


class IntakeIssueLiteSerializer(BaseSerializer):
    class Meta:
        model = IntakeIssue
        fields = ["id", "status", "duplicate_to", "snoozed_till", "source"]
        read_only_fields = fields


class IssueStateIntakeSerializer(BaseSerializer):
    state_detail = StateLiteSerializer(read_only=True, source="state")
    project_detail = ProjectLiteSerializer(read_only=True, source="project")
    label_details = LabelLiteSerializer(read_only=True, source="labels", many=True)
    assignee_details = UserLiteSerializer(read_only=True, source="assignees", many=True)
    sub_issues_count = serializers.IntegerField(read_only=True)
    issue_intake = IntakeIssueLiteSerializer(read_only=True, many=True)

    class Meta:
        model = Issue
        fields = "__all__"
