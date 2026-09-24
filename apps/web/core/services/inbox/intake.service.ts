/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import type { TIntake, TIntakeTemplateConfig } from "@plane/types";
import { APIService } from "@/services/api.service";

export class IntakeService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async retrieve(workspaceSlug: string, projectId: string): Promise<TIntake> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/intakes/`)
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async updateTemplateConfig(
    workspaceSlug: string,
    projectId: string,
    intakeId: string,
    templateConfig: TIntakeTemplateConfig
  ): Promise<TIntake> {
    return this.patch(`/api/workspaces/${workspaceSlug}/projects/${projectId}/intakes/${intakeId}/`, {
      template_config: templateConfig,
    })
      .then((response) => response?.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}
