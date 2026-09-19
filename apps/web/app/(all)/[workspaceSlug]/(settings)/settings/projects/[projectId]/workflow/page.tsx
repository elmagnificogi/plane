/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useTranslation } from "@plane/i18n";
import { PageHead } from "@/components/core/page-title";
import { WorkflowSettings } from "@/components/project/settings/workflow-settings";
import { SettingsContentWrapper } from "@/components/settings/content-wrapper";
import { SettingsHeading } from "@/components/settings/heading";
import { useProject } from "@/hooks/store/use-project";
import type { Route } from "./+types/page";
import { WorkflowProjectSettingsHeader } from "./header";

function WorkflowSettingsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  const { currentProjectDetails } = useProject();
  const { t } = useTranslation();
  const pageTitle = currentProjectDetails?.name
    ? `${currentProjectDetails.name} - ${t("project_settings.lightweight_workflow.label")}`
    : undefined;

  return (
    <SettingsContentWrapper header={<WorkflowProjectSettingsHeader />}>
      <PageHead title={pageTitle} />
      <SettingsHeading
        title={t("project_settings.lightweight_workflow.label")}
        description={t("project_settings.lightweight_workflow.page_description")}
      />
      <div className="mt-6">
        <WorkflowSettings workspaceSlug={workspaceSlug} projectId={projectId} />
      </div>
    </SettingsContentWrapper>
  );
}

export default observer(WorkflowSettingsPage);
