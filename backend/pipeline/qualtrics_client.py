"""
Qualtrics API client: export responses, retrieve video info, download media.
"""

import io
import json
import logging
import os
import zipfile

import requests

from backend.pipeline.config import QUALTRICS_DIR, WORKSPACE_DIR

log = logging.getLogger(__name__)


class QualtricsClient:
    def __init__(
        self, api_token: str, survey_id: str, data_center: str, workspace_dir: str, video_dir: str
    ):
        self.api_token = api_token
        self.survey_id = survey_id
        self.data_center = data_center
        self.workspace_dir = workspace_dir
        self.video_dir = video_dir

    def check_new(self):
        return

    def download_media_file(self, response_id: int, file_id: int, label: str) -> bytes | None:
        url = f"https://{self.data_center}.qualtrics.com/API/v3/surveys/{self.survey_id}/responses/{response_id}/uploaded-files/{file_id}"
        log.info("Qualtrics: Downloading video for response %s, file %s", response_id, file_id)
        headers = {
            "Accept": "application/octet-stream, application/json",
            "X-API-TOKEN": self.api_token,
        }
        file_name = f"{file_id}.mp4"
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            video_dir_path = os.path.join(WORKSPACE_DIR, self.video_dir)
            os.makedirs(video_dir_path, exist_ok=True)
            with open(os.path.join(video_dir_path, file_name), "wb") as f:
                f.write(response.content)
            log.info("Qualtrics: Video downloaded successfully: %s", file_name)
            return response.content
        log.warning(
            "Qualtrics: Failed to download file %s — status %s: %s",
            file_id,
            response.status_code,
            response.text[:200],
        )
        return None

    def download_survey_responses(self) -> str:
        request_progress = 0.0
        progress_status = "inProgress"
        base_url = f"https://{self.data_center}.qualtrics.com/API/v3/surveys/{self.survey_id}/export-responses/"
        headers = {
            "content-type": "application/json",
            "x-api-token": self.api_token,
        }
        log.info("Qualtrics: Requesting survey export (JSON format)...")
        download_request_response = requests.post(
            base_url, data='{"format":"json"}', headers=headers
        )
        progress_id = download_request_response.json()["result"]["progressId"]
        log.info("Qualtrics: Export in progress (progressId=%s)", progress_id)
        while progress_status != "complete" and progress_status != "failed":
            request_check_response = requests.get(base_url + progress_id, headers=headers)
            request_progress = request_check_response.json()["result"]["percentComplete"]
            log.info("Qualtrics: Download is %s%% complete", request_progress)
            progress_status = request_check_response.json()["result"]["status"]
        if progress_status == "failed":
            raise Exception("Qualtrics export failed!")
        file_id = request_check_response.json()["result"]["fileId"]
        log.info("Qualtrics: Export complete. Downloading file %s...", file_id)
        request_download = requests.get(base_url + file_id + "/file", headers=headers, stream=True)
        os.makedirs(QUALTRICS_DIR, exist_ok=True)
        zipfile.ZipFile(io.BytesIO(request_download.content)).extractall(QUALTRICS_DIR)
        json_files = [f for f in os.listdir(QUALTRICS_DIR) if f.endswith(".json")]
        if not json_files:
            raise FileNotFoundError(f"No JSON file found in {QUALTRICS_DIR} after export")
        export_json_path = os.path.join(QUALTRICS_DIR, json_files[0])
        log.info("Qualtrics: Complete. Extracted export to %s", export_json_path)
        return export_json_path

    def retrieve_videos_info(
        self, ids: list[str], file_name: str, download: bool = False
    ) -> list[dict]:
        with open(file_name) as f:
            data = json.load(f)
        responses = data["responses"]
        files_info = []
        for response in responses:
            file_info = {}
            for val in response["values"]:
                if val.startswith("QID") and val.endswith("FILE_ID"):
                    file_info["responseId"] = response["responseId"]
                    file_info[val] = response["values"][val]
                    file_id = response["values"][val]
                    response_id = response["responseId"]
                    label = response["values"][val]
                    if download:
                        self.download_media_file(response_id, file_id, label)
                elif val in ids:
                    file_info[val] = response["values"][val]
            if file_info:
                files_info.append(file_info)
        return files_info
