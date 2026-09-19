/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { API_BASE_URL } from "@plane/constants";
import { APIService } from "@/services/api.service";

export type TWorkflowRole = "product" | "developer" | "tester" | "project_manager";

export type TWorkflowAssignment = {
  member_id: string;
  email: string;
  display_name: string;
  roles: TWorkflowRole[];
};

export type TWorkflowState = {
  id: string;
  name: string;
  group: string;
  color: string;
};

export type TProjectWorkflowConfiguration = {
  is_bootstrapped: boolean;
  is_enabled: boolean;
  schema_version: number | null;
  state_mapping: Record<string, string>;
  states: Record<string, TWorkflowState | null>;
  labels: { defect: string | null; blocking: string | null };
  assignments: TWorkflowAssignment[];
  available_roles: { key: TWorkflowRole; label: string }[];
};

export type TIssueWorkflowTransition = {
  state_key: string | null;
  state_id: string;
  required_role: TWorkflowRole | null;
  track: "main" | "defect";
  is_reversal: boolean;
  state: TWorkflowState | null;
};

export type TIssueWorkflowTransitions = {
  is_enabled: boolean;
  transitions: TIssueWorkflowTransition[];
};

export class ProjectWorkflowService extends APIService {
  constructor() {
    super(API_BASE_URL);
  }

  async getConfiguration(workspaceSlug: string, projectId: string): Promise<TProjectWorkflowConfiguration> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/workflow/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async bootstrap(workspaceSlug: string, projectId: string): Promise<TProjectWorkflowConfiguration> {
    return this.post(`/api/workspaces/${workspaceSlug}/projects/${projectId}/workflow/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async update(
    workspaceSlug: string,
    projectId: string,
    data: { is_enabled?: boolean; assignments?: Pick<TWorkflowAssignment, "member_id" | "roles">[] }
  ): Promise<TProjectWorkflowConfiguration> {
    return this.patch(`/api/workspaces/${workspaceSlug}/projects/${projectId}/workflow/`, data)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }

  async getAvailableTransitions(
    workspaceSlug: string,
    projectId: string,
    issueId: string
  ): Promise<TIssueWorkflowTransitions> {
    return this.get(`/api/workspaces/${workspaceSlug}/projects/${projectId}/issues/${issueId}/workflow-transitions/`)
      .then((response) => response.data)
      .catch((error) => {
        throw error?.response?.data;
      });
  }
}

export const projectWorkflowService = new ProjectWorkflowService();
