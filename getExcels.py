import json
import requests
import pandas as pd
from pathlib import Path
import os

# -------------------
# CONFIG
# -------------------
DATASET = "GWATERLVL"   # Dataset code

# -------------------
# COMMON HEADERS
# -------------------
HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://indiawris.gov.in",
    "Referer": "https://indiawris.gov.in/dataSet/",
    "User-Agent": "Mozilla/5.0"
}

# -------------------
# HELPER FUNCTIONS
# -------------------
def safe(s: str) -> str:
    """Sanitize text for filenames: spaces -> _, / and \ -> -"""
    return str(s).replace("/", "-").replace("\\", "-").replace(" ", "_")

# -------------------
# MAIN
# -------------------
def main():
    # Ask for state name
    state_name = input("Enter State Name (e.g., AndhraPradesh): ").strip()
    base_folder = Path(state_name)
    manual_folder = base_folder / "Manual"
    telemetry_folder = base_folder / "Telemetry"

    # Create folders if not exist
    manual_folder.mkdir(parents=True, exist_ok=True)
    telemetry_folder.mkdir(parents=True, exist_ok=True)
	
	json_file = f"{safe(STATE_NAME)}_Stations.json"
    # Load JSON
    with open(json_file, "r", encoding="utf-8") as f:
        stations_list = json.load(f)

    for st in stations_list:
        STATION_CODE = st["station_id"]
        mode = st.get("mode", "Unknown").capitalize()

        print(f"\n📡 Processing: {STATION_CODE} ({st['station_name']})")

        # ---- STEP 1: Metadata ----
        meta_url = "https://indiawris.gov.in/stationMaster/getMasterStationsList"
        meta_payload = {"stationcode": STATION_CODE, "datasetcode": DATASET}

        try:
            meta_resp = requests.post(meta_url, json=meta_payload, headers=HEADERS, timeout=30)
            meta_resp.raise_for_status()
            meta = meta_resp.json()
        except Exception as e:
            print(f"❌ Metadata request failed for {STATION_CODE}: {e}")
            continue

        if meta.get("statusCode") != 200 or not meta.get("data"):
            print("❌ Metadata fetch failed:", meta)
            continue

        station_meta = meta["data"][0]
        print("✅ Station:", station_meta.get("station_Name"))
        print("📍 District:", station_meta.get("district"))
        print("📅 Available:", station_meta.get("data_available_from"), "→", station_meta.get("data_available_Till"))

        df_info = pd.DataFrame(list(station_meta.items()), columns=["Field", "Value"])

        # ---- STEP 2: Data ----
        data_url = "https://indiawris.gov.in/CommonDataSetMasterAPI/getCommonDataSetByStationCode"
        data_payload = {
            "station_code": STATION_CODE,
            "starttime": station_meta["data_available_from"],
            "endtime": station_meta["data_available_Till"],
            "dataset": DATASET
        }

        try:
            data_resp = requests.post(data_url, json=data_payload, headers=HEADERS, timeout=60)
            data_resp.raise_for_status()
            data = data_resp.json()
        except Exception as e:
            print(f"❌ Data request failed for {STATION_CODE}: {e}")
            continue

        if data.get("statusCode") != 200 or not data.get("data"):
            print("❌ Data fetch failed:", data)
            continue

        records = data["data"]
        print(f"✅ Received {len(records)} rows")

        df_data = pd.DataFrame(records)
        if "dataTime" in df_data.columns:
            df_data["dataTime"] = pd.to_datetime(df_data["dataTime"])

        # ---- STEP 3: Save ----
        outfile = f"{safe(st['district'])}_{safe(st['tehsil'])}_{safe(st['block'])}_{safe(st['agency'])}_{safe(st['mode'])}_{safe(st['station_name'])}.xlsx"

        if mode == "Manual":
            save_path = manual_folder / outfile
        else:
            save_path = telemetry_folder / outfile

        with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
            df_info.to_excel(writer, sheet_name="Info", index=False)
            df_data.to_excel(writer, sheet_name="Data", index=False)

        print("💾 Saved:", save_path)

if __name__ == "__main__":
    main()
