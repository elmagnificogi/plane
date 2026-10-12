# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from plane.utils.cycle_stats import snapshot_without_triage


def test_snapshot_total_uses_counted_groups_so_triage_is_omitted():
    snapshot = {
        "total_issues": 16,
        "completed_issues": 15,
        "cancelled_issues": 0,
        "started_issues": 0,
        "unstarted_issues": 0,
        "backlog_issues": 0,
        "total_estimate_points": 8,
        "completed_estimate_points": 5,
        "cancelled_estimate_points": 0,
        "started_estimate_points": 0,
        "unstarted_estimate_points": 0,
        "backlog_estimate_points": 0,
    }

    result = snapshot_without_triage(snapshot)

    assert result["total_issues"] == 15
    assert result["completed_issues"] == 15
    assert result["total_estimate_points"] == 5
    assert snapshot["total_issues"] == 16


def test_snapshot_without_group_counts_is_left_unchanged():
    snapshot = {"total_issues": 3, "distribution": {}}

    assert snapshot_without_triage(snapshot) is snapshot
    assert snapshot_without_triage({}) == {}
    assert snapshot_without_triage(None) is None
