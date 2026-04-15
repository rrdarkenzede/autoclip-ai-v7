import os
import json
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2 import service_account
import io

log = logging.getLogger("AutoClipAI.Cloud")

# Configuration from Environment
# In GH Actions/Colab, we set these via secrets or environment variables
DRIVE_CREDENTIALS_JSON = os.environ.get("GOOGLE_DRIVE_CREDENTIALS")
STOCKPILE_FOLDER_ID = os.environ.get("GOOGLE_DRIVE_FOLDER_ID") # The 'Stockpile' on Drive

class GoogleDriveManager:
    def __init__(self):
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """Authenticates using Service Account JSON from environment variable."""
        try:
            if not DRIVE_CREDENTIALS_JSON:
                log.warning("⚠️ GOOGLE_DRIVE_CREDENTIALS not found. Cloud storage DISABLED.")
                return

            creds_data = json.loads(DRIVE_CREDENTIALS_JSON)
            creds = service_account.Credentials.from_service_account_info(
                creds_data,
                scopes=['https://www.googleapis.com/auth/drive']
            )
            self.service = build('drive', 'v3', credentials=creds)
            log.info("✅ Google Drive Authentication SUCCESS.")
        except Exception as e:
            log.error(f"❌ Drive Auth Error: {e}")

    def upload_file(self, local_path, folder_id=None):
        """Uploads a file to a specific Google Drive folder."""
        if not self.service: return None
        
        folder_id = folder_id or STOCKPILE_FOLDER_ID
        filename = os.path.basename(local_path)
        
        file_metadata = {'name': filename}
        if folder_id:
            file_metadata['parents'] = [folder_id]

        media = MediaFileUpload(local_path, resumable=True)
        try:
            file = self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            log.info(f"📤 Uploaded {filename} to Drive (ID: {file.get('id')})")
            return file.get('id')
        except Exception as e:
            log.error(f"❌ Upload failed: {e}")
            return None

    def list_files(self, folder_id=None):
        """Lists files in the stockpile folder."""
        if not self.service: return []
        
        folder_id = folder_id or STOCKPILE_FOLDER_ID
        query = f"'{folder_id}' in parents and trashed = false"
        try:
            results = self.service.files().list(q=query, fields="files(id, name)").execute()
            return results.get('files', [])
        except Exception as e:
            log.error(f"❌ Failed to list Drive files: {e}")
            return []

    def download_file(self, file_id, dest_path):
        """Downloads a file from Drive to local path."""
        if not self.service: return False
        
        request = self.service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        try:
            while done is False:
                status, done = downloader.next_chunk()
            
            with open(dest_path, 'wb') as f:
                f.write(fh.getvalue())
            return True
        except Exception as e:
            log.error(f"❌ Download failed: {e}")
            return False

    def delete_file(self, file_id):
        """Deletes a file from Drive."""
        if not self.service: return
        try:
            self.service.files().delete(fileId=file_id).execute()
        except Exception as e:
            log.error(f"❌ Delete failed: {e}")

# Global Instance
drive_manager = GoogleDriveManager()
