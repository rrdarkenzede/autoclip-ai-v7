import os
import json
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2 import service_account
import io

log = logging.getLogger("AutoClipAI.Cloud")

# Configuration from Environment
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
        """Lists files in the stockpile folder, ordered by creation time (Oldest first)."""
        if not self.service: return []
        
        folder_id = folder_id or STOCKPILE_FOLDER_ID
        if not folder_id:
            log.warning("⚠️ No STOCKPILE_FOLDER_ID configured.")
            return []
            
        query = f"'{folder_id}' in parents and trashed = false"
        try:
            results = self.service.files().list(
                q=query, 
                fields="files(id, name, createdTime)",
                orderBy="createdTime",
                pageSize=100
            ).execute()
            files = results.get('files', [])
            log.info(f"📦 Stockpile status: {len(files)} items found in folder {folder_id}.")
            return files
        except Exception as e:
            log.error(f"❌ Failed to list Drive files: {e}")
            return []

    def get_oldest_stockpile_video_and_metadata(self):
        """Finds oldest .mp4 and its matching .json on Drive."""
        files = self.list_files()
        if not files: return None, None, None
            
        oldest_mp4 = next((f for f in files if f['name'].lower().endswith('.mp4')), None)
        if not oldest_mp4:
            log.info("ℹ️ No .mp4 files found in Stockpile.")
            return None, None, None
            
        base_name = os.path.splitext(oldest_mp4['name'])[0]
        # Search for matching .json
        matching_json = next((f for f in files if f['name'].lower() == f"{base_name.lower()}.json"), None)
        
        log.info(f"🎯 Oldest candidate detected: {oldest_mp4['name']} (created: {oldest_mp4.get('createdTime')})")
        return oldest_mp4['id'], (matching_json['id'] if matching_json else None), base_name

    def download_file(self, file_id, dest_path):
        """Downloads a file from Drive to local path."""
        if not self.service: return False
        try:
            request = self.service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            with open(dest_path, 'wb') as f:
                f.write(fh.getvalue())
            return True
        except Exception as e:
            log.error(f"❌ Download failed for {file_id}: {e}")
            return False

    def delete_file(self, file_id):
        """Deletes a file from Drive."""
        if not self.service or not file_id: return
        try:
            self.service.files().delete(fileId=file_id).execute()
            log.info(f"🗑️ Deleted file ID {file_id} from Drive.")
        except Exception as e:
            log.error(f"❌ Delete failed for {file_id}: {e}")

# Global Instance
drive_manager = GoogleDriveManager()
