# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Cycle progress counts omit triage work items.

Triage items can stay linked to a cycle, but the cycle list does not show
them. Counting them in the total keeps progress below 100% after every
visible item is done or cancelled.
"""

from django.db.models import Q

TRIAGE_STATE_GROUP = "triage"

ISSUE_COUNT_GROUPS = (
    "backlog_issues",
    "unstarted_issues",
    "started_issues",
    "completed_issues",
    "cancelled_issues",
)

ESTIMATE_COUNT_GROUPS = (
    "backlog_estimate_points",
    "unstarted_estimate_points",
    "started_estimate_points",
    "completed_estimate_points",
    "cancelled_estimate_points",
)


def exclude_triage_issues(prefix: str = "issue_cycle__issue__") -> Q:
    return ~Q(**{f"{prefix}state__group": TRIAGE_STATE_GROUP})


def snapshot_without_triage(snapshot):
    """Drop triage from a stored progress snapshot.

    Group counts never include triage. The stored total can, because it
    counted every linked work item. Progress then uses the group sum.
    """
    if not isinstance(snapshot, dict) or not snapshot:
        return snapshot
    if not all(key in snapshot for key in ISSUE_COUNT_GROUPS):
        return snapshot

    updated = dict(snapshot)
    updated["total_issues"] = sum(int(snapshot.get(key) or 0) for key in ISSUE_COUNT_GROUPS)
    if all(key in snapshot for key in ESTIMATE_COUNT_GROUPS):
        updated["total_estimate_points"] = sum(float(snapshot.get(key) or 0) for key in ESTIMATE_COUNT_GROUPS)
    return updated


def strip_triage_from_cycle_payload(payload):
    if isinstance(payload, dict):
        if "progress_snapshot" in payload:
            payload["progress_snapshot"] = snapshot_without_triage(payload.get("progress_snapshot"))
        return payload
    if isinstance(payload, list):
        for item in payload:
            strip_triage_from_cycle_payload(item)
    return payload
