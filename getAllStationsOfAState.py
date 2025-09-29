import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def safe(s: str) -> str:
    """Sanitize text for filenames: spaces -> _, / and \ -> -"""
    return str(s).replace("/", "-").replace("\\", "-").replace(" ", "_")
	

DATASET_NAME = "Ground Water Level"
STATE_NAME = input("State Name (default: Andhra Pradesh): ").strip() or "Andhra Pradesh"
OUTFILE = Path(f"{safe(STATE_NAME)}_Stations.json")
MODES = ["Telemetry", "Manual"]

def click_option_by_text(container, btn, option_name):
    btn.click()
    items = container.locator("li.multiselect-item-checkbox")
    found = False
    for i in range(items.count()):
        txt = items.nth(i).inner_text().strip()
        if txt == option_name:
            items.nth(i).click()
            found = True
            break
    btn.click()
    return found


def click_nth_option_by_text(container, btn, option_name, occurrence=0):
    btn.click()
    items = container.locator("li.multiselect-item-checkbox")
    match_count = 0
    found = False
    for i in range(items.count()):
        txt = items.nth(i).inner_text().strip()
        if txt == option_name:
            if match_count == occurrence:
                items.nth(i).click()
                found = True
                break
            match_count += 1
    btn.click()
    return found


def reset_dropdown(container, btn, label):
    btn.click()
    items = container.locator("li.multiselect-item-checkbox")
    for i in range(items.count()):
        txt = items.nth(i).inner_text().strip()
        if "Select all" in txt:
            items.nth(i).click()
            print(f"   🔄 Reset {label}")
            break
    btn.click()
    time.sleep(0.7)


def fetch_stations_with_metadata(page, iframe, dname, tname, bname, aname, mode):
    """Loop through all stations, reset each time, click, and extract stationId from metadata table."""
    station_data = []
    try:
        # open dropdown once to count stations
        station_container = iframe.locator("h3:has-text('Station Selection')").locator("xpath=..")
        station_btn = station_container.locator("div.multiselect-dropdown .dropdown-btn")

        station_btn.click(force=True)
        time.sleep(1.0)
        station_items = station_container.locator("ul.item2 li.multiselect-item-checkbox")
        scount = station_items.count()
        station_btn.click(force=True)

        if scount == 0:
            print(f"               🚫 No stations found for {mode}")
            return []

        print(f"               📋 Found {scount} stations")

        # loop through all stations
        for sidx in range(scount):
            try:
                # re-open dropdown fresh each time
                station_container = iframe.locator("h3:has-text('Station Selection')").locator("xpath=..")
                station_btn = station_container.locator("div.multiselect-dropdown .dropdown-btn")
                station_btn.click(force=True)
                page.wait_for_timeout(500)

                # 🔄 Reset all previously selected stations (Select all → deselect all)
                if station_container.locator("li.multiselect-item-checkbox:has-text('Select all')").count() > 0:
                    sel_all = station_container.locator("li.multiselect-item-checkbox:has-text('Select all')")
                    sel_all.click(force=True)   # select all
                    sel_all.click(force=True)   # deselect all
                    page.wait_for_timeout(500)

                # re-fetch items again after reset
                station_items = station_container.locator("ul.item2 li.multiselect-item-checkbox")

                stxt = station_items.nth(sidx).inner_text().strip()
                code = station_items.nth(sidx).locator("input").get_attribute("value")

                print(f"                  ⏩ Selecting station {sidx+1}/{scount}: {stxt}")

                # select this station only
                station_items.nth(sidx).click(force=True)
                station_btn.click(force=True)

                # wait for metadata panel to refresh
                iframe.wait_for_selector("h3:has-text('Station Metadata')", timeout=5000)
                iframe.wait_for_selector("tr:has(th:has-text('Station Code')) td", timeout=5000)

                metadata_table = iframe.locator("h3:has-text('Station Metadata')").locator("xpath=..")
                code_cell = metadata_table.locator("tr:has(th:has-text('Station Code')) td")
                name_cell = metadata_table.locator("tr:has(th:has-text('Station Name')) td")

                station_id = code_cell.inner_text().strip() if code_cell.count() else None
                meta_name = name_cell.inner_text().strip() if name_cell.count() else None

                print(f"               🎯 Station {sidx+1}/{scount}: {stxt} ({code}) → stationId={station_id}")

                station_data.append({
                    "district": dname,
                    "tehsil": tname,
                    "block": bname,
                    "agency": aname,
                    "mode": mode,
                    "station_code": code,
                    "station_name": stxt,
                    "station_id": station_id,
                    "meta_name": meta_name
                })

            except Exception as e:
                print(f"                  ⚠️ Error on station {sidx+1}/{scount}: {e}")
                continue

        return station_data

    except Exception as e:
        print(f"               ⚠️ Could not fetch stations for {mode}: {e}")
        return []


def run():
    stations = []
    seen_counts = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=300)
        page = browser.new_page()

        print("🌐 Opening WRIS...")
        page.goto("https://indiawris.gov.in/dataSet/")
        page.wait_for_timeout(4500)

        iframe = None
        for f in page.frames:
            if "/dataSet/" in f.url:
                iframe = f
                break
        if not iframe:
            print("❌ No iframe found!")
            return

        print("✅ Switched to iframe:", iframe.url)

        iframe.locator("select#applicationSelect").select_option(label=DATASET_NAME)
        print("✅ Dataset selected:", DATASET_NAME)

        state_container = iframe.locator("label:has-text('State')").locator("xpath=..")
        state_btn = state_container.locator("span.dropdown-btn")
        click_option_by_text(state_container, state_btn, STATE_NAME)
        print("✅ State selected:", STATE_NAME)

        # --- Districts ---
        dist_container = iframe.locator("label:has-text('District')").locator("xpath=..")
        dist_btn = dist_container.locator("span.dropdown-btn")
        dist_btn.click()
        dist_items = dist_container.locator("li.multiselect-item-checkbox")
        districts = []
        for i in range(dist_items.count()):
            txt = dist_items.nth(i).inner_text().strip()
            if txt and "Select all" not in txt:
                districts.append(txt)
        dist_btn.click()
        print(f"📍 Found {len(districts)} districts (including duplicates)")

        for dname in districts:
            occurrence = seen_counts.get(dname, 0)
            is_duplicate = occurrence > 0

            print(f"\n🏙️ District: {dname} (occurrence #{occurrence + 1})")

            if is_duplicate:
                print(f"   🔁 Duplicate district detected: {dname} → resetting dependent filters")
                tehsil_container = iframe.locator("label:has-text('Tehsil')").locator("xpath=..")
                tehsil_btn = tehsil_container.locator("span.dropdown-btn")
                reset_dropdown(tehsil_container, tehsil_btn, "Tehsil")

                block_container = iframe.locator("label:has-text('Block')").locator("xpath=..")
                block_btn = block_container.locator("span.dropdown-btn")
                reset_dropdown(block_container, block_btn, "Block")

                agency_container = iframe.locator("label:has-text('Agency')").locator("xpath=..")
                agency_btn = agency_container.locator("span.dropdown-btn")
                reset_dropdown(agency_container, agency_btn, "Agency")

            click_nth_option_by_text(dist_container, dist_btn, dname, occurrence=occurrence)
            time.sleep(1.0)

            seen_counts[dname] = occurrence + 1

            # --- Tehsils ---
            tehsil_container = iframe.locator("label:has-text('Tehsil')").locator("xpath=..")
            tehsil_btn = tehsil_container.locator("span.dropdown-btn")
            tehsil_btn.click()
            tehsil_items = tehsil_container.locator("li.multiselect-item-checkbox")
            tehsils = []
            for j in range(tehsil_items.count()):
                ttxt = tehsil_items.nth(j).inner_text().strip()
                if ttxt and "Select all" not in ttxt:
                    tehsils.append(ttxt)
            tehsil_btn.click()
            print(f"   📌 Found {len(tehsils)} tehsils for {dname}")

            tehsil_used = False

            for tname in tehsils:
                print(f"   📌 Trying tehsil: {tname}")
                click_option_by_text(tehsil_container, tehsil_btn, tname)
                time.sleep(0.6)

                block_container = iframe.locator("label:has-text('Block')").locator("xpath=..")
                block_btn = block_container.locator("span.dropdown-btn")
                block_btn.click()
                time.sleep(0.9)
                block_items = block_container.locator("li.multiselect-item-checkbox")
                blocks = []
                for b in range(block_items.count()):
                    btxt = block_items.nth(b).inner_text().strip()
                    if btxt and "Select all" not in btxt:
                        blocks.append(btxt)
                block_btn.click()

                if not blocks:
                    print(f"      ⚠️ No blocks for tehsil {tname}, trying next tehsil…")
                    continue

                tehsil_used = True

                for bname in blocks:
                    print(f"      🧱 Block: {bname}")
                    click_option_by_text(block_container, block_btn, bname)
                    time.sleep(0.5)

                    agency_container = iframe.locator("label:has-text('Agency')").locator("xpath=..")
                    agency_btn = agency_container.locator("span.dropdown-btn")
                    agency_btn.click()
                    time.sleep(0.8)
                    agency_items = agency_container.locator("li.multiselect-item-checkbox")
                    agencies = []
                    for a in range(agency_items.count()):
                        atxt = agency_items.nth(a).inner_text().strip()
                        if atxt and "Select all" not in atxt:
                            agencies.append(atxt)
                    agency_btn.click()

                    for aname in agencies:
                        print(f"         🏢 Agency: {aname}")
                        click_option_by_text(agency_container, agency_btn, aname)
                        time.sleep(0.4)

                        for mode in MODES:
                            iframe.locator("select#manualTelemetry").select_option(label=mode)
                            print(f"            ⚙️ Mode: {mode}")
                            stations.extend(fetch_stations_with_metadata(page, iframe, dname, tname, bname, aname, mode))

                break

            if not tehsil_used:
                print(f"⚠️ No valid tehsil found with blocks for district {dname}")

        with open(OUTFILE, "w", encoding="utf-8") as f:
            json.dump(stations, f, ensure_ascii=False, indent=2)

        print(f"\n💾 Saved {len(stations)} stations to {OUTFILE}")
        browser.close()


if __name__ == "__main__":
    run()
