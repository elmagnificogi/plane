/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useMemo, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { v4 as uuidv4 } from "uuid";
import { useTranslation } from "@plane/i18n";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { TIntakeTemplate, TIntakeTemplateConfig } from "@plane/types";
import { CustomSelect, EModalPosition, EModalWidth, Input, ModalCore, TextArea, ToggleSwitch } from "@plane/ui";

type TProps = {
  isOpen: boolean;
  handleClose: () => void;
  config: TIntakeTemplateConfig;
  onSave: (config: TIntakeTemplateConfig) => Promise<void>;
};

const createTemplate = (description: string): TIntakeTemplate => ({
  id: uuidv4(),
  name: "",
  description,
});

const cloneConfig = (config: TIntakeTemplateConfig): TIntakeTemplateConfig => ({
  templates: config.templates.map(({ id, name, description }) => ({ id, name, description })),
  default_template_id: config.default_template_id,
});

export function IntakeTemplateSettingsModal(props: TProps) {
  const { isOpen, handleClose, config, onSave } = props;
  const { t } = useTranslation();
  const [draft, setDraft] = useState<TIntakeTemplateConfig>(() => cloneConfig(config));
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(config.templates[0]?.id ?? null);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    const nextDraft = cloneConfig(config);
    setDraft(nextDraft);
    setSelectedTemplateId(nextDraft.templates[0]?.id ?? null);
  }, [config, isOpen]);

  const selectedTemplate = useMemo(
    () => draft.templates.find((template) => template.id === selectedTemplateId),
    [draft.templates, selectedTemplateId]
  );

  const updateSelectedTemplate = (patch: Partial<TIntakeTemplate>) => {
    if (!selectedTemplateId) return;
    setDraft((current) => ({
      ...current,
      templates: current.templates.map((template) =>
        template.id === selectedTemplateId ? { ...template, ...patch } : template
      ),
    }));
  };

  const handleAdd = () => {
    const template = createTemplate(t("project_settings.features.intake.templates.starter_markdown"));
    setDraft((current) => ({ ...current, templates: [...current.templates, template] }));
    setSelectedTemplateId(template.id);
  };

  const handleDelete = () => {
    if (!selectedTemplateId) return;
    setDraft((current) => {
      const templates = current.templates.filter((template) => template.id !== selectedTemplateId);
      setSelectedTemplateId(templates[0]?.id ?? null);
      return {
        templates,
        default_template_id: current.default_template_id === selectedTemplateId ? null : current.default_template_id,
      };
    });
  };

  const handleSave = async () => {
    const names = draft.templates.map((template) => template.name.trim());
    if (names.some((name) => !name)) {
      setToast({ type: TOAST_TYPE.ERROR, title: t("error"), message: t("name_is_required") });
      return;
    }
    if (new Set(names.map((name) => name.toLocaleLowerCase())).size !== names.length) {
      setToast({ type: TOAST_TYPE.ERROR, title: t("error"), message: `${t("common.name")}: ${t("error")}` });
      return;
    }

    setIsSaving(true);
    try {
      await onSave({
        ...draft,
        templates: draft.templates.map((template) => ({ ...template, name: template.name.trim() })),
      });
    } catch {
      // The caller owns the error toast so the modal can stay open for corrections.
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <ModalCore isOpen={isOpen} handleClose={handleClose} position={EModalPosition.TOP} width={EModalWidth.XXXXL}>
      <div className="flex max-h-[80vh] flex-col bg-surface-1">
        <div className="flex items-center justify-between border-b border-subtle px-5 py-4">
          <div>
            <h3 className="text-18 font-medium text-primary">Intake {t("common.templates")}</h3>
            <p className="mt-1 text-12 text-secondary">{t("project_settings.features.intake.templates.description")}</p>
          </div>
          <Button variant="secondary" size="base" prependIcon={<Plus className="h-3.5 w-3.5" />} onClick={handleAdd}>
            {t("add")}
          </Button>
        </div>

        <div className="overflow-y-auto p-5">
          {draft.templates.length === 0 ? (
            <button
              type="button"
              className="flex min-h-40 w-full flex-col items-center justify-center gap-3 rounded-md border border-dashed border-subtle text-secondary hover:bg-surface-2"
              onClick={handleAdd}
            >
              <Plus className="h-5 w-5" />
              <span>
                {t("add")} {t("common.templates")}
              </span>
            </button>
          ) : (
            <div className="space-y-5">
              <div className="flex items-center gap-2">
                <CustomSelect
                  value={selectedTemplateId}
                  label={selectedTemplate?.name || t("common.templates")}
                  onChange={(value: string) => setSelectedTemplateId(value)}
                  buttonClassName="min-w-56 border border-subtle-1"
                  input
                >
                  {draft.templates.map((template) => (
                    <CustomSelect.Option key={template.id} value={template.id}>
                      {template.name || t("common.name")}
                      {draft.default_template_id === template.id ? ` · ${t("common.default")}` : ""}
                    </CustomSelect.Option>
                  ))}
                </CustomSelect>
                <Button
                  variant="secondary"
                  size="base"
                  prependIcon={<Trash2 className="h-3.5 w-3.5" />}
                  onClick={handleDelete}
                >
                  {t("delete")}
                </Button>
              </div>

              {selectedTemplate && (
                <div className="space-y-4 rounded-md border border-subtle p-4">
                  <label className="block space-y-1.5 text-12 text-secondary">
                    <span>{t("common.name")}</span>
                    <Input
                      value={selectedTemplate.name}
                      onChange={(event) => updateSelectedTemplate({ name: event.target.value })}
                      maxLength={100}
                      className="w-full"
                    />
                  </label>
                  <label className="block space-y-1.5 text-12 text-secondary">
                    <span>{t("common.description")}</span>
                    <TextArea
                      value={selectedTemplate.description}
                      onChange={(event) => updateSelectedTemplate({ description: event.target.value })}
                      maxLength={20000}
                      className="font-mono min-h-80 w-full resize-y"
                    />
                  </label>
                  <button
                    type="button"
                    className="flex items-center gap-2 text-13 text-primary"
                    onClick={() =>
                      setDraft((current) => ({
                        ...current,
                        default_template_id:
                          current.default_template_id === selectedTemplate.id ? null : selectedTemplate.id,
                      }))
                    }
                  >
                    <ToggleSwitch
                      value={draft.default_template_id === selectedTemplate.id}
                      onChange={() => {}}
                      size="sm"
                    />
                    {t("common.default")}
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 border-t border-subtle px-5 py-4">
          <Button variant="secondary" size="lg" onClick={handleClose}>
            {t("cancel")}
          </Button>
          <Button variant="primary" size="lg" loading={isSaving} onClick={handleSave}>
            {t("save")}
          </Button>
        </div>
      </div>
    </ModalCore>
  );
}
