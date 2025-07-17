# Shadowserver Report Ingestion & Intelligence Framework

**Author:** Ike Owuraku Amponsah\
**LinkedIn:** [https://www.linkedin.com/in/iowuraku](https://www.linkedin.com/in/iowuraku)\
**License:** [MIT (Modified - No Resale)](./LICENSE)

---

## Overview

This project automates the collection, parsing, categorization, and reporting of threat intelligence feeds from [Shadowserver](https://www.shadowserver.org/), eliminating the complexities many CERTs have faced for years.

Key features include:

- IMAP email ingestion (generic)
- Archive and attachment extraction (ZIP, RAR, 7z)
- CSV validation, geo/IP/ASN enrichment
- Organization mapping and alert tracking
- Daily PDF/CSV statistical summaries
- Full support for MongoDB-backed enrichment
- Chrome + Selenium automation for scraping report metadata

---

## Project Structure

MongoDB is required. See: [https://www.howtoforge.com/tutorial/install-mongodb-on-ubuntu/](https://www.howtoforge.com/tutorial/install-mongodb-on-ubuntu/)\
Get latest Mongo repo here: [https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-ubuntu/](https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-ubuntu/)

```bash
.
├── bootstrap_shadowserver_environment.py         # Sets up OS, pip, Chrome & ChromeDriver
├── install_python_and_run_bootstrap.sh           # Prepares system with Python3 & pip
├── generate_statistics_reported_from_shadowserver_unverified.py
├── get_shadowserver_report_types.py
├── shadow_server_data_analysis_system_builder_and_updater.py
├── shadowserver_url_descriptions/                # Cached metadata from Shadowserver site
├── statistical_data/                             # Daily per-org PDF/CSV reports
├── reported_companies/                           # Normalized and enriched ingested reports
├── LICENSE                                       # MIT (Modified)
├── .env                                          # Configuration file
└── README.md
```

---

## System Requirements

### OS-Level Dependencies (Ubuntu)

```bash
sudo apt update && sudo apt install -y \
    python3 python3-pip unzip zip \
    p7zip-full p7zip-rar unrar \
    libnss3 libxss1 libappindicator3-1 fonts-liberation \
    whois wget ca-certificates gnupg lsb-release
```

> Google Chrome and ChromeDriver are auto-installed via the Python bootstrap script.

---

## Python Dependencies

Install via pip:

```bash
pip3 install -r requirements.txt
```

```txt
aiofiles
aiohttp
async-lru
beautifulsoup4
bs4
colorama
pandas
pymongo
py7zr
rarfile
reportlab
selenium
tqdm
python-dotenv
```

---

## Environment Configuration (`.env`)

Example `.env` file:

```dotenv
# MongoDB connection
mongo_username="your_user"
mongo_password="your_pass"
mongo_auth_source="admin"
mongo_host="127.0.0.1"
mongo_port=27017

# Email credentials
imap_server="imap.example.com"
email_address="alerts@example.com"
email_password="your_email_password"

# Regex patterns for filename classification
geo_csv_regex="^\\d{4}-\\d{2}-\\d{2}-(.*?)\\-ghana\\-geo_as\\d+\\.csv$"
geo_csv_fallback_regex="^\\d{4}-\\d{2}-\\d{2}-(.*?)\\-\\d+\\-ghana\\-geo_as\\d+\\.csv$"
```

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
python3 shadow_server_data_analysis_system_builder_and_updater.py [email|refresh|process|country|service|ingest|all] [--tracker] [--tracker=auto] [--tracker-service=auto|manual|off] [--tracker-ingest=auto|manual|off]
```

Examples:

```bash
# Ingest emails only
python3 shadow_server_data_analysis_system_builder_and_updater.py email

# Run email, processing, and country mapping with auto tracking
python3 shadow_server_data_analysis_system_builder_and_updater.py all --tracker=auto

# Only process downloaded reports without ingestion
python3 shadow_server_data_analysis_system_builder_and_updater.py process --tracker-service=manual
```

---

## Generate Statistics Per Organization

Use a constituent map in `shadowserver_analysis_system/detected_companies/constituent_map.csv`.

```bash
python3 generate_statistics_reported_from_shadowserver_unverified.py
```

Outputs:

- CSVs and PDFs under `statistical_data/<org>/`
- ASN-category maps, IP prefixes, summary counts

---

## Scrape Shadowserver Report Metadata

```bash
python3 get_shadowserver_report_types.py
```

Stores output in:

- HTML: `shadowserver_report_types_http_files/`
- CSV: `shadowserver_url_descriptions/`

---

## License

MIT License (Modified - No Resale)

```
MIT License (Modified - No Commercial Resale)

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

# Summary
Automates the ingestion, parsing, validation of ASN, and processing of Shadowserver reports received via email. Includes support for attachment extraction, file integrity checks, ASN resolution, country-based sorting, and audit logging. Designed for CERTs and security teams to streamline threat intelligence workflows.

