import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTFILE = Path("Stations.json")

DATASET_NAME = "Ground Water Level"
STATE_NAME = "Andhra pradesh"
MODES = ["Telemetry", "Manual"]

def run():
    stations = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=500)
        page = browser.new_page()

        print("🌐 Opening WRIS...")
        page.goto("https://indiawris.gov.in/dataSet/")
        page.wait_for_timeout(5000)

        # --- Switch to iframe ---
        iframe = None
        for f in page.frames:
            if "/dataSet/" in f.url:
                iframe = f
                break
        if not iframe:
            print("❌ No iframe found!")
            return

        print("✅ Switched to iframe:", iframe.url)

        # --- Select Dataset ---
        iframe.locator("select#applicationSelect").select_option(label=DATASET_NAME)
        print("✅ Dataset selected:", DATASET_NAME)

        # --- Select State ---
        state_container = iframe.locator("label:has-text('State')").locator("xpath=..")
        state_btn = state_container.locator("span.dropdown-btn")
        state_btn.click()
        iframe.locator(f"li.multiselect-item-checkbox:has-text('{STATE_NAME}')").click()
        state_btn.click()
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
                districts.append((txt, i))
        dist_btn.click()
        print(f"📍 Found {len(districts)} districts")

        for dname, didx in districts:
            print(f"\n🏙️ District: {dname} (variant {didx})")
            dist_btn.click()
            dist_container.locator(f"li.multiselect-item-checkbox:has-text('{dname}')").nth(didx).click()
            dist_btn.click()

            # --- Tehsils ---
            tehsil_container = iframe.locator("label:has-text('Tehsil')").locator("xpath=..")
            tehsil_btn = tehsil_container.locator("span.dropdown-btn")
            tehsil_btn.click()
            tehsil_items = tehsil_container.locator("li.multiselect-item-checkbox")
            tehsils = []
            for j in range(tehsil_items.count()):
                ttxt = tehsil_items.nth(j).inner_text().strip()
                if ttxt and "Select all" not in ttxt:
                    tehsils.append((ttxt, j))
            tehsil_btn.click()
            print(f"   📌 Found {len(tehsils)} tehsils for {dname}")

            for tname, tidx in tehsils:
                print(f"   📌 Tehsil: {tname} (variant {tidx})")
                tehsil_btn.click()
                option = tehsil_container.locator(f"li.multiselect-item-checkbox:has-text('{tname}')").nth(tidx)
                option.scroll_into_view_if_needed()
                option.wait_for(state="visible", timeout=5000)
                option.click(force=True)
                tehsil_btn.click()

                # --- Blocks ---
                block_container = iframe.locator("label:has-text('Block')").locator("xpath=..")
                block_btn = block_container.locator("span.dropdown-btn")
                block_btn.click()
                time.sleep(2)
                block_items = block_container.locator("li.multiselect-item-checkbox")
                blocks = []
                for b in range(block_items.count()):
                    btxt = block_items.nth(b).inner_text().strip()
                    if btxt and "Select all" not in btxt:
                        blocks.append((btxt, b))
                block_btn.click()

                for bname, bidx in blocks:
                    print(f"      🧱 Block: {bname} (variant {bidx})")
                    block_btn.click()
                    block_container.locator(f"li.multiselect-item-checkbox:has-text('{bname}')").nth(bidx).click()
                    block_btn.click()

                    # --- Agencies ---
                    agency_container = iframe.locator("label:has-text('Agency')").locator("xpath=..")
                    agency_btn = agency_container.locator("span.dropdown-btn")
                    agency_btn.click()
                    time.sleep(2)
                    agency_items = agency_container.locator("li.multiselect-item-checkbox")
                    agencies = []
                    for a in range(agency_items.count()):
                        atxt = agency_items.nth(a).inner_text().strip()
                        if atxt and "Select all" not in atxt:
                            agencies.append((atxt, a))
                    agency_btn.click()

                    for aname, aidx in agencies:
                        print(f"         🏢 Agency: {aname} (variant {aidx})")
                        agency_btn.click()
                        agency_container.locator(f"li.multiselect-item-checkbox:has-text('{aname}')").nth(aidx).click()
                        agency_btn.click()

                        # --- Modes ---
                        for mode in MODES:
                            iframe.locator("select#manualTelemetry").select_option(label=mode)
                            print(f"            ⚙️ Mode: {mode}")

                            # --- Stations ---
                            station_container = iframe.locator("h3:has-text('Station Selection')").locator("..")
                            station_btn = station_container.locator("span.dropdown-btn")

                            try:
                                station_btn.click()
                                time.sleep(2)

                                # Check if "Station not found" is present
                                if station_container.locator("li.no-data:has-text('Station not found.')").count() > 0:
                                    print(f"               🚫 No stations found for {mode}")
                                    station_btn.click()
                                    continue

                                # Collect stations
                                station_items = station_container.locator("li.multiselect-item-checkbox")
                                for sidx in range(station_items.count()):
                                    stxt = station_items.nth(sidx).inner_text().strip()
                                    if not stxt or "Select all" in stxt:
                                        continue
                                    code = station_items.nth(sidx).locator("input").get_attribute("value")
                                    print(f"               🎯 Station: {stxt} ({code})")
                                    stations.append({
                                        "district": dname,
                                        "tehsil": tname,
                                        "block": bname,
                                        "agency": aname,
                                        "mode": mode,
                                        "station_code": code,
                                        "station_name": stxt
                                    })
                                station_btn.click()

                            except Exception as e:
                                print(f"               ⚠️ Could not fetch stations for {mode}: {e}")

        # Save all stations
        with open(OUTFILE, "w", encoding="utf-8") as f:
            json.dump(stations, f, ensure_ascii=False, indent=2)

        print(f"\n💾 Saved {len(stations)} stations to {OUTFILE}")
        browser.close()


if __name__ == "__main__":
    run()
