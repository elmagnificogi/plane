# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
import requests

from plane.bgtasks.webhook_task import webhook_send_task


def _webhook():
    return SimpleNamespace(
        id=uuid4(),
        workspace_id=uuid4(),
        secret_key="",
        url="https://example.com/webhook",
    )


def _response(status_code: int):
    return SimpleNamespace(status_code=status_code, headers={}, text=f"HTTP {status_code}")


def _run_delivery(webhook):
    webhook_send_task._orig_run(
        webhook_id=str(webhook.id),
        slug="workflow-demo",
        event="issue",
        event_data={"id": str(uuid4())},
        action="POST",
        current_site="http://plane.example.com",
        activity=None,
    )


@pytest.mark.unit
def test_transport_failure_is_retried_without_disabling_webhook():
    webhook = _webhook()

    with (
        patch("plane.bgtasks.webhook_task.Webhook.objects.get", return_value=webhook),
        patch("plane.bgtasks.webhook_task.Webhook.objects.filter") as webhook_filter,
        patch(
            "plane.bgtasks.webhook_task.pinned_fetch",
            side_effect=requests.ConnectionError("temporarily unavailable"),
        ),
        patch("plane.bgtasks.webhook_task.save_webhook_log") as save_log,
        pytest.raises(requests.ConnectionError),
    ):
        _run_delivery(webhook)

    webhook_filter.assert_not_called()
    save_log.assert_called_once()
    assert save_log.call_args.kwargs["response_status"] == 500


@pytest.mark.unit
@pytest.mark.parametrize("status_code", [408, 425, 429, 500, 503])
def test_transient_http_status_is_retried_without_disabling_webhook(status_code):
    webhook = _webhook()

    with (
        patch("plane.bgtasks.webhook_task.Webhook.objects.get", return_value=webhook),
        patch("plane.bgtasks.webhook_task.Webhook.objects.filter") as webhook_filter,
        patch("plane.bgtasks.webhook_task.pinned_fetch", return_value=_response(status_code)),
        patch("plane.bgtasks.webhook_task.save_webhook_log") as save_log,
        pytest.raises(requests.RequestException),
    ):
        _run_delivery(webhook)

    webhook_filter.assert_not_called()
    save_log.assert_called_once()
    assert save_log.call_args.kwargs["response_status"] == status_code


@pytest.mark.unit
def test_permanent_client_error_is_logged_without_retrying_or_disabling_webhook():
    webhook = _webhook()

    with (
        patch("plane.bgtasks.webhook_task.Webhook.objects.get", return_value=webhook),
        patch("plane.bgtasks.webhook_task.Webhook.objects.filter") as webhook_filter,
        patch("plane.bgtasks.webhook_task.pinned_fetch", return_value=_response(400)),
        patch("plane.bgtasks.webhook_task.save_webhook_log") as save_log,
    ):
        _run_delivery(webhook)

    webhook_filter.assert_not_called()
    save_log.assert_called_once()
    assert save_log.call_args.kwargs["response_status"] == 400
