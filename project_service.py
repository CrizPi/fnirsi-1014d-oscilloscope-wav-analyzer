import json
import os
from datetime import datetime
from state_store import state_get, state_set, state_update

PROJECT_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.dirname(os.path.abspath(__file__))),
    "FNIRSI1014DAnalyzer",
    "projects",
)

PROJECT_STATE_KEYS = (
    "file_wav",
    "original_name",
    "ch1_name",
    "ch2_name",
    "config",
    "measures",
    "math_operation",
    "math_measures",
    "fft_settings",
    "fft_enabled",
    "fft_data",
    "statistics_enabled",
    "statistics_data",
    "advanced_enabled",
    "advanced_data",
    "calculus_enabled",
    "calculus_settings",
    "calculus_data",
    "current_enabled",
    "current_settings",
    "current_data",
    "total_current_enabled",
    "total_current_settings",
    "total_current_data",
    "transfer_enabled",
    "transfer_settings",
    "transfer_data",
    "xy_enabled",
    "xy_settings",
    "xy_data",
    "correlation_enabled",
    "correlation_data",
    "calibration_settings",
    "calibration_enabled",
    "cursor_settings",
    "cursor_enabled",
    "cursor_data",
    "cycle_settings",
    "cycle_enabled",
    "cycle_data",
    "comparison_enabled",
    "comparison_snapshot_id",
    "comparison_data",
    "digital_data",
    "snapshots",
    "current_snapshots",
    "export_settings",
    "user_preferences",
    "recent_files",
)


def save_project(name):
    os.makedirs(PROJECT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in name).strip() or "untitled"
    filename = f"{safe_name}_{timestamp}.json"
    path = os.path.join(PROJECT_DIR, filename)
    data = {"name": name, "date": timestamp, "path": path}
    for key in PROJECT_STATE_KEYS:
        value = state_get(key)
        if value is not None:
            data[key] = value
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def load_project(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        return {"error": f"Could not load project: {exc}"}
    file_wav = data.get("file_wav")
    if not file_wav or not os.path.exists(file_wav):
        return {"error": "Original WAV file not found at: " + str(file_wav)}
    for key in PROJECT_STATE_KEYS:
        if key in data:
            state_set(key, data[key])
    state_update({"project_data": data})
    return data


def list_projects():
    if not os.path.isdir(PROJECT_DIR):
        return []
    projects = []
    for entry in sorted(os.scandir(PROJECT_DIR), key=lambda e: e.stat().st_mtime, reverse=True):
        if entry.is_file() and entry.name.endswith(".json"):
            try:
                with open(entry.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                projects.append({
                    "name": data.get("name", entry.name),
                    "path": entry.path,
                    "date": data.get("date", datetime.fromtimestamp(entry.stat().st_mtime).strftime("%Y%m%d_%H%M%S")),
                })
            except (OSError, json.JSONDecodeError):
                continue
    return projects
