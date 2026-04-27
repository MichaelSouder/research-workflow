"""
Normalize legacy Qualtrics response data: split name fields, sort complete/incomplete.
"""


def normalize_legacy_qualtrics_data(data: list[dict]) -> list[dict]:
    normalized_names = []
    for response in data:
        if "QID312_1" in response and "QID312_5" in response:
            normalized_names.append(response)
        else:
            if "QID312_1" in response:
                name_array = response["QID312_1"].split(" ", 1)
                response["QID312_1"] = name_array[0]
                response["QID312_5"] = name_array[1] if len(name_array) > 1 else ""
                normalized_names.append(response)
    incomplete = []
    normalized_name_completion_records = []
    for record in normalized_names:
        if "responseId" in record:
            normalized_name_completion_records.append(record)
        else:
            incomplete.append(record)
    result = []
    for record in normalized_name_completion_records:
        record["normalizedName"] = record["QID312_1"] + " " + record["QID312_5"]
        result.append(record)
    return result
