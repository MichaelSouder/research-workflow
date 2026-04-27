"""
Box SDK wrapper: list folders, create folder, upload files.
"""

import logging
import os

from boxsdk import Client, JWTAuth

log = logging.getLogger(__name__)


class BoxClient:
    def __init__(self, settings_file_path: str):
        self.auth = JWTAuth.from_settings_file(settings_file_path)
        self.access_token = self.auth.authenticate_instance()
        self.client = Client(self.auth)

    def create_folder(self, root_folder_id: str, new_folder_name: str) -> object:
        return self.client.folder(root_folder_id).create_subfolder(new_folder_name)

    def list_folders(self):
        return self.client.folder("0")

    def list_folder_items(self, root_id: str):
        items = self.client.folder(root_id).get_items(limit=None)
        folders = [item for item in items if item.type == "folder"]
        log.info("Box: Found %s folder(s) in root %s", len(folders), root_id)
        for item in folders:
            log.info("Box:   — %s (ID: %s)", item.name, item.id)

    def upload(self, folder_id: str, file_path: str, file_name: str):
        folder = self.client.folder(folder_id).get()
        result = folder.upload(file_path, file_name)
        log.info("Box: Upload complete: %s -> folder %s", file_name, folder_id)
        return result

    @staticmethod
    def cleanup_directory(dir_path: str):
        try:
            os.rmdir(dir_path)
            log.info("Directory '%s' deleted successfully.", dir_path)
        except FileNotFoundError:
            log.info("Directory '%s' not found.", dir_path)
        except OSError:
            log.info("Directory '%s' is not empty.", dir_path)

    def delete_box_folder(self, folder_id: str):
        self.client.folder(folder_id).delete(recursive=True)
