---
title: 07 Organization-Based Shadowserver Report Generator
---
# 📊 Organization-Based Shadowserver Report Generator

This module analyzes enriched Shadowserver data by mapping **ASNs to organizations** to generate statistical reports in both **CSV and PDF** formats.

---
## Company Logo
Place company logo named "logo.png" in Base Directory

## 🗂️ Expected `constituent_map.csv` Format

This file maps organizations to the ASNs they are responsible for. It's used to isolate Shadowserver-reported IPs by ASN ownership.

| Column     | Description                                                                                                                                                                                  |
| ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `org_name` | **Organization Name** — A label used to identify the entity (e.g., MTN). This will be used to create folders under `statistical_data/`.                                                      |
| `asn`      | **Autonomous System Number(s)** — A single ASN or a comma-separated list of ASNs that belong to the organization. Each will be matched against MongoDB databases with names like `_as{ASN}`. |





### 🧾 Example Structure

```csv

#Delimiter Structure

org_name,asn
COMPANY A,30986
COMPANY B,29614

How It Looks as a Table in Excel as CSV format

| org\_name | asn   |
| --------- | ----- |
| COMPANY A | 30986 |
| COMPANY B | 29614 |


```
- Multiple ASNs can be comma-separated in the `asn` column.
- `org_name` will be used as the folder name for reports.

---

## ⚙️ How the Report Generator Works

1. **Load Org→ASN Map**: Reads `constituent_map.csv` into a dictionary.
2. **Database Matching**: Scans MongoDB for databases named like `_as{ASN}` to associate them with an org.
3. **Data Extraction**:
   - Loops through MongoDB collections under matching databases.
   - Filters documents from **yesterday’s date** using `extracted_date` field.
   - Extracts IPs (`ip`, `src_ip`, `http_referer_ip`) and determines:
     - Associated ASN
     - Shadowserver report category
     - Inferred prefix is /24 which is genereric and needs to be confirmed by the stakeholder or analyst
4. **Category & Prefix Grouping**:
   - Groups IPs by prefix and category frequency.
   - Calculates how many IPs appear under each prefix.
   - Tracks ASN→Category map for multi-ASN attribution.
5. **Report Output**:
   - Writes all summarized data into a CSV.
   - Generates a PDF with:
     - Executive summary
     - Detailed table of IPs, prefixes, ASNs, and categories
     - Prefix → IP count table
     - Category table with severity, titles, descriptions, and reference URLs
6. **Reference Tracking**:
   - A unique reference is generated using the SHA-256 hash of the CSV.
   - Logs reference into `reference_system.<org>` collection.
7. **Memory Cleanup**:
   - Clears variables and performs garbage collection after each org is processed.

---

## 📤 Output Location

Reports are saved under:

```
statistical_data/<org>/
├── <org>_reported_shadowserverver_events_<date>.csv
├── <org>_reported_shadowserverver_events_<date>.html
└── <org>_reported_shadowserverver_events_<date>.pdf
```

---

## 🔐 Reference System

Each report has a **reference number** derived from its CSV hash and logged with metadata such as:

- `org_name`
- `filename`
- `generated_on`
- `report_category`: Always `statistical_report`
- `tlp_label`: Always `AMBER`

Stored in MongoDB `reference_system` database per org.

---

## 📎 Requirements

- MongoDB with extracted Shadowserver data (via previous `ingest` steps)
- Environment variables:
  - `cert_name` – used in PDF footer
  - `reference_nomenclature` – prefix for reference numbers

---

## 📄 PDF Sections

1. **Title Page & Summary**
2. **Detailed Table of IPs and Categories**
3. **Prefix Summary Table**
4. **Category Summary Table (with metadata from `shadowserver_report_types.csv`)**
5. **Page footer with TLP:AMBER, reference, and page number**

---

## 🧼 Notes

- Category names are cleaned (e.g., remove suffixes like `-318` - this is inline and will be updated).
- Prefix inference: `/24` for IPv4, `/64` for IPv6.
- PDF uses colors to represent severity levels for easy triage.

