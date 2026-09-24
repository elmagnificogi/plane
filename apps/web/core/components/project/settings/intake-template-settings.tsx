/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import useSWR from "swr";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TIntake, TIntakeTemplateConfig } from "@plane/types";
import { Loader } from "@plane/ui";
import { IntakeTemplateSettingsModal } from "@/components/inbox/modals/template-settings-modal";
import { SettingsBoxedControlItem } from "@/components/settings/boxed-control-item";
import { IntakeService } from "@/services/inbox";

type TProps = {
  workspaceSlug: string;
  projectId: string;
};

const intakeService = new IntakeService();

const normalizeTemplateConfig = (intake?: TIntake): TIntakeTemplateConfig => ({
  templates: intake?.template_config?.templates ?? [],
  default_template_id: intake?.template_config?.default_template_id ?? null,
});

export function IntakeTemplateSettings({ workspaceSlug, projectId }: TProps) {
  const { t } = useTranslation();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const {
    data: intake,
    mutate,
    isLoading,
  } = useSWR<TIntake>(workspaceSlug && projectId ? `intake-${workspaceSlug}-${projectId}` : null, () =>
    intakeService.retrieve(workspaceSlug, projectId)
  );
  const templateConfig = normalizeTemplateConfig(intake);

  const handleSave = async (config: TIntakeTemplateConfig) => {
    if (!intake?.id) return;
    try {
      const updatedIntake = await intakeService.updateTemplateConfig(workspaceSlug, projectId, intake.id, config);
      await mutate(updatedIntake, false);
      setIsModalOpen(false);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: t("success"),
        message: t("project_settings.features.intake.templates.save_success"),
      });
    } catch (error) {
      console.error(error);
      setToast({
        type: TOAST_TYPE.ERROR,
        title: t("error"),
        message: t("project_settings.features.intake.templates.save_error"),
      });
      throw error;
    }
  };

  if (isLoading) {
    return (
      <Loader>
        <Loader.Item height="72px" />
      </Loader>
    );
  }
  if (!intake?.id) return null;

  return (
    <>
      <SettingsBoxedControlItem
        title={t("project_settings.features.intake.templates.title")}
        description={t("project_settings.features.intake.templates.description")}
        control={
          <Button variant="secondary" onClick={() => setIsModalOpen(true)}>
            {t("project_settings.features.intake.templates.manage")} ({templateConfig.templates.length})
          </Button>
        }
      />
      <IntakeTemplateSettingsModal
        isOpen={isModalOpen}
        handleClose={() => setIsModalOpen(false)}
        config={templateConfig}
        onSave={handleSave}
      />
    </>
  );
}
