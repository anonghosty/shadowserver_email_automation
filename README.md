# Shadowserver Report Ingestion & Intelligence Toolkit

**Author:** Ike Owuraku Amponsah\
**LinkedIn:** [https://www.linkedin.com/in/iowuraku](https://www.linkedin.com/in/iowuraku)\
**License:** [MIT (Modified - No Resale)](./LICENSE)

---
## Documentation 
https://anonghosty.github.io/shadowserver_email_automation/

## Overview

This project automates the collection, parsing, categorization, and reporting of threat intelligence feeds from [Shadowserver](https://www.shadowserver.org/), eliminating the complexities many CERTs have faced for years.

Key features include:

- IMAP basic authentication email ingestion (generic)
- Archive and attachment extraction (ZIP, RAR, 7z)
- CSV validation, geo/IP/ASN enrichment
- Organization mapping and alert tracking
- 3 flavored variations for report generation daily - CSV {can be used in automation}, PDF {can be be used in official reporting}, HTML {has charts and search bars}
- Full support for MongoDB-backed enrichment
- Chrome + Selenium automation for scraping report metadata

---
---
Update: On the First of August 2025, I received an email from the National CSIRT of Kenya regarding an issue related to O365 and Google Workspace limitations with IMAP. CSIRT Kenya highlighted the issue affecting users on the said platforms and shared a solution which will be implemented. In case you would want to review the details and the solution, here is the document:

[Feedback on KE National CSIRT Implementation of O365 and Gmail (2025-08-02)](docs/feedback_ke_national_csirt_implementation_of_0365_and_gmail_20250802.pdf)
---
## Project Structure

MongoDB is required. See: [https://www.howtoforge.com/tutorial/install-mongodb-on-ubuntu/](https://www.howtoforge.com/tutorial/install-mongodb-on-ubuntu/)\
Get latest Mongo repo here: [https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-ubuntu/](https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-ubuntu/)

```Toolkit
.
├── bootstrap_shadowserver_environment.py         # Sets up OS, pip, Chrome & ChromeDriver
├── install_python_and_run_bootstrap.sh           # Prepares system with Python3 & pip
├── generate_statistics_reported_from_shadowserver_unverified.py
├── get_shadowserver_report_types.py
├── shadow_server_data_analysis_system_builder_and_updater.py
├── LICENSE                                       # MIT (Modified)
├── .env                                          # Configuration file
└── README.md
```

---

## System Requirements

### OS-Level Dependencies (Ubuntu)

```bash
| #  | Package              | Purpose                                                                  |
| -- | -------------------- | ------------------------------------------------------------------------ |
| 1  | `python3`            | Python interpreter for executing the application                         |
| 2  | `python3-pip`        | Python package manager used to install dependencies                      |
| 3  | `unzip`              | Utility for extracting `.zip` files                                      |
| 4  | `zip`                | Utility for creating `.zip` archives                                     |
| 5  | `p7zip-full`         | Full-featured 7-Zip tool for `.7z` archive extraction                    |
| 6  | `p7zip-rar`          | Enables RAR archive support in 7-Zip                                     |
| 7  | `unrar`              | Standalone utility for extracting `.rar` files                           |
| 8  | `libnss3`            | Required security library for Chrome/Chromium (used by Selenium)         |
| 9  | `libxss1`            | X11 Screen Saver extension (required for headless browser stability)     |
| 10 | `libappindicator3-1` | Enables application indicators in headless browser environments          |
| 11 | `fonts-liberation`   | Provides standard web fonts used in headless Chrome rendering            |
| 12 | `whois`              | Performs ASN and WHOIS lookups for IP metadata enrichment                |
| 13 | `wget`               | Command-line tool to download files and data from the web                |
| 14 | `ca-certificates`    | Installs trusted CA certificates for secure HTTPS communication          |
| 15 | `gnupg`              | Enables digital signing, encryption, and verification                    |
| 16 | `lsb-release`        | Provides distro version info for environment detection and compatibility |


```

> All non-inbuilt requirements are installed with the setup scripts

---

## Python Dependencies

Install via pip:
```Packages
| #  | Package          | Purpose                                                         |
| -- | ---------------- | --------------------------------------------------------------- |
| 1  | `aiofiles`       | Asynchronous file operations without blocking the event loop    |
| 2  | `aiohttp`        | Asynchronous HTTP requests and web client support               |
| 3  | `async-lru`      | Caching for async functions to improve performance              |
| 4  | `beautifulsoup4` | HTML/XML parsing for web scraping and document analysis         |
| 5  | `bs4`            | Import alias for BeautifulSoup (required by some packages)      |
| 6  | `colorama`       | Cross-platform colored terminal output                          |
| 7  | `pandas`         | High-level data structures and analysis tools for CSV/JSON      |
| 8  | `pymongo`        | MongoDB driver to insert and query intelligence data            |
| 9  | `py7zr`          | 7-Zip archive extraction and creation                           |
| 10 | `rarfile`        | Handle `.rar` files                                             |
| 11 | `reportlab`      | Generate structured PDF reports dynamically                     |
| 12 | `selenium`       | Web automation for browser-based scraping or headless downloads |
| 13 | `tqdm`           | Lightweight progress bars in loops and pipelines                |
| 14 | `python-dotenv`  | Load environment variables from `.env` for config and secrets   |

```

---

## Environment Configuration (`.env`)

<details>
<summary>Click to view example .env configuration</summary>

```dotenv
# MongoDB credentials
mongo_username="anon"
mongo_password="input password"
mongo_auth_source="admin"  # change if using a different auth DB
mongo_host="127.0.0.1"
mongo_port=27017

# Email settings
mail_server="mail.example.com"
email_address="cookies@example.com"
email_password="cookiesonthelu"
imap_shadowserver_folder_or_email_processing_folder="INBOX"

# Advisory metadata (Future Plans)
advisory_prefix="default-cert-"

# Report metadata
reference_nomenclature="default-cert-stat-"
cert_name="DEFAULT-CERT"

# ====== Performance Settings ======
buffer_size="1024"
flush_row_count=100
tracker_batch_size=1000
service_sorting_batch_size=1000
number_of_files_ingested_into_knowledgebase_per_batch=2000

# ====== REGEX SECTION ======
# Replace "<input_country_here>" with the country name in lowercase

geo_csv_regex="^\\d{4}-\\d{2}-\\d{2}-(.*?)-<input_country_here>-geo_as\\d+\\.csv$"
geo_csv_fallback_regex="^\\d{4}-\\d{2}-\\d{2}-(.*?)(?:-\\d{3})?-<input_country_here>_as\\d+\\.csv$"

# ====== Feature Spotlight: Anomaly Pattern Detection ======

#=Special Detection In Case Of Issues---run just service flag to troubleshoot----
#Increase the number of anomaly pattern checks
anomaly_pattern_count=5

#Real Life Scenarios
# Anomaly patterns for Shadowserver consultationv -Blocked_IPs Report
enable_anomaly_pattern_1="true"
anomaly_pattern_1="^\d{4}-\d{2}-\d{2}-(\d+)_as\d+\.csv$"

#Detected government asn naming at suffix 
enable_anomaly_pattern_2="true"
anomaly_pattern_2="^\d{4}-\d{2}-\d{2}-(.*?)-<input_country_here>[_-][a-z0-9\-]*_as\d+\.csv$"

#Ransomware Reports Service Sorting
enable_anomaly_pattern_3="true"
anomaly_pattern_3="^\d{4}-\d{2}-\d{2}-(.*?)-<input_country_here>-geo\.csv$"


enable_anomaly_pattern_4="false"
anomaly_pattern_4=""
```
</details> 

---

## Bootstrap the Environment

Run:

```bash
chmod +x install_python_and_run_bootstrap.sh
./install_python_and_run_bootstrap.sh
```

This script will:

- Install Python3 and pip
- Run `bootstrap_shadowserver_environment.py` to install:
  - Required pip packages
  - Google Chrome
  - Matching ChromeDriver
  - System dependencies

---

## Ingest Shadowserver Reports via IMAP

```bash
Sequence: Really Important To Observe the sequence so you can build flavors in automation

+---------+     +---------+     +----------+     +-----------+     +-----------+     +--------+
|  email  | --> | refresh | --> | process  | --> |  country  | --> |  service  | --> | ingest |
+---------+     +---------+     +----------+     +-----------+     +-----------+     +--------+
     │              │               │                 │                 │               │
     ▼              ▼               ▼                 ▼                 ▼               ▼
 Pull Emails   Refresh ASN/    Normalize &     Sort by Country    Sort by Service   Ingest into
 & Extract     WHOIS Info     Parse Reports     (ISO 3166-1)       (Report Type)   Knowledgebase
Attachments


python3 shadow_server_data_analysis_system_builder_and_updater.py [email|refresh|process|country|service|ingest|all] [--tracker] [--tracker=auto] [--tracker-service=auto|manual|off] [--tracker-ingest=auto|manual|off]

email   → Pull Emails Including Shadowserver Reports, Save as EML, and Extract Attachments  
refresh → Refresh Stored ASN/WHOIS data from Previous Shadowserver Reports  
process → Parse and Normalize Shadowserver CSV/JSON Files  
country → Sort Processed Reports by Country Code (based on IP WHOIS geolocation)  
service → Sort Processed Reports by Detected Service Type (via Filename Pattern Analysis)  
ingest  → Ingest Cleaned Shadowserver Data into the Knowledgebase (Databases & Collections)
```
### 🧭 Task Flow When Using `all`

```text
email   → Pull Emails and Extract Shadowserver Attachments
   ↓
refresh → Refresh Stored ASN/WHOIS data
   ↓
process → Normalize and Parse Extracted CSV/JSON Reports
   ↓
country → Sort by IP Country Code (ISO 3166-1)
   ↓
service → Sort by Shadowserver Report Type Patterns
   ↓
ingest  → Ingest Parsed Data into Local/Cloud Knowledgebase (Mongodb Instance)


```
Examples:

```bash
# Ingest emails only
python3 shadow_server_data_analysis_system_builder_and_updater.py email

# Run email, processing, and country mapping with auto tracking
python3 shadow_server_data_analysis_system_builder_and_updater.py all --tracker=auto

# Only process downloaded reports without ingestion
python3 shadow_server_data_analysis_system_builder_and_updater.py process --tracker-service=manual

# Choose a sequential execution pattern (flavor):
python3 shadow_server_data_analysis_system_builder_and_updater.py email process country service
python3 shadow_server_data_analysis_system_builder_and_updater.py email refresh country service
python3 shadow_server_data_analysis_system_builder_and_updater.py refresh country service ingest


```
---

## Scrape Shadowserver Report Metadata (Run Before Report Generation)

```bash
python3 get_shadowserver_report_types.py
```

Stores output in:

- HTML: `shadowserver_report_types_http_files/`
- CSV: `shadowserver_url_descriptions/`
---

## Generate Statistics Per Organization

Use a constituent map in `shadowserver_analysis_system/detected_companies/constituent_map.csv`.
Place company logo  named as "logo.png" in base directory
```bash
python3 generate_statistics_reported_from_shadowserver_unverified.py
```

Outputs:

- CSVs and PDFs under `statistical_data/<org>/`
- ASN-category maps, IP prefixes, summary counts


---

## License

MIT License (Modified - No Resale)

```
MIT License (No Commercial Resale)

Copyright (c) 2025 Ike Owuraku Amponsah

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to use,
copy, modify, merge, publish, and distribute the Software for non-commercial
and internal purposes, subject to the following conditions:

- The Software may not be sold, sublicensed for profit, or repurposed as part
  of a commercial product or service offering without the explicit written
  permission of the copyright holder.

- This license does not grant permission to repackage or resell the Software,
  in whole or in part, as a commercial product.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```



