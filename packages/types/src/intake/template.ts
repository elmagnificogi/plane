/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export type TIntakeTemplate = {
  id: string;
  name: string;
  description: string;
};

export type TIntakeTemplateConfig = {
  templates: TIntakeTemplate[];
  default_template_id: string | null;
};

export type TIntake = {
  id: string;
  name: string;
  project: string;
  workspace: string;
  template_config: Partial<TIntakeTemplateConfig> | null;
};
