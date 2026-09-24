---
cbd:
  target: packages/i18n/src/constants/language.ts
  kind: file
---

# Default interface language

Plane defaults to Simplified Chinese (`zh-CN`) when no explicit user or browser-stored preference exists. This applies to unauthenticated pages, first render, sign-out reset, and the initial client-side profile state.

New backend `Profile` records also default `language` to `zh-CN`, keeping the persisted preference aligned with the frontend fallback. Existing profiles keep their selected language and are not rewritten by the migration.
