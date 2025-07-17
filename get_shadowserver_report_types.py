import os
import csv
import time
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from urllib.parse import urljoin  # Add this to the top
from pathlib import Path
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# === Config ===
base_url = "https://www.shadowserver.org"
target_url = f"{base_url}/what-we-do/network-reporting/"
output_dir = "shadowserver_url_descriptions"
html_dir = "shadowserver_report_types_http_files"
output_csv = os.path.join(output_dir, "shadowserver_description_check.csv")
final_output_file = os.path.join(output_dir, "shadowserver_report_types.csv")

os.makedirs(output_dir, exist_ok=True)
os.makedirs(html_dir, exist_ok=True)

# === Setup Selenium ===
options = Options()
options.add_argument("--headless")
options.add_argument("--window-size=1920,1080")
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)
driver = webdriver.Chrome(options=options)

# === Phase 1: Extract from network-reporting page ===
driver.get(target_url)

# Wait for the reports section to be fully loaded
try:
    WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.reports-list div.report"))
    )
    soup = BeautifulSoup(driver.page_source, "html.parser")
    report_blocks = soup.select("div.reports-list div.report")
except Exception as e:
    print(f"Error: {e}")

report_blocks = soup.select("div.reports-list div.report")
rows = []

print("📥 Extracting report entries from main page...\n")

unknown_severity_rows = []
seen_titles = set()

for report in report_blocks:
    title_tag = report.select_one("div.title a.standard")
    desc_div = report.select_one("div.description")
    if not title_tag or not desc_div:
        continue

    title = title_tag.text.strip()
    if "API:" in title:
        continue

    link = urljoin(base_url, title_tag["href"])
    description = desc_div.get_text(strip=True)

    if ":" in title:
        severity, name = title.split(":", 1)
        severity = severity.strip()
        name = name.strip()
    else:
        severity = "INFO"
        name = title
        unknown_severity_rows.append(name)
        print(f"⚠️ No explicit severity for: {name}")

    # === Safeguard 1: Skip incomplete entries ===
    if not all([title, severity, name, link, description]):
        print(f"⚠️ Skipping incomplete entry – missing fields in: {title}")
        continue

    # === Safeguard 2: Detect duplicates ===
    if title in seen_titles:
        print(f"⚠️ Duplicate title found and skipped: {title}")
        continue
    seen_titles.add(title)

    print(f"🔗 Title: {name}")
    print(f"📎 URL:   {link}")
    print(f"📝 Desc:  {description}\n")

    rows.append({
        "Title": title,
        "Severity": severity,
        "Name": name,
        "URL": link,
        "Description": description
    })

# === Manual entries to include if missing ===
manual_entries = [
    {
        "Title": "Accessible BGP Service Report",
        "Severity": "MEDIUM",
        "Name": "Accessible BGP Service Report",
        "URL": "https://www.shadowserver.org/what-we-do/network-reporting/accessible-bgp-service-report/",
        "Description": "This report identifies accessible Border Gateway Protocol (BGP) servers on port 179/TCP. Updates every 24 hours."
    }
]

# === Inject manual entries if not already in rows ===
existing_titles = {row["Title"] for row in rows}
added_manual_count = 0

for entry in manual_entries:
    if entry["Title"] not in existing_titles:
        print(f"➕ Adding manual entry: {entry['Title']}")
        rows.append(entry)
        added_manual_count += 1
    else:
        print(f"ℹ️ Manual entry already present, skipped: {entry['Title']}")

# === Save CSV ===
with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["Title", "Severity", "Name", "URL", "Description"])
    writer.writeheader()
    writer.writerows(rows)

print(f"\n✅ Saved Phase 1 CSV to: {output_csv}")
print(f"🧾 Total reports saved: {len(rows)} (including {added_manual_count} manual entries)")

# === Print reports with unknown severity (if any) ===
if unknown_severity_rows:
    print("\n⚠️ Reports without explicit severity:")
    for name in unknown_severity_rows:
        print(f"   • {name}")


# === Phase 2: Use downloaded metadata to extract filenames ===
data = []
missing_filenames = []

print("\n🔍 Phase 2: Extracting filenames using existing Phase 1 metadata...\n")

with open(output_csv, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        severity = row["Severity"]
        name = row["Name"]
        url = row["URL"]
        description = row["Description"]
        filename_base = name.lower().replace(" ", "_").replace("/", "_")
        html_path = os.path.join(html_dir, f"{filename_base}.html")
        filename = ""

        try:
            # === Download HTML if not cached ===
            if os.path.exists(html_path):
                print(f"📂 Skipping download (cached): {html_path}")
            else:
                print(f"🌐 Downloading: {url}")
                driver.get(url)
                with open(html_path, "w", encoding="utf-8") as f_html:
                    f_html.write(driver.page_source)
                print("⏳ Sleeping 2s to avoid rate limiting...\n")
                time.sleep(2)


            # === Parse the HTML file ===
            with open(html_path, "r", encoding="utf-8") as f_html:
                soup = BeautifulSoup(f_html.read(), "html.parser")

            # === Extract filename using 4-layer fallback ===
            strong_tags = soup.find_all("strong")
            for tag in strong_tags:
                text = tag.get_text(strip=True)
                # ✅ Explicit check for prefix and colon structure
                if any(text.lower().startswith(x) for x in ["filename:", "filenames:", "filename(s):", "filename prefix(s):"]):
                    if ":" in text:
                        value = text.split(":", 1)[-1].strip()
                        filename = ", ".join(f.strip() for f in value.split(","))
                        print(f"✅ {name} – Filename found (inline): {filename}")
                        break

            # === Remaining fallback logic unchanged ===
            if not filename:
                for p in soup.find_all("p"):
                    strongs = p.find_all("strong")
                    if len(strongs) >= 2:
                        label = strongs[0].get_text(strip=True).lower()
                        if any(x in label for x in ["filename", "filenames", "filename(s)", "filename prefix(s)"]):
                            value = strongs[1].get_text(strip=True)
                            filename = ", ".join(f.strip() for f in value.split(","))
                            print(f"✅ {name} – Filename found (fallback 1): {filename}")
                            break

            if not filename:
                for p in soup.find_all("p"):
                    text = p.get_text(strip=True).lower()
                    if any(x in text for x in ["file name:", "file names:", "file name(s):"]):
                        strong = p.find("strong")
                        if strong:
                            filename = ", ".join(f.strip() for f in strong.text.strip().split(","))
                            print(f"✅ {name} – Filename found (fallback 2): {filename}")
                            break

            if not filename:
                for p in soup.find_all("p"):
                    text = p.get_text(strip=True)
                    if any(text.lower().startswith(x) for x in [
                        "filename:", "filenames:", "filename(s):",
                        "file name:", "file names:", "file name(s):"
                    ]):
                        value = text.split(":", 1)[-1].strip()
                        filename = ", ".join(f.strip() for f in value.split(","))
                        print(f"✅ {name} – Filename found (fallback 3): {filename}")
                        break

            # === Extra: Handle <strong> tag alone with full match like "Filename(s): xyz" ===
            if not filename:
                for strong in soup.find_all("strong"):
                    text = strong.get_text(separator=" ", strip=True).lower()
                    if any(x in text for x in ["filename:", "filenames:", "filename(s):", "filename prefix(s):"]):
                        if ":" in text:
                            value = text.split(":", 1)[-1].strip()
                            filename = ", ".join(f.strip() for f in value.split(","))
                            print(f"✅ {name} – Filename found (fallback 4): {filename}")
                            break

            # === Fallback 5: <strong>Filename prefix: xyz</strong>
            if not filename:
                for strong in soup.find_all("strong"):
                    text = strong.get_text(strip=True)
                    if "filename prefix:" in text.lower():
                        value = text.split(":", 1)[-1].strip()
                        filename = ", ".join(f.strip() for f in value.split(","))
                        print(f"✅ {name} – Filename found (fallback 5): {filename}")
                        break
 

            # === Fallback 6: <strong>Filename: value1, value2</strong>
            if not filename:
                for strong in soup.find_all("strong"):
                    text = strong.get_text(strip=True)
                    if text.lower().startswith("filename:"):
                        value = text.split(":", 1)[-1].strip()
                        filename = ", ".join(f.strip() for f in value.split(","))
                        print(f"✅ {name} – Filename found (fallback 6): {filename}")
                        break

            # === Fallback 8: Search rendered cached HTML for visible text with Selenium
            if not filename and os.path.exists(html_path):
                try:
                    from pathlib import Path
                    local_html_url = Path(html_path).absolute().as_uri()
                    driver.get(local_html_url)
                    print(f"🔎 Scanning cached HTML: {local_html_url}")
                    time.sleep(1)  # Give browser time to render

                    markers = [
                        "filename:", "filenames:", "filename(s):", "filename prefix:"
                    ]

                    body_text = driver.find_element("tag name", "body").text.lower()
                    for marker in markers:
                        if marker in body_text:
                            start = body_text.find(marker) + len(marker)
                            snippet = body_text[start:start + 200].splitlines()[0]
                            candidates = [f.strip() for f in snippet.split(",") if f.strip()]
                            if candidates:
                                filename = ", ".join(candidates)
                                print(f"✅ {name} – Filename found (fallback 8 - cached render): {filename}")
                                break
                except Exception as e:
                    print(f"⚠️ {name} – Fallback 8 (cached render) failed: {e}")





            if not filename:
                print(f"❌ {name} – Filename not found.")
                missing_filenames.append({"name": name, "url": url})


            data.append({
                "Severity": severity,
                "Title": name,
                "URL": url,
                "Description": description,
                "Filename": filename
            })

        except Exception as e:
            print(f"❌ Error processing {name}: {e}")
            missing_filenames.append(name)

driver.quit()

# === Save final CSV ===
with open(final_output_file, mode="w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["Severity", "Title", "URL", "Description", "Filename"])
    writer.writeheader()
    writer.writerows(data)

print(f"\n✅ Phase 2 completed. Saved {len(data)} entries to: {final_output_file}")

if missing_filenames:
    print("\n📄 Reports without 'Filename:' found:")
    for t in missing_filenames:
        print(f"   • {t['name']} → {t['url']}")

    print("\n✅ All reports included a filename.")

