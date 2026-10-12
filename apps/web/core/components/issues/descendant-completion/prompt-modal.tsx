/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { useTranslation } from "@plane/i18n";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import { AlertModalCore } from "@plane/ui";
import {
  isDescendantCompletionPromptOpen,
  resolveDescendantCompletionPrompt,
  subscribeDescendantCompletionFailures,
  subscribeDescendantCompletionPrompt,
} from "./prompt";

export function DescendantCompletionPromptModal() {
  const { t } = useTranslation();
  const [isOpen, setIsOpen] = useState(isDescendantCompletionPromptOpen);

  useEffect(
    () =>
      subscribeDescendantCompletionPrompt(() => {
        setIsOpen(isDescendantCompletionPromptOpen());
      }),
    []
  );

  useEffect(
    () =>
      subscribeDescendantCompletionFailures((names) => {
        setToast({
          type: TOAST_TYPE.ERROR,
          title: t("project_settings.lightweight_workflow.descendant_completion.failure_title"),
          message: t("project_settings.lightweight_workflow.descendant_completion.failure_message", {
            names: names.join(", "),
          }),
        });
      }),
    [t]
  );

  return (
    <AlertModalCore
      handleClose={() => resolveDescendantCompletionPrompt(false)}
      handleSubmit={() => resolveDescendantCompletionPrompt(true)}
      isSubmitting={false}
      isOpen={isOpen}
      variant="primary"
      title={t("project_settings.lightweight_workflow.descendant_completion.title")}
      content={t("project_settings.lightweight_workflow.descendant_completion.content")}
      primaryButtonText={{
        loading: t("project_settings.lightweight_workflow.descendant_completion.confirm"),
        default: t("project_settings.lightweight_workflow.descendant_completion.confirm"),
      }}
      secondaryButtonText={t("project_settings.lightweight_workflow.descendant_completion.decline")}
    />
  );
}
