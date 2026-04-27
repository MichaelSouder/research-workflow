"""
Grid API client: subjects, events, event details, subject-study.
"""

import logging
from datetime import datetime

import requests

log = logging.getLogger(__name__)


class GridClient:
    def __init__(self, api_token: str, population_id: str):
        self.base_url = f"https://lnpiapp.med.umn.edu/api/grid/studies/{population_id}"
        self.root_url = "https://lnpiapp.med.umn.edu/api/grid"
        self.api_token = api_token
        self.headers = {"Authorization": self.api_token}
        self.population_id = population_id

    def _get_event_template(
        self,
        subject_id: int,
        procedure_id: int,
        event_start: datetime,
        event_end: datetime,
        event_status: int,
        event_quality: int,
        note: str,
    ) -> dict:
        return {
            "study_id": self.population_id,
            "subject_id": subject_id,
            "procedure_id": procedure_id,
            "event_start_time": event_start,
            "event_end_time": event_end,
            "event_status": event_status,
            "event_quality": event_quality,
            "event_note": note,
            "key_person": "TicBot",
            "ignore": None,
            "created_by": "TicBot",
            "updated_by": None,
            "created_at": datetime.now().strftime("%Y-%m-%d"),
            "updated_at": datetime.now().strftime("%Y-%m-%d"),
            "lock_version": 0,
        }

    def _get_event_detail_template(
        self, description: str, event_id: int, datatype_id: int, json_data: str
    ) -> dict:
        return {
            "description": description,
            "event_id": event_id,
            "datatype_id": datatype_id,
            "prior_detail_id": 1,
            "json_data": json_data,
            "created_by": None,
            "updated_by": None,
            "created_at": None,
            "updated_at": None,
            "lock_version": None,
        }

    def _get_subject_template(
        self,
        contact_id: int,
        first_name: str,
        last_name: str,
        birthdate: datetime,
        sex: int,
        ssn: int,
        medical_record_number: str,
        research_status: str,
        race_id: int,
        ethnicity_id: int,
        note: str,
    ) -> dict:
        return {
            "contact_id": None,
            "first_name": first_name,
            "last_name": last_name,
            "date_of_birth": birthdate,
            "sex": sex,
            "ssn": ssn,
            "medical_record_number": medical_record_number,
            "research_status": research_status,
            "race_id": race_id,
            "ethnicity_id": ethnicity_id,
            "note": note,
            "created_by": "TicBot",
            "updated_by": "TicBot",
            "created_at": datetime.now().strftime("%Y-%m-%d"),
            "updated_at": datetime.now().strftime("%Y-%m-%d"),
            "lock_version": 0,
        }

    def _get_subject_study_template(
        self,
        subject_id: int,
        note: str,
        study_of_origin: str,
        study_entry_date: datetime,
        participant_status: int,
        group_id: int,
    ) -> dict:
        return {
            "subject_id": subject_id,
            "study_id": self.population_id,
            "note": note,
            "study_of_origin": study_of_origin,
            "study_entry_date": study_entry_date,
            "participant_status": participant_status,
            "group_id": group_id,
            "created_by": "TicBot",
            "updated_by": "TicBot",
            "created_at": datetime.now().strftime("%Y-%m-%d"),
            "updated_at": datetime.now().strftime("%Y-%m-%d"),
            "lock_version": 0,
        }

    def event_get(self, id: int) -> object:
        r = requests.get(f"{self.base_url}/events/{id}", headers=self.headers)
        try:
            return r.json()
        except Exception:
            log.error("Error: Could not decode JSON.")

    def event_get_all(self) -> list:
        r = requests.get(f"{self.base_url}/events/", headers=self.headers)
        try:
            return r.json()
        except Exception:
            log.error("Error: Could not decode JSON.")

    def event_create(self, data: dict) -> object:
        r = requests.post(f"{self.base_url}/events/", headers=self.headers, data=data)
        try:
            return r.json()
        except Exception:
            log.error("Error: Could not decode JSON.")

    def event_details_get(self, event_id: int, id: int) -> object:
        r = requests.get(f"{self.base_url}/events/{event_id}/details/{id}", headers=self.headers)
        try:
            return r.json()
        except Exception:
            log.error("Error: Could not decode JSON.")

    def event_details_get_all(self, event_id: int) -> list:
        r = requests.get(f"{self.base_url}/events/{event_id}/details/", headers=self.headers)
        try:
            return r.json()
        except Exception:
            log.error("Error: Could not decode JSON.")

    def event_details_create(self, event_id: int, data: dict) -> object:
        r = requests.post(
            f"{self.base_url}/events/{event_id}/details/",
            headers=self.headers,
            data=data,
        )
        try:
            return r.json()
        except Exception:
            log.error("Error: Could not decode JSON.")

    def subject_get(self, id: int) -> object:
        r = requests.get(f"{self.base_url}/subjects/{id}/", headers=self.headers)
        try:
            return r.json()
        except Exception:
            log.error("Error: Could not decode JSON.")

    def subject_get_by_last_name(self, last_name: str):
        r = requests.get(f"{self.base_url}/subjects?last_name={last_name}", headers=self.headers)
        try:
            return r.json()
        except Exception:
            log.error("Error: Could not decode JSON.")

    def subject_get_all(self) -> list:
        r = requests.get(f"{self.base_url}/subjects/", headers=self.headers)
        try:
            return r.json()
        except Exception:
            log.error("Error: Could not decode JSON.")

    def subject_create(self, data: dict) -> object:
        r = requests.post(f"{self.base_url}/subjects/", data=data, headers=self.headers)
        try:
            return r.json()
        except Exception:
            log.error("Error: Could not decode JSON.")

    def subject_study_get(self, id: int) -> object:
        r = requests.get(f"{self.root_url}/subjectstudies/{id}/", headers=self.headers)
        try:
            return r.json()
        except Exception:
            log.error("Error: Could not decode JSON.")

    def subject_study_get_all(self) -> list:
        r = requests.get(f"{self.root_url}/subjectstudies/", headers=self.headers)
        try:
            return r.json()
        except Exception:
            log.error("Error: Could not decode JSON.")

    def subject_study_create(self, data: dict) -> object:
        r = requests.post(f"{self.root_url}/subjectstudies/", data=data, headers=self.headers)
        try:
            return r.json()
        except Exception:
            log.error("Error: Could not decode JSON.")
