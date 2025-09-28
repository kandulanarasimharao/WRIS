import os
import json
import time
from collections import defaultdict
from playwright.sync_api import sync_playwright

OUTFILE = "Districts_Tehsils.json"
DATASET_NAME = "Ground Water Level"
STATE_NAME = "Andhra pradesh"

def get_dropdown_options(frame, label_text):
    """Return all options (text + index) from a multiselect dropdown."""
    container = frame.locator(f"label:has-text('{label_text}')").locator("xpath=..")
    btn = container.locator("span.dropdown-btn")
    btn.click()
    items = container.locator("li.multiselect-item-checkbox")
    results = []
    count = items.count()
    for idx in range(count):
        txt = items.nth(idx).inner_text().strip()
        if txt and "Select all" not in txt:
            results.append(txt)
    btn.click()
    return results

def select_from_dropdown(frame, label_text, option_text, option_index=0):
    """Open a multiselect dropdown and select/deselect option at given index."""
    container = frame.locator(f"label:has-text('{label_text}')").locator("xpath=..")
    btn = container.locator("span.dropdown-btn")
    btn.click()
    matches = container.locator(f"li.multiselect-item-checkbox:has-text('{option_text}')")
    matches.nth(option_index).click()
    btn.click()

def run():
    all_data = defaultdict(list)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=400)
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

        # --- Dataset ---
        iframe.locator("select#applicationSelect").select_option(label=DATASET_NAME)
        print("✅ Dataset selected:", DATASET_NAME)

        # --- State ---
        select_from_dropdown(iframe, "State", STATE_NAME)
        print("✅ State selected:", STATE_NAME)

        # --- Districts ---
        districts = get_dropdown_options(iframe, "District")
        print(f"📍 Found {len(districts)} district entries")

        # group by name
        from collections import Counter
        counts = Counter(districts)

        for dname in counts.keys():
            num_variants = counts[dname]
            for v in range(num_variants):
                try:
                    print(f"\n🏙️ District: {dname} (variant {v})")

                    # Select district variant
                    select_from_dropdown(iframe, "District", dname, v)
                    time.sleep(2)  # wait for tehsils to load

                    # Get tehsils
                    tehsils = get_dropdown_options(iframe, "Tehsil")
                    print(f"   📌 {len(tehsils)} tehsils found for {dname} ({v})")

                    for tname in tehsils:
                        if tname not in all_data[dname]:
                            all_data[dname].append(tname)

                    # Deselect this district
                    select_from_dropdown(iframe, "District", dname, v)
                    time.sleep(1)

                except Exception as e:
                    print(f"⚠️ Skipping {dname} ({v}) due to error: {e}")

        # Save results
        with open(OUTFILE, "w", encoding="utf-8") as f:
            json.dump(all_data, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Saved {OUTFILE}")

        browser.close()

if __name__ == "__main__":
    run()
