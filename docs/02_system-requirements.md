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

| #   | Package          | Purpose                                                                 |
|-----|------------------|-------------------------------------------------------------------------|
| 1   | `aiofiles`       | Async file read/write                                                  |
| 2   | `aiohttp`        | Async HTTP requests                                                    |
| 3   | `async-lru`      | Caching for async operations                                           |
| 4   | `beautifulsoup4` | HTML/XML parsing                                                       |
| 5   | `bs4`            | Alias for BeautifulSoup                                                |
| 6   | `colorama`       | Terminal color output                                                  |
| 7   | `pandas`         | DataFrame-based parsing and processing                                 |
| 8   | `pymongo`        | MongoDB driver                                                         |
| 9   | `py7zr`          | 7-Zip archive extraction                                               |
| 10  | `rarfile`        | `.rar` support                                                         |
| 11  | `reportlab`      | PDF generation                                                         |
| 12  | `selenium`       | Headless browser automation                                            |
| 13  | `tqdm`           | Progress bar                                                           |
| 14  | `python-dotenv`  | Load configuration from `.env`                                         |
