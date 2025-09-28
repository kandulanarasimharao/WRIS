from playwright.sync_api import sync_playwright
import json

BASE = "https://indiawris.gov.in/wris-lapi"
STATECODE = "01"       # Andhra Pradesh
DATASET = "GWATERLVL"  # Ground Water Level

def fetch_json(page, endpoint, params=None):
    query = ""
    if params:
        query = "?" + "&".join(f"{k}={v}" for k, v in params.items())
    url = f"{BASE}/{endpoint}{query}"
    result = page.evaluate(f"""async () => {{
        const resp = await fetch("{url}", {{
            headers: {{
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://indiawris.gov.in/dataSet/",
                "Origin": "https://indiawris.gov.in"
            }}
        }});
        return await resp.json();
    }}""")
    return result

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # keep visible for debugging
    page = browser.new_page()

    print("🌐 Opening WRIS...")
    page.goto("https://indiawris.gov.in/dataSet/")
    page.wait_for_timeout(5000)  # wait 5 seconds

    print("➡️ Fetching districts for Andhra Pradesh...")
    result = fetch_json(page, "getDistrictByState", {
        "datasetcode": DATASET,
        "statecode": STATECODE
    })

    print("✅ Raw Response:")
    print(json.dumps(result, indent=2))

    browser.close()
