# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from urllib.parse import urlparse

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from plane.db.models import FileAsset


@pytest.mark.contract
@pytest.mark.django_db
class TestLocalAssetStorage:
    def test_workspace_cover_uses_signed_local_upload(self, session_client, workspace, tmp_path):
        storage_settings = {
            "default": {
                "BACKEND": "django.core.files.storage.FileSystemStorage",
                "OPTIONS": {"location": str(tmp_path)},
            },
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        }
        cache_settings = {
            "default": {
                "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                "LOCATION": "local-asset-storage-test",
            }
        }
        content = b"\xff\xd8\xff\xe0local-cover"

        with override_settings(
            USE_LOCAL_FILE_STORAGE=True,
            STORAGES=storage_settings,
            CACHES=cache_settings,
        ):
            response = session_client.post(
                f"/api/assets/v2/workspaces/{workspace.slug}/",
                {
                    "name": "cover.jpg",
                    "type": "image/jpeg",
                    "size": len(content),
                    "entity_type": FileAsset.EntityTypeContext.PROJECT_COVER,
                    "entity_identifier": None,
                },
                format="json",
            )

            assert response.status_code == status.HTTP_200_OK
            assert response.data["upload_data"]["url"].endswith("/api/assets/v2/local-upload/")
            asset_id = response.data["asset_id"]

            upload_data = response.data["upload_data"]
            upload_client = APIClient()
            upload_response = upload_client.post(
                urlparse(upload_data["url"]).path,
                {
                    **upload_data["fields"],
                    "file": SimpleUploadedFile("cover.jpg", content, content_type="image/jpeg"),
                },
                format="multipart",
            )
            assert upload_response.status_code == status.HTTP_204_NO_CONTENT

            asset = FileAsset.objects.get(id=asset_id)
            assert asset.storage_metadata == {
                "ContentType": "image/jpeg",
                "ContentLength": len(content),
            }

            response = session_client.patch(
                f"/api/assets/v2/workspaces/{workspace.slug}/{asset_id}/",
                {},
                format="json",
            )
            assert response.status_code == status.HTTP_204_NO_CONTENT

            asset.refresh_from_db()
            assert asset.is_uploaded is True
            response = upload_client.get(asset.asset_url)
            assert response.status_code == status.HTTP_200_OK
            assert response.content == content
