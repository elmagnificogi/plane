/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import useSWR from "swr";
import { EUserPermissions, EUserPermissionsLevel } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { setPromiseToast } from "@plane/propel/toast";
import { Checkbox, Loader, ToggleSwitch } from "@plane/ui";
import { useUserPermissions } from "@/hooks/store/user";
import {
  projectWorkflowService,
  type TProjectWorkflowConfiguration,
  type TWorkflowAssignment,
  type TWorkflowRole,
} from "@/services/project";

const ROLE_LABEL_KEYS: Record<TWorkflowRole, string> = {
  product: "project_settings.lightweight_workflow.roles.product",
  developer: "project_settings.lightweight_workflow.roles.developer",
  tester: "project_settings.lightweight_workflow.roles.tester",
  project_manager: "project_settings.lightweight_workflow.roles.project_manager",
};

const MAIN_FLOW_KEYS = [
  "backlog",
  "todo",
  "in_progress",
  "waiting_for_test",
  "testing",
  "done_or_delayed_done",
] as const;

type TWorkflowSettingsProps = {
  workspaceSlug: string;
  projectId: string;
};

export function WorkflowSettings({ workspaceSlug, projectId }: TWorkflowSettingsProps) {
  const { t } = useTranslation();
  const { allowPermissions } = useUserPermissions();
  const isAdmin = allowPermissions([EUserPermissions.ADMIN], EUserPermissionsLevel.PROJECT, workspaceSlug, projectId);
  const { data, mutate, isLoading } = useSWR<TProjectWorkflowConfiguration>(
    workspaceSlug && projectId ? `project-workflow-${workspaceSlug}-${projectId}` : null,
    () => projectWorkflowService.getConfiguration(workspaceSlug, projectId)
  );
  const [assignments, setAssignments] = useState<TWorkflowAssignment[]>([]);

  useEffect(() => {
    if (data) setAssignments(data.assignments);
  }, [data]);

  const bootstrap = () => {
    const promise = projectWorkflowService.bootstrap(workspaceSlug, projectId);
    setPromiseToast(promise, {
      loading: t("project_settings.lightweight_workflow.toasts.bootstrap.loading"),
      success: {
        title: t("project_settings.lightweight_workflow.toasts.bootstrap.success_title"),
        message: () => t("project_settings.lightweight_workflow.toasts.bootstrap.success_message"),
      },
      error: {
        title: t("project_settings.lightweight_workflow.toasts.bootstrap.error_title"),
        message: () => t("project_settings.lightweight_workflow.toasts.bootstrap.error_message"),
      },
    });
    void promise.then((configuration) => mutate(configuration, false));
  };

  const toggleEnabled = (isEnabled: boolean) => {
    const promise = projectWorkflowService.update(workspaceSlug, projectId, { is_enabled: isEnabled });
    setPromiseToast(promise, {
      loading: t("project_settings.lightweight_workflow.toasts.toggle.loading"),
      success: {
        title: t("project_settings.lightweight_workflow.toasts.toggle.success_title"),
        message: () =>
          t(
            isEnabled
              ? "project_settings.lightweight_workflow.toasts.toggle.enabled_message"
              : "project_settings.lightweight_workflow.toasts.toggle.disabled_message"
          ),
      },
      error: {
        title: t("project_settings.lightweight_workflow.toasts.toggle.error_title"),
        message: () => t("project_settings.lightweight_workflow.toasts.toggle.error_message"),
      },
    });
    void promise.then((configuration) => mutate(configuration, false));
  };

  const toggleRole = (memberId: string, role: TWorkflowRole) => {
    setAssignments((current) =>
      current.map((assignment) => {
        if (assignment.member_id !== memberId) return assignment;
        const roles = assignment.roles.includes(role)
          ? assignment.roles.filter((item) => item !== role)
          : [...assignment.roles, role];
        return { ...assignment, roles };
      })
    );
  };

  const saveAssignments = () => {
    const promise = projectWorkflowService.update(workspaceSlug, projectId, {
      assignments: assignments.map(({ member_id, roles }) => ({ member_id, roles })),
    });
    setPromiseToast(promise, {
      loading: t("project_settings.lightweight_workflow.toasts.roles.loading"),
      success: {
        title: t("project_settings.lightweight_workflow.toasts.roles.success_title"),
        message: () => t("project_settings.lightweight_workflow.toasts.roles.success_message"),
      },
      error: {
        title: t("project_settings.lightweight_workflow.toasts.roles.error_title"),
        message: () => t("project_settings.lightweight_workflow.toasts.roles.error_message"),
      },
    });
    void promise.then((configuration) => mutate(configuration, false));
  };

  if (isLoading || !data) {
    return (
      <Loader className="space-y-3">
        <Loader.Item height="72px" />
        <Loader.Item height="180px" />
      </Loader>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-lg border border-subtle bg-surface-1 p-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-14 font-semibold">{t("project_settings.lightweight_workflow.fixed_flow.title")}</h3>
            <p className="mt-1 text-12 text-secondary">
              {t("project_settings.lightweight_workflow.fixed_flow.description")}
            </p>
          </div>
          {data.is_bootstrapped ? (
            <ToggleSwitch
              value={data.is_enabled}
              onChange={() => toggleEnabled(!data.is_enabled)}
              disabled={!isAdmin}
              size="sm"
            />
          ) : (
            <Button variant="primary" onClick={bootstrap} disabled={!isAdmin}>
              {t("project_settings.lightweight_workflow.actions.initialize_enable")}
            </Button>
          )}
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2 text-11">
          {MAIN_FLOW_KEYS.map((stateKey, index) => (
            <div key={stateKey} className="flex items-center gap-2">
              <span className="rounded border border-subtle bg-surface-2 px-2 py-1">
                {t(`project_settings.lightweight_workflow.states.${stateKey}`)}
              </span>
              {index < MAIN_FLOW_KEYS.length - 1 && <span className="text-tertiary">→</span>}
            </div>
          ))}
        </div>
        <p className="mt-3 text-11 text-tertiary">{t("project_settings.lightweight_workflow.fixed_flow.details")}</p>
      </div>

      {data.is_bootstrapped && (
        <div className="rounded-lg border border-subtle bg-surface-1">
          <div className="flex items-center justify-between border-b border-subtle px-4 py-3">
            <div>
              <h3 className="text-14 font-semibold">{t("project_settings.lightweight_workflow.roles.title")}</h3>
              <p className="mt-1 text-11 text-tertiary">
                {t("project_settings.lightweight_workflow.roles.description")}
              </p>
            </div>
            <Button variant="primary" onClick={saveAssignments} disabled={!isAdmin}>
              {t("project_settings.lightweight_workflow.actions.save_roles")}
            </Button>
          </div>
          <div className="divide-y divide-subtle">
            {assignments.map((assignment) => (
              <div key={assignment.member_id} className="grid gap-3 px-4 py-3 md:grid-cols-[minmax(180px,1fr)_2fr]">
                <div className="min-w-0">
                  <p className="truncate text-13 font-medium">{assignment.display_name || assignment.email}</p>
                  <p className="truncate text-11 text-tertiary">{assignment.email}</p>
                </div>
                <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
                  {(Object.keys(ROLE_LABEL_KEYS) as TWorkflowRole[]).map((role) => (
                    <label key={role} className="flex cursor-pointer items-center gap-2 text-12">
                      <Checkbox
                        checked={assignment.roles.includes(role)}
                        onChange={() => toggleRole(assignment.member_id, role)}
                        disabled={!isAdmin}
                      />
                      {t(ROLE_LABEL_KEYS[role])}
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="rounded-lg border border-subtle px-4 py-3 text-12 text-secondary">
        {t("project_settings.lightweight_workflow.webhook.prefix")} <code>issue</code>{" "}
        {t("project_settings.lightweight_workflow.webhook.middle")} <code>issue.workflow_transition</code>{" "}
        {t("project_settings.lightweight_workflow.webhook.suffix")}
      </div>
    </div>
  );
}
