---
cbd:
  target: apps/api/plane/db/models/intake.py
  kind: file
---

# Intake 工作项模板

每个项目的 Intake 在 `template_config` JSON 字段中保存最多 20 个模板和一个可选的默认模板。旧数据迁移后该字段为空对象，因此不改变已有 Intake 和工作项的行为，也不要求重建 Plane 数据。

模板只保存模板名称和 Markdown 内容，管理入口仅位于“项目设置 → 功能 → Intake”。创建弹窗会把 Markdown 转为富文本描述，用户仍可修改、切换到“不使用模板”，也可改用其他模板。工作项标题和 Plane 属性始终由提交者填写。

状态不属于模板。Intake 后端仍统一把新工作项放入 Triage，避免模板绕过现有状态流转权限。

项目管理员可以维护模板；项目成员和访客只能读取并使用模板。后端会校验模板 ID、名称、内容长度和默认模板引用。
