"""Distribution tools: read-only (contacts, check, status, list, preview, export) and dangerous (send, delete_unsent, contact_patch)."""

import threading

from backend.services import state

from ai.context import get_store, get_user
from ai.tools.common import require_study_access, require_confirm, tool_error, tool_result


def _config_for_study(study_id: str) -> dict:
    store = get_store()
    raw = store.get_study_config(study_id)
    return state.get_study_config_merged(raw)


def qual_distribution_contacts(study_id: str) -> str:
    """List mailing list contacts for the study (short form with index, name, email, embeddedData)."""
    try:
        store = get_store()
        user = get_user()
        err = require_study_access(store, user, study_id)
        if err:
            return tool_error(err)
        config_dict = _config_for_study(study_id)
        from backend.pipeline.qualtrics_distribution import get_contact_list

        contacts = get_contact_list(config_dict, include_embedded=True)
        short = []
        for i, co in enumerate(contacts):
            emb = co.get("embeddedData") or {}
            short.append({
                "index": i,
                "id": co.get("id"),
                "firstName": co.get("firstName", ""),
                "lastName": co.get("lastName", ""),
                "name": f"{co.get('firstName', '')} {co.get('lastName', '')}".strip(),
                "email": co.get("email") or "",
                "phone": co.get("phone") or "",
                "embeddedData": emb,
                "scheduled": emb.get("SurveysSchedule"),
                "useSMS": emb.get("UseSMS"),
                "useEmail": emb.get("UseEmail"),
                "deleteUnsent": emb.get("DeleteUnsent"),
            })
        return tool_result({"contacts": short})
    except ValueError as e:
        return tool_error(str(e))
    except Exception as e:
        return tool_error(str(e))


def qual_distribution_check(study_id: str) -> str:
    """Validate survey, mailing list, and message IDs for the study."""
    try:
        store = get_store()
        user = get_user()
        err = require_study_access(store, user, study_id)
        if err:
            return tool_error(err)
        config_dict = _config_for_study(study_id)
        from backend.pipeline.qualtrics_distribution import check_ids

        result = check_ids(config_dict)
        return tool_result(result)
    except Exception as e:
        return tool_error(str(e))


def qual_distribution_status(study_id: str) -> str:
    """Return whether a send is in progress and the last send result for the study."""
    try:
        store = get_store()
        user = get_user()
        err = require_study_access(store, user, study_id)
        if err:
            return tool_error(err)
        busy = state.get_distribution_busy(study_id)
        last = state.get_distribution_last_result(study_id)
        return tool_result({"busy": busy, "lastResult": last})
    except Exception as e:
        return tool_error(str(e))


def qual_distribution_list(study_id: str) -> str:
    """List email and SMS distributions for the survey/mailing list."""
    try:
        store = get_store()
        user = get_user()
        err = require_study_access(store, user, study_id)
        if err:
            return tool_error(err)
        config_dict = _config_for_study(study_id)
        from backend.pipeline.qualtrics_distribution import list_distributions

        return tool_result(list_distributions(config_dict))
    except Exception as e:
        return tool_error(str(e))


def qual_distribution_send_preview(study_id: str) -> str:
    """Preview which contacts would receive a send (no actual send)."""
    try:
        store = get_store()
        user = get_user()
        err = require_study_access(store, user, study_id)
        if err:
            return tool_error(err)
        config_dict = _config_for_study(study_id)
        from backend.pipeline.qualtrics_distribution import send_preview

        return tool_result(send_preview(config_dict))
    except ValueError as e:
        return tool_error(str(e))
    except Exception as e:
        return tool_error(str(e))


def qual_distribution_export(study_id: str, format: str = "json") -> str:
    """Export survey responses. format: 'json' or 'csv'. Returns path to the exported file."""
    try:
        store = get_store()
        user = get_user()
        err = require_study_access(store, user, study_id)
        if err:
            return tool_error(err)
        if format not in ("json", "csv"):
            format = "json"
        config_dict = _config_for_study(study_id)
        from backend.pipeline.qualtrics_distribution import export_surveys

        path = export_surveys(config_dict, file_format=format)
        return tool_result({"ok": True, "path": path, "format": format})
    except ValueError as e:
        return tool_error(str(e))
    except Exception as e:
        return tool_error(str(e))


def qual_distribution_send(
    study_id: str,
    limit: int | None = None,
    contact_indices: list[int] | None = None,
    bypass_time_slot: bool = False,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Start sending distributions in the background. Optional limit, contactIndices, bypassTimeSlot. Requires confirmation."""
    err = require_confirm("qual_distribution_send", confirm_dangerous_operation)
    if err:
        return err
    try:
        store = get_store()
        user = get_user()
        err_acc = require_study_access(store, user, study_id, min_role="editor")
        if err_acc:
            return tool_error(err_acc)
        if state.get_distribution_busy(study_id):
            return tool_error("Distribution send already in progress.")
        config_dict = _config_for_study(study_id)
        if limit is not None and (not isinstance(limit, int) or limit < 1):
            return tool_error("limit must be a positive integer.")
        if contact_indices is not None and not isinstance(contact_indices, list):
            return tool_error("contactIndices must be an array of integers.")

        def run_send():
            try:
                from backend.pipeline.qualtrics_distribution import send_distributions

                result = send_distributions(
                    config_dict,
                    contact_indices=contact_indices,
                    limit=limit,
                    bypass_time_slot=bypass_time_slot,
                )
                state.set_distribution_last_result(study_id, result)
            except Exception as e:
                state.set_distribution_last_result(study_id, {"sent": 0, "errors": [str(e)]})
            finally:
                state.set_distribution_busy(study_id, False)

        state.set_distribution_busy(study_id, True)
        t = threading.Thread(target=run_send, daemon=True)
        t.start()
        return tool_result({"ok": True, "message": "Send started."})
    except Exception as e:
        return tool_error(str(e))


def qual_distribution_delete_unsent(
    study_id: str,
    index: int | None = None,
    contact_id: str | None = None,
    all_unsent: bool = False,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Delete unsent distributions. Use exactly one of: index, contact_id, or all_unsent. Requires confirmation."""
    err = require_confirm("qual_distribution_delete_unsent", confirm_dangerous_operation)
    if err:
        return err
    try:
        store = get_store()
        user = get_user()
        err_acc = require_study_access(store, user, study_id, min_role="editor")
        if err_acc:
            return tool_error(err_acc)
        if sum(x is not None and x for x in [index, contact_id, all_unsent]) > 1:
            return tool_error("Use only one of: index, contactId, or allUnsent.")
        config_dict = _config_for_study(study_id)
        from backend.pipeline.qualtrics_distribution import delete_unsent

        result = delete_unsent(
            config_dict,
            contact_index=index,
            contact_id=contact_id or None,
            all_unsent=all_unsent,
        )
        return tool_result({"ok": True, "deleted": result.get("deleted", 0), "errors": result.get("errors", [])})
    except ValueError as e:
        return tool_error(str(e))
    except RuntimeError as e:
        return tool_error(str(e))
    except Exception as e:
        return tool_error(str(e))


def qual_distribution_contact_patch(
    study_id: str,
    contact_id: str,
    embedded_data: dict,
    confirm_dangerous_operation: bool = False,
) -> str:
    """Update contact embedded data. embedded_data: object to merge. Requires confirmation."""
    err = require_confirm("qual_distribution_contact_patch", confirm_dangerous_operation)
    if err:
        return err
    try:
        store = get_store()
        user = get_user()
        err_acc = require_study_access(store, user, study_id, min_role="editor")
        if err_acc:
            return tool_error(err_acc)
        if not isinstance(embedded_data, dict):
            return tool_error("embeddedData must be an object.")
        config_dict = _config_for_study(study_id)
        from backend.pipeline.qualtrics_distribution import update_embedded

        update_embedded(config_dict, contact_id=contact_id, update_fields=embedded_data)
        return tool_result({"ok": True, "message": "Contact updated."})
    except ValueError as e:
        return tool_error(str(e))
    except RuntimeError as e:
        return tool_error(str(e))
    except Exception as e:
        return tool_error(str(e))
