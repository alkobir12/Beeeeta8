import os
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Scopes
SCOPES = [
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/spreadsheets",
]


class GoogleService:
    def __init__(self):
        self.creds = None
        self.drive_service = None
        self.sheets_service = None
        self._authenticate()

    def _authenticate(self):
        # Service Account is the only supported auth path (server-side).
        # Note: Legacy pickle-based OAuth token loading was removed for security
        # (pickle.load on a file is an arbitrary-code-execution risk).
        sa_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        if sa_file and os.path.exists(sa_file):
            try:
                self.creds = Credentials.from_service_account_file(
                    sa_file, scopes=SCOPES
                )
                print("✅ Authenticated with Service Account")
            except Exception as e:
                print(f"❌ Service Account Auth failed: {e}")

        # Refresh if expired
        if self.creds and getattr(self.creds, "expired", False) and getattr(self.creds, "refresh_token", None):
            self.creds.refresh(Request())

        if self.creds:
            self.drive_service = build("drive", "v3", credentials=self.creds)
            self.sheets_service = build("sheets", "v4", credentials=self.creds)
        else:
            print("⚠️ No valid Google Credentials found.")

    def upload_file(self, file_path: str, folder_id: str = None, mime_type: str = None):
        if not self.drive_service:
            return None

        file_name = os.path.basename(file_path)
        file_metadata = {"name": file_name}
        if folder_id:
            file_metadata["parents"] = [folder_id]

        media = MediaFileUpload(file_path, mimetype=mime_type)

        try:
            file = (
                self.drive_service.files()
                .create(body=file_metadata, media_body=media, fields="id")
                .execute()
            )
            return file.get("id")
        except Exception as e:
            print(f"Upload failed: {e}")
            return None

    def append_to_sheet(self, spreadsheet_id: str, range_name: str, values: list):
        if not self.sheets_service:
            return None

        body = {"values": values}

        try:
            result = (
                self.sheets_service.spreadsheets()
                .values()
                .append(
                    spreadsheetId=spreadsheet_id,
                    range=range_name,
                    valueInputOption="USER_ENTERED",
                    body=body,
                )
                .execute()
            )
            return result
        except Exception as e:
            print(f"Sheet append failed: {e}")
            return None

    def create_folder(self, folder_name: str, parent_id: str = None):
        if not self.drive_service:
            return None

        file_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            file_metadata["parents"] = [parent_id]

        try:
            file = (
                self.drive_service.files()
                .create(body=file_metadata, fields="id")
                .execute()
            )
            return file.get("id")
        except Exception as e:
            print(f"Create folder failed: {e}")
            return None
