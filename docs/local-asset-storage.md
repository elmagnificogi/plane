---
cbd:
  target: apps/api/plane/app/views/asset/v2.py
  kind: file
---

# Local asset storage

Plane's V2 asset flow normally creates a database record, returns an S3 or MinIO presigned form, uploads the file to object storage, and then marks the record as uploaded.

The single-machine `plane.settings.workflow_local` deployment intentionally has no S3 or MinIO service. It enables `USE_LOCAL_FILE_STORAGE`, which preserves the same client flow while replacing the object-storage form with a short-lived, cryptographically signed API upload form.

- The upload signature binds the asset ID and server-generated storage key.
- The anonymous upload endpoint is unavailable unless local file storage is explicitly enabled.
- Uploaded bytes are written through Django's configured `default_storage` and remain subject to Plane's file-size limit.
- Metadata is stored before the normal authenticated completion request, so no S3 metadata task is needed.
- Public avatar, logo, and project-cover URLs serve the local file with `nosniff`; script-capable MIME types remain downloads.

Production and container deployments continue to use their existing S3 or MinIO presigned-upload behavior.
