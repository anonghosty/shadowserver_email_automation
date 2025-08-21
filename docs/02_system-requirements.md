---
title: 02 System Requirements
---
# System Requirements

---

## OS-Level Dependencies (Ubuntu)

| #   | Package              | Purpose                                                                 |
|-----|----------------------|-------------------------------------------------------------------------|
| 1   | `python3`            | Python interpreter                                                      |
| 2   | `python3-pip`        | Install Python packages                                                 |
| 3   | `unzip`              | Extract `.zip` files                                                    |
| 4   | `zip`                | Create `.zip` files                                                     |
| 5   | `p7zip-full`         | Handle `.7z` files                                                      |
| 6   | `p7zip-rar`          | Add `.rar` support to 7-Zip                                            |
| 7   | `unrar`              | Extract `.rar` archives                                                 |
| 8   | `libnss3`            | Required by Chrome for secure communication                            |
| 9   | `libxss1`            | Ensures Chrome stability in headless mode                              |
| 10  | `libappindicator3-1` | UI indicators for headless Chrome                                       |
| 11  | `fonts-liberation`   | Common font pack for browser rendering                                 |
| 12  | `whois`              | IP-to-ASN and WHOIS lookups                                             |
| 13  | `wget`               | Web download utility                                                    |
| 14  | `ca-certificates`    | Trusted CA root certificates                                            |
| 15  | `gnupg`              | Encryption/signing for secure operations                               |
| 16  | `lsb-release`        | Detect OS distro/version                                                |

> ✅ All dependencies can be installed with the bootstrap script.

---

## Python Package Dependencies

| #  | Package          | Purpose                                                                                |
| -- | ---------------- | -------------------------------------------------------------------------------------- |
| 1  | `aiofiles`       | Asynchronous file operations without blocking the event loop                           |
| 2  | `aiohttp`        | Asynchronous HTTP requests and web client support                                      |
| 3  | `async-lru`      | Caching for async functions to improve performance                                     |
| 4  | `beautifulsoup4` | HTML/XML parsing for web scraping and document analysis                                |
| 5  | `bs4`            | Import alias for BeautifulSoup (required by some packages)                             |
| 6  | `colorama`       | Cross-platform colored terminal output                                                 |
| 7  | `pandas`         | High-level data structures and analysis tools for CSV/JSON                             |
| 8  | `pymongo`        | MongoDB driver to insert and query intelligence data                                   |
| 9  | `py7zr`          | 7-Zip archive extraction and creation                                                  |
| 10 | `rarfile`        | Handle `.rar` files                                                                    |
| 11 | `reportlab`      | Generate structured PDF reports dynamically                                            |
| 12 | `selenium`       | Web automation for browser-based scraping or headless downloads                        |
| 13 | `tqdm`           | Lightweight progress bars in loops and pipelines                                       |
| 14 | `python-dotenv`  | Load environment variables from `.env` for config and secrets                          |
| 15 | `msal`           | Microsoft Authentication Library for Azure AD integration and secure token acquisition |
| 16 | `dash`           | Framework for building interactive web dashboards using Python                         |
| 17 | `geopandas`      | Extend Pandas for geospatial data handling and mapping                                 |
| 18 | `pycountry`      | Access ISO country, subdivision, currency, and language lists                          |
| 19 | `matplotlib`     | Data visualization and chart plotting for analytics and reports                        |

