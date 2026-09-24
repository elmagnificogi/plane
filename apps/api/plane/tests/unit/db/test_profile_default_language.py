# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.db.models import Profile


@pytest.mark.unit
def test_profile_language_defaults_to_simplified_chinese():
    assert Profile._meta.get_field("language").default == "zh-CN"
