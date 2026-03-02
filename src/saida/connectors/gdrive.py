from __future__ import annotations

import io
import os
from typing import Any

from saida.connectors.base import BaseConnector


class GoogleDriveConnector(BaseConnector):
    name = "gdrive"

    def __init__(
        self,
        folder_id: str | None = None,
        page_size: int = 100,
        service: Any | None = None,
        credentials_path: str | None = None,
        token_path: str | None = None,
        scopes: list[str] | None = None,
        downloader_cls: Any | None = None,
    ):
        self.folder_id = folder_id
        self.page_size = page_size
        self._service = service
        self.credentials_path = credentials_path or os.getenv("SAIDA_GDRIVE_CREDENTIALS_PATH")
        self.token_path = token_path or os.getenv("SAIDA_GDRIVE_TOKEN_PATH")
        self.scopes = scopes or ["https://www.googleapis.com/auth/drive.readonly"]
        self._downloader_cls = downloader_cls

    def _get_downloader_cls(self):
        if self._downloader_cls is not None:
            return self._downloader_cls
        from googleapiclient.http import MediaIoBaseDownload

        return MediaIoBaseDownload

    def _get_service(self) -> Any:
        if self._service is not None:
            return self._service

        from google.oauth2.credentials import Credentials
        from google.oauth2.service_account import Credentials as ServiceAccountCredentials
        from googleapiclient.discovery import build

        if self.credentials_path:
            creds = ServiceAccountCredentials.from_service_account_file(self.credentials_path, scopes=self.scopes)
        elif self.token_path:
            creds = Credentials.from_authorized_user_file(self.token_path, scopes=self.scopes)
        else:
            raise RuntimeError(
                "GoogleDriveConnector requires service injection or credentials path/token path."
            )

        self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self._service

    def _query(self) -> str:
        if self.folder_id:
            return f"'{self.folder_id}' in parents and trashed = false"
        return "trashed = false"

    def discover(self) -> list[str]:
        service = self._get_service()
        files_api = service.files()
        ids: list[str] = []
        token: str | None = None
        while True:
            response = (
                files_api.list(
                    q=self._query(),
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                    pageSize=self.page_size,
                    pageToken=token,
                ).execute()
            )
            ids.extend([str(item["id"]) for item in response.get("files", []) if item.get("id")])
            token = response.get("nextPageToken")
            if not token:
                break
        return ids

    def load(self, resource_id: str) -> Any:
        service = self._get_service()
        files_api = service.files()
        metadata = files_api.get(fileId=resource_id, fields="id,name,mimeType,modifiedTime,size").execute()
        mime_type = metadata.get("mimeType", "")

        if mime_type.startswith("application/vnd.google-apps."):
            content = self._export_native_doc(files_api, resource_id, mime_type)
        else:
            request = files_api.get_media(fileId=resource_id)
            buffer = io.BytesIO()
            downloader = self._get_downloader_cls()(buffer, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
            content = buffer.getvalue()

        return {"metadata": metadata, "content": content}

    def _export_native_doc(self, files_api: Any, resource_id: str, mime_type: str) -> bytes:
        export_map = {
            "application/vnd.google-apps.document": "text/plain",
            "application/vnd.google-apps.spreadsheet": "text/csv",
            "application/vnd.google-apps.presentation": "text/plain",
            "application/vnd.google-apps.drawing": "image/png",
        }
        export_mime = export_map.get(mime_type, "text/plain")
        request = files_api.export_media(fileId=resource_id, mimeType=export_mime)
        buffer = io.BytesIO()
        downloader = self._get_downloader_cls()(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue()

    def get_metadata(self) -> dict:
        return {
            "type": "gdrive",
            "folder_id": self.folder_id,
            "page_size": self.page_size,
        }
