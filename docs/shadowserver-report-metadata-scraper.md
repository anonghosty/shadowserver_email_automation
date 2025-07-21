# 🌐 Shadowserver Report Metadata Scraper

This component scrapes live Shadowserver.org report metadata and stores structured reference data for use in intelligence reports and ingestion logic.

---

## 🔧 Script: `get_shadowserver_report_types.py`

### ✅ Purpose

- Automates the collection of **report titles**, **URLs**, **descriptions**, and **filenames**
- Powers classification, tagging, and enrichment of Shadowserver CSV reports
- Ensures dynamic tracking of **new**, **retired**, or **revised** Shadowserver reports

---

## 🚀 Usage

```bash
python3 get_shadowserver_report_types.py
```

---

## 📁 Output Structure

| Output Format | Path                                      | Description                                                   |
|---------------|-------------------------------------------|---------------------------------------------------------------|
| `.html`       | `shadowserver_report_types_http_files/`   | Raw HTML pages from Shadowserver site (cached copies)         |
| `.csv`        | `shadowserver_url_descriptions/`          | Parsed metadata output including title, URL, filename, etc.   |

---

## 🧠 Output Fields (CSV)

The resulting `shadowserver_report_types.csv` contains the following fields:

| Column        | Description                                                                 |
|---------------|-----------------------------------------------------------------------------|
| `Severity`    | Risk/impact level from Shadowserver (e.g. `Critical`, `High`, etc.)         |
| `Title`       | Full name of the report (used in classification and PDF headers)            |
| `Description` | Summary of the report purpose/content                                        |
| `URL`         | Direct link to the Shadowserver report description                          |
| `Filename`    | Canonical filename pattern or identifier expected in raw Shadowserver ZIP/CSV       |

---

## 🗂️ Example Files After Execution

```text
shadowserver_report_types_http_files/
├── accessible_activemq_service_report.html
├── accessible_amqp_report.html
└── accessible_bgp_service_report.html

shadowserver_url_descriptions/
├── shadowserver_description_check.csv
├── shadowserver_report_types.csv
```

---

## 🔁 When to Run

| Scenario                               | Recommendation |
|----------------------------------------|----------------|
| First setup of the toolkit             | ✅ Run it      |
| New Shadowserver report released       | ✅ Run it      |
| Monthly pipeline maintenance           | ✅ Run it      |
| Building or updating classifications   | ✅ Run it      |

---

## 📌 Integration Note

The output `.csv` can be consumed by other scripts for:

- **Tag enrichment**
- **Alert generation**
- **PDF/CSV statistical report labelling**
- **Filtering or categorizing files on disk**

---

