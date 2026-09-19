# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from plane.bgtasks.webhook_task import workflow_transition_activity


@pytest.mark.unit
def test_workflow_transition_activity_sends_structured_issue_event():
    issue_id = str(uuid4())
    actor_id = str(uuid4())
    from_state_id = str(uuid4())
    to_state_id = str(uuid4())
    webhook_id = uuid4()
    transition = {
        "configuration_id": str(uuid4()),
        "schema_version": 1,
        "track": "main",
        "from_key": "testing",
        "to_key": "done",
        "from_state_id": from_state_id,
        "to_state_id": to_state_id,
        "required_role": "product",
    }

    states = [
        SimpleNamespace(id=from_state_id, name="测试中", group="started"),
        SimpleNamespace(id=to_state_id, name="Done", group="completed"),
    ]

    def model_data(*, event, event_id):
        return {"id": str(event_id), "event": event}

    with (
        patch("plane.bgtasks.webhook_task.get_model_data", side_effect=model_data),
        patch("plane.bgtasks.webhook_task.State.objects.filter", return_value=states),
        patch(
            "plane.bgtasks.webhook_task.Webhook.objects.filter",
            return_value=[SimpleNamespace(id=webhook_id)],
        ),
        patch("plane.bgtasks.webhook_task.webhook_send_task.delay") as send,
    ):
        workflow_transition_activity.run(
            issue_id=issue_id,
            actor_id=actor_id,
            slug="workflow-demo",
            current_site="http://127.0.0.1:8000",
            transition=transition,
        )

    send.assert_called_once_with(
        webhook_id=webhook_id,
        slug="workflow-demo",
        event="issue.workflow_transition",
        event_data={"id": issue_id, "event": "issue"},
        action="update",
        current_site="http://127.0.0.1:8000",
        activity={
            "field": "state_id",
            "old_value": {"id": from_state_id, "name": "测试中", "group": "started"},
            "new_value": {"id": to_state_id, "name": "Done", "group": "completed"},
            "actor": {"id": actor_id, "event": "user"},
            "workflow": transition,
        },
    )
