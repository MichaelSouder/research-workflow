"""
Qualtrics distribution and mailing list (qualtrics_util-style).
Uses config dict (env-like); no backend imports. Caller injects config from study or env.
"""

import json
import logging
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from backend.pipeline.config import QUALTRICS_DIR, WORKSPACE_DIR

log = logging.getLogger(__name__)


def _config(config_override: dict[str, str] | None = None) -> dict[str, str]:
    """Merge override with os.environ and pipeline.config defaults."""
    from backend.pipeline import config as pipeline_config

    out = {}
    keys = [
        "QUALTRICS_API_TOKEN",
        "QUALTRICS_SURVEY_ID",
        "QUALTRICS_DATA_CENTER",
        "QUALTRICS_DIRECTORY_ID",
        "QUALTRICS_MAILING_LIST_ID",
        "QUALTRICS_LIBRARY_ID",
        "QUALTRICS_MESSAGE_ID_SMS",
        "QUALTRICS_MESSAGE_ID_EMAIL",
        "QUALTRICS_CONTACT_METHOD",
        "QUALTRICS_DISTRIBUTION_TIMEZONE",
        "QUALTRICS_DISTRIBUTION_TIME_SLOTS",
        "QUALTRICS_DISTRIBUTION_EXPIRE_MINUTES",
    ]
    for k in keys:
        v = (config_override or {}).get(k) or os.environ.get(k) or getattr(pipeline_config, k, None)
        out[k] = (v or "") if isinstance(v, str) else str(v) if v is not None else ""
    return out


def _base_url(c: dict[str, str]) -> str:
    dc = (c.get("QUALTRICS_DATA_CENTER") or "yul1").strip()
    return f"https://{dc}.qualtrics.com/API/v3"


def _headers(c: dict[str, str]) -> dict[str, str]:
    token = c.get("QUALTRICS_API_TOKEN", "").strip()
    if not token or token == "********":
        raise ValueError("QUALTRICS_API_TOKEN is not set or masked.")
    return {"x-api-token": token, "content-type": "application/json"}


def _validate_timezone(tz_str: str) -> None:
    """Raise if tz_str is not a valid IANA timezone."""
    if not tz_str or not tz_str.strip():
        raise ValueError("Timezone is empty.")
    try:
        ZoneInfo(tz_str.strip())
    except Exception as e:
        raise ValueError(f"Invalid timezone '{tz_str}': {e}") from e


def _parse_time_slots(slots_json: str) -> list[tuple[int, int]]:
    """Parse QUALTRICS_DISTRIBUTION_TIME_SLOTS JSON e.g. [[800,900],[1200,1300]]. Returns list of (start, end) 24h times."""
    if not slots_json or not slots_json.strip():
        return []
    try:
        raw = json.loads(slots_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid time slots JSON: {e}") from e
    if not isinstance(raw, list):
        raise ValueError("Time slots must be a JSON array.")
    result = []
    for i, item in enumerate(raw):
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError(f"Time slot {i} must be [start, end].")
        start, end = int(item[0]), int(item[1])
        if start < 0 or start > 2400 or end < 0 or end > 2400:
            raise ValueError(f"Time slot {i}: start and end must be 0-2400 (24h).")
        if start >= end:
            raise ValueError(f"Time slot {i}: start must be less than end.")
        result.append((start, end))
    return result


def _embedded_flag(emb: dict, key: str, default: str = "") -> str:
    """Get embedded data value as string; support common truthy values."""
    v = emb.get(key, default)
    if v is None:
        return default or ""
    return (v if isinstance(v, str) else str(v)).strip()


def list_distributions(config_override: dict[str, str] | None = None) -> dict:
    """
    List email and SMS distributions for the configured survey/mailing list.
    Returns { "email": [...], "sms": [...] } with elements containing id, status, recipients, etc.
    """
    c = _config(config_override)
    base = _base_url(c)
    headers = _headers(c)
    survey_id = (c.get("QUALTRICS_SURVEY_ID") or "").strip()
    mailing_list_id = (c.get("QUALTRICS_MAILING_LIST_ID") or "").strip()
    if not survey_id:
        return {"email": [], "sms": [], "errors": ["QUALTRICS_SURVEY_ID is required."]}

    out: dict = {"email": [], "sms": [], "errors": []}

    r = requests.get(
        f"{base}/distributions",
        headers=headers,
        params={"surveyId": survey_id, "mailingListId": mailing_list_id, "distributionRequestType": "Invite"},
        timeout=30,
    )
    if r.status_code == 200:
        out["email"] = r.json().get("result", {}).get("elements", [])
    else:
        out["errors"].append(f"Email distributions: {r.status_code}")

    r2 = requests.get(f"{base}/distributions/sms", headers=headers, params={"surveyId": survey_id}, timeout=30)
    if r2.status_code == 200:
        out["sms"] = r2.json().get("result", {}).get("elements", [])
    else:
        out["errors"].append(f"SMS distributions: {r2.status_code}")

    return out


def send_preview(config_override: dict[str, str] | None = None) -> dict:
    """
    Return which contacts would be sent to (same logic as send_distributions, but no actual send).
    Returns { "count": int, "contacts": [ { "index", "id", "name", "email", "phone" }, ... ], "inTimeSlot": bool }.
    """
    c = _config(config_override)
    _validate_timezone(c.get("QUALTRICS_DISTRIBUTION_TIMEZONE", ""))
    slots = _parse_time_slots(c.get("QUALTRICS_DISTRIBUTION_TIME_SLOTS", "[]"))
    contacts = get_contact_list(c, include_embedded=True)
    method = (c.get("QUALTRICS_CONTACT_METHOD") or "email").strip().lower()

    in_time_slot = True
    if slots:
        from datetime import datetime

        tz_str = (c.get("QUALTRICS_DISTRIBUTION_TIMEZONE") or "America/Chicago").strip()
        now = datetime.now(ZoneInfo(tz_str)).time()
        now_minutes = now.hour * 60 + now.minute
        in_time_slot = False
        for start, end in slots:
            start_min = (start // 100) * 60 + (start % 100)
            end_min = (end // 100) * 60 + (end % 100)
            if start_min <= now_minutes < end_min:
                in_time_slot = True
                break

    eligible: list[dict] = []
    for i, contact in enumerate(contacts):
        emb = contact.get("embeddedData") or {}
        if _embedded_flag(emb, "SurveysSchedule") != "0":
            continue
        use_sms = _embedded_flag(emb, "UseSMS") == "1"
        use_email = _embedded_flag(emb, "UseEmail") == "1"
        if method == "sms" and not use_sms:
            continue
        if method == "email" and not use_email:
            continue
        if not contact.get("id"):
            continue
        eligible.append({
            "index": i,
            "id": contact.get("id"),
            "name": f"{contact.get('firstName', '')} {contact.get('lastName', '')}".strip(),
            "email": contact.get("email") or "",
            "phone": contact.get("phone") or "",
        })
    return {"count": len(eligible), "contacts": eligible, "inTimeSlot": in_time_slot}


def get_contact_list(config_override: dict[str, str] | None = None, include_embedded: bool = True) -> list[dict]:
    """
    List all contacts in the configured mailing list. Handles pagination.
    Returns list of contact dicts (id, firstName, lastName, email, phone, embeddedData, etc.).
    """
    c = _config(config_override)
    base = _base_url(c)
    headers = _headers(c)
    directory_id = (c.get("QUALTRICS_DIRECTORY_ID") or "").strip()
    mailing_list_id = (c.get("QUALTRICS_MAILING_LIST_ID") or "").strip()
    if not directory_id or not mailing_list_id:
        raise ValueError("QUALTRICS_DIRECTORY_ID and QUALTRICS_MAILING_LIST_ID are required.")
    url = f"{base}/directories/{directory_id}/mailinglists/{mailing_list_id}/contacts"
    params = {"includeEmbedded": "true"} if include_embedded else {}
    contacts: list[dict] = []
    while url:
        r = requests.get(url, headers=headers, params=params, timeout=60)
        params = {}
        if r.status_code != 200:
            try:
                body = r.json()
                msg = body.get("meta", {}).get("error", {}).get("errorMessage", r.text)
            except Exception:
                msg = r.text[:500]
            raise RuntimeError(f"Qualtrics contacts list failed: {r.status_code} — {msg}")
        data = r.json()
        contacts.extend(data.get("result", {}).get("elements", []))
        url = data.get("result", {}).get("nextPage")
        if url and not url.startswith("http"):
            url = f"{base.rstrip('/API/v3')}{url}" if url.startswith("/") else url
    return contacts


def check_ids(config_override: dict[str, str] | None = None) -> dict:
    """
    Validate survey ID, mailing list ID, and message ID(s). Return { "ok": bool, "details": {...}, "errors": [...] }.
    """
    c = _config(config_override)
    base = _base_url(c)
    headers = _headers(c)
    errors: list[str] = []
    details: dict[str, str] = {}

    survey_id = (c.get("QUALTRICS_SURVEY_ID") or "").strip()
    if survey_id:
        try:
            r = requests.get(f"{base}/surveys/{survey_id}", headers=headers, timeout=30)
            if r.status_code == 200:
                details["survey"] = "ok"
            else:
                errors.append(f"Survey {survey_id}: {r.status_code}")
        except Exception as e:
            errors.append(f"Survey: {e}")
    else:
        errors.append("QUALTRICS_SURVEY_ID is empty.")

    directory_id = (c.get("QUALTRICS_DIRECTORY_ID") or "").strip()
    mailing_list_id = (c.get("QUALTRICS_MAILING_LIST_ID") or "").strip()
    if directory_id and mailing_list_id:
        try:
            r = requests.get(
                f"{base}/directories/{directory_id}/mailinglists/{mailing_list_id}",
                headers=headers,
                timeout=30,
            )
            if r.status_code == 200:
                details["mailing_list"] = "ok"
            else:
                errors.append(f"Mailing list: {r.status_code}")
        except Exception as e:
            errors.append(f"Mailing list: {e}")
    else:
        if not directory_id:
            errors.append("QUALTRICS_DIRECTORY_ID is empty.")
        if not mailing_list_id:
            errors.append("QUALTRICS_MAILING_LIST_ID is empty.")

    method = (c.get("QUALTRICS_CONTACT_METHOD") or "email").strip().lower()
    lib_id = (c.get("QUALTRICS_LIBRARY_ID") or "").strip()
    if method == "sms":
        msg_id = (c.get("QUALTRICS_MESSAGE_ID_SMS") or "").strip()
    else:
        msg_id = (c.get("QUALTRICS_MESSAGE_ID_EMAIL") or "").strip()
    if lib_id and msg_id:
        try:
            r = requests.get(
                f"{base}/libraries/{lib_id}/messages/{msg_id}",
                headers=headers,
                timeout=30,
            )
            if r.status_code == 200:
                details["message"] = "ok"
            else:
                errors.append(f"Message ({method}): {r.status_code}")
        except Exception as e:
            errors.append(f"Message: {e}")
    else:
        if not lib_id:
            errors.append("QUALTRICS_LIBRARY_ID is empty.")
        if not msg_id:
            errors.append(f"QUALTRICS_MESSAGE_ID_{'SMS' if method == 'sms' else 'EMAIL'} is empty.")

    return {"ok": len(errors) == 0, "details": details, "errors": errors}


def send_distributions(
    config_override: dict[str, str] | None = None,
    *,
    contact_indices: list[int] | None = None,
    limit: int | None = None,
    bypass_time_slot: bool = False,
    expire_minutes_override: int | None = None,
) -> dict:
    """
    Send distributions for contacts where SurveysSchedule=0 and contact method matches.
    Returns { "sent": int, "errors": list[str] }. Respects time slots unless bypass_time_slot=True.

    Optional:
      contact_indices: if set, only consider these contact list indices (0-based).
      limit: max number of distributions to send (None = no limit).
      bypass_time_slot: if True, send regardless of QUALTRICS_DISTRIBUTION_TIME_SLOTS.
      expire_minutes_override: override config expiration (minutes).
    """
    c = _config(config_override)
    _validate_timezone(c.get("QUALTRICS_DISTRIBUTION_TIMEZONE", ""))
    slots = [] if bypass_time_slot else _parse_time_slots(c.get("QUALTRICS_DISTRIBUTION_TIME_SLOTS", "[]"))
    contacts = get_contact_list(c, include_embedded=True)
    method = (c.get("QUALTRICS_CONTACT_METHOD") or "email").strip().lower()
    survey_id = (c.get("QUALTRICS_SURVEY_ID") or "").strip()
    directory_id = (c.get("QUALTRICS_DIRECTORY_ID") or "").strip()
    mailing_list_id = (c.get("QUALTRICS_MAILING_LIST_ID") or "").strip()
    lib_id = (c.get("QUALTRICS_LIBRARY_ID") or "").strip()
    if method == "sms":
        message_id = (c.get("QUALTRICS_MESSAGE_ID_SMS") or "").strip()
    else:
        message_id = (c.get("QUALTRICS_MESSAGE_ID_EMAIL") or "").strip()
    if not survey_id or not directory_id or not mailing_list_id or not lib_id or not message_id:
        return {"sent": 0, "errors": ["Missing required config: survey, directory, mailing list, library, message ID."]}

    base = _base_url(c)
    headers = _headers(c)
    expire_minutes = (
        expire_minutes_override
        if expire_minutes_override is not None
        else int(c.get("QUALTRICS_DISTRIBUTION_EXPIRE_MINUTES") or "10080")
    )
    sent = 0
    errors: list[str] = []
    index_set = None if contact_indices is None else set(contact_indices)

    for i, contact in enumerate(contacts):
        if index_set is not None and i not in index_set:
            continue
        if limit is not None and sent >= limit:
            break
        emb = contact.get("embeddedData") or {}
        if _embedded_flag(emb, "SurveysSchedule") != "0":
            continue
        use_sms = _embedded_flag(emb, "UseSMS") == "1"
        use_email = _embedded_flag(emb, "UseEmail") == "1"
        if method == "sms" and not use_sms:
            continue
        if method == "email" and not use_email:
            continue
        contact_id = contact.get("id")
        if not contact_id:
            continue
        if slots:
            from datetime import datetime

            tz_str = (c.get("QUALTRICS_DISTRIBUTION_TIMEZONE") or "America/Chicago").strip()
            now = datetime.now(ZoneInfo(tz_str)).time()
            now_minutes = now.hour * 60 + now.minute
            in_slot = False
            for start, end in slots:
                start_min = (start // 100) * 60 + (start % 100)
                end_min = (end // 100) * 60 + (end % 100)
                if start_min <= now_minutes < end_min:
                    in_slot = True
                    break
            if not in_slot:
                continue
        if method == "sms":
            payload = {
                "surveyId": survey_id,
                "messageId": message_id,
                "recipients": [{"contactId": contact_id}],
                "expirationMinutes": expire_minutes,
            }
            r = requests.post(f"{base}/distributions/sms", headers=headers, json=payload, timeout=30)
        else:
            payload = {
                "surveyId": survey_id,
                "mailingListId": mailing_list_id,
                "message": {"libraryId": lib_id, "messageId": message_id},
                "recipients": [{"contactId": contact_id}],
                "expirationMinutes": expire_minutes,
            }
            r = requests.post(f"{base}/distributions", headers=headers, json=payload, timeout=30)
        if r.status_code in (200, 201):
            sent += 1
        else:
            try:
                err = r.json().get("meta", {}).get("error", {}).get("errorMessage", r.text[:200])
            except Exception:
                err = r.text[:200]
            errors.append(f"Contact {contact_id}: {err}")
    return {"sent": sent, "errors": errors}


def delete_unsent(
    config_override: dict[str, str] | None = None,
    *,
    contact_index: int | None = None,
    contact_id: str | None = None,
    all_unsent: bool = False,
) -> dict:
    """
    Delete unsent distributions.
    Targeting: contact_index (list index), or contact_id (Qualtrics id), or all_unsent=True (all unsent),
    or else contacts with embeddedData.DeleteUnsent=1.
    Returns { "deleted": int, "errors": list[str] }.
    """
    c = _config(config_override)
    base = _base_url(c)
    headers = _headers(c)
    survey_id = (c.get("QUALTRICS_SURVEY_ID") or "").strip()
    mailing_list_id = (c.get("QUALTRICS_MAILING_LIST_ID") or "").strip()
    if not survey_id:
        return {"deleted": 0, "errors": ["QUALTRICS_SURVEY_ID is required."]}

    contacts = get_contact_list(c, include_embedded=True)
    if contact_index is not None:
        if contact_index < 0 or contact_index >= len(contacts):
            return {"deleted": 0, "errors": [f"Invalid contact index: {contact_index}."]}
        contact_ids = {contacts[contact_index]["id"]}
    elif contact_id:
        contact_ids = {contact_id.strip()}
    elif all_unsent:
        contact_ids = {co["id"] for co in contacts if co.get("id")}
    else:
        contact_ids = {
            co["id"] for co in contacts
            if _embedded_flag(co.get("embeddedData") or {}, "DeleteUnsent") == "1"
        }

    if not contact_ids:
        return {"deleted": 0, "errors": []}

    deleted = 0
    errors: list[str] = []

    # List email distributions for this survey + mailing list
    r = requests.get(
        f"{base}/distributions",
        headers=headers,
        params={"surveyId": survey_id, "mailingListId": mailing_list_id, "distributionRequestType": "Invite"},
        timeout=30,
    )
    if r.status_code != 200:
        errors.append(f"List distributions: {r.status_code}")
        return {"deleted": 0, "errors": errors}
    dist_list = r.json().get("result", {}).get("elements", [])

    for d in dist_list:
        if d.get("status") != "Not Sent":
            continue
        rec = d.get("recipients", {}).get("mailingListId")
        if rec != mailing_list_id:
            continue
        for elem in d.get("recipients", {}).get("elements", []) or []:
            if elem.get("contactId") in contact_ids:
                dist_id = d.get("id")
                if dist_id:
                    dr = requests.delete(f"{base}/distributions/{dist_id}", headers=headers, timeout=30)
                    if dr.status_code in (200, 204):
                        deleted += 1
                    else:
                        errors.append(f"Delete distribution {dist_id}: {dr.status_code}")
                break

    # List SMS distributions
    r2 = requests.get(f"{base}/distributions/sms", headers=headers, params={"surveyId": survey_id}, timeout=30)
    if r2.status_code == 200:
        sms_list = r2.json().get("result", {}).get("elements", [])
        for d in sms_list:
            if d.get("status") != "Not Sent":
                continue
            for elem in d.get("recipients", {}).get("elements", []) or []:
                if elem.get("contactId") in contact_ids:
                    sms_id = d.get("id")
                    if sms_id:
                        dr = requests.delete(
                            f"{base}/distributions/sms/{sms_id}",
                            headers=headers,
                            params={"surveyId": survey_id},
                            timeout=30,
                        )
                        if dr.status_code in (200, 204):
                            deleted += 1
                        else:
                            errors.append(f"Delete SMS distribution {sms_id}: {dr.status_code}")
                    break

    return {"deleted": deleted, "errors": errors}


def update_embedded(
    config_override: dict[str, str] | None = None,
    contact_id: str = "",
    update_fields: dict | None = None,
) -> None:
    """Update embedded data for a contact. contact_id required; update_fields merged into embeddedData."""
    if not contact_id or not update_fields:
        raise ValueError("contact_id and update_fields are required.")
    c = _config(config_override)
    base = _base_url(c)
    headers = _headers(c)
    directory_id = (c.get("QUALTRICS_DIRECTORY_ID") or "").strip()
    mailing_list_id = (c.get("QUALTRICS_MAILING_LIST_ID") or "").strip()
    if not directory_id or not mailing_list_id:
        raise ValueError("QUALTRICS_DIRECTORY_ID and QUALTRICS_MAILING_LIST_ID are required.")
    url = f"{base}/directories/{directory_id}/mailinglists/{mailing_list_id}/contacts/{contact_id}"
    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        try:
            msg = r.json().get("meta", {}).get("error", {}).get("errorMessage", r.text)
        except Exception:
            msg = r.text[:500]
        raise RuntimeError(f"Get contact failed: {r.status_code} — {msg}")
    contact = r.json().get("result", {})
    embedded = dict(contact.get("embeddedData") or {})
    embedded.update(update_fields)
    payload = {"embeddedData": embedded}
    r2 = requests.put(url, headers=headers, json=payload, timeout=30)
    if r2.status_code != 200:
        try:
            msg = r2.json().get("meta", {}).get("error", {}).get("errorMessage", r2.text)
        except Exception:
            msg = r2.text[:500]
        raise RuntimeError(f"Update contact failed: {r2.status_code} — {msg}")


def export_surveys(config_override: dict[str, str] | None = None, file_format: str = "json") -> str:
    """
    Export survey responses. file_format: "json" or "csv". Returns path to extracted file.
    Reuses Qualtrics export API; writes to QUALTRICS_DIR.
    """
    if file_format not in ("json", "csv"):
        raise ValueError("file_format must be 'json' or 'csv'.")
    c = _config(config_override)
    base = _base_url(c)
    headers = _headers(c)
    survey_id = (c.get("QUALTRICS_SURVEY_ID") or "").strip()
    if not survey_id:
        raise ValueError("QUALTRICS_SURVEY_ID is required.")
    export_url = f"{base}/surveys/{survey_id}/export-responses/"
    payload = {"format": file_format}
    r = requests.post(export_url, headers=headers, json=payload, timeout=60)
    if r.status_code != 200:
        try:
            msg = r.json().get("meta", {}).get("error", {}).get("errorMessage", r.text)
        except Exception:
            msg = r.text[:500]
        raise RuntimeError(f"Export request failed: {r.status_code} — {msg}")
    progress_id = r.json().get("result", {}).get("progressId")
    if not progress_id:
        raise RuntimeError("Export did not return progressId.")
    import time

    data = None
    while True:
        r2 = requests.get(export_url + progress_id, headers=headers, timeout=30)
        if r2.status_code != 200:
            raise RuntimeError(f"Export progress check failed: {r2.status_code}")
        data = r2.json()
        status = data.get("result", {}).get("status")
        if status == "failed":
            raise RuntimeError("Qualtrics export failed.")
        if status == "complete":
            break
        time.sleep(1)
    file_id = (data or {}).get("result", {}).get("fileId")
    if not file_id:
        raise RuntimeError("Export did not return fileId.")
    r3 = requests.get(export_url + file_id + "/file", headers=headers, stream=True, timeout=120)
    if r3.status_code != 200:
        raise RuntimeError(f"Export download failed: {r3.status_code}")
    import zipfile
    import io

    os.makedirs(QUALTRICS_DIR, exist_ok=True)
    zipfile.ZipFile(io.BytesIO(r3.content)).extractall(QUALTRICS_DIR)
    ext = ".json" if file_format == "json" else ".csv"
    found = [f for f in os.listdir(QUALTRICS_DIR) if f.endswith(ext)]
    if not found:
        raise FileNotFoundError(f"No {ext} file in {QUALTRICS_DIR} after export.")
    return str(Path(QUALTRICS_DIR) / found[0])


def run_cmd(
    cmd: str,
    config_override: dict[str, str] | None = None,
    index: int | None = None,
    file_format: str = "json",
    *,
    contact_id: str | None = None,
    contact_indices: list[int] | None = None,
    limit: int | None = None,
    bypass_time_slot: bool = False,
    all_unsent: bool = False,
) -> None:
    """
    CLI entrypoint: check, list, slist, distributions, preview, send, delete, export.
    Prints to stdout; for export writes file and prints path.
    """
    cmd = (cmd or "").strip().lower()
    config_override = config_override or None

    if cmd == "check":
        result = check_ids(config_override)
        print(json.dumps(result, indent=2))

    elif cmd == "list":
        contacts = get_contact_list(config_override, include_embedded=True)
        print(json.dumps(contacts, indent=2))

    elif cmd == "slist":
        contacts = get_contact_list(config_override, include_embedded=True)
        short = []
        for i, co in enumerate(contacts):
            emb = co.get("embeddedData") or {}
            short.append({
                "index": i,
                "name": f"{co.get('firstName', '')} {co.get('lastName', '')}".strip(),
                "email": co.get("email") or "",
                "phone": co.get("phone") or "",
                "scheduled": emb.get("SurveysSchedule"),
                "useSMS": emb.get("UseSMS"),
                "useEmail": emb.get("UseEmail"),
                "deleteUnsent": emb.get("DeleteUnsent"),
            })
        print(json.dumps(short, indent=2))

    elif cmd == "distributions":
        result = list_distributions(config_override)
        print(json.dumps(result, indent=2))

    elif cmd == "preview":
        result = send_preview(config_override)
        print(json.dumps(result, indent=2))

    elif cmd == "send":
        result = send_distributions(
            config_override,
            contact_indices=contact_indices,
            limit=limit,
            bypass_time_slot=bypass_time_slot,
        )
        print(json.dumps(result, indent=2))

    elif cmd == "delete":
        result = delete_unsent(
            config_override,
            contact_index=index,
            contact_id=contact_id,
            all_unsent=all_unsent,
        )
        print(json.dumps(result, indent=2))

    elif cmd == "export":
        path = export_surveys(config_override, file_format=file_format)
        print(path)

    else:
        raise ValueError(
            f"Unknown command: {cmd}. Use: check, list, slist, distributions, preview, send, delete, export."
        )
