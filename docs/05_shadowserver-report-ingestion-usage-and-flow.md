---
title: 05 Shadowserver Report Ingestion - Usage & Flow
---
# 📥 Shadowserver Report Ingestion - Usage & Flow 
(0365 and Google Workspace Usera Kindly Should Kindly See the Solution From Kenyan National CSIRT)

This section explains how to run the Shadowserver ingestion pipeline using the core CLI entry point:  
**`shadow_server_data_analysis_system_builder_and_updater.py`**

---
## Update – 1st August 2025

On the First of August 2025, I received a message from the National CSIRT of Kenya regarding an issue related to O365 and Gmail limitations with IMAP. CSIRT Kenya highlighted the issue affecting users on the said platforms and shared a solution which will be implemented. In case you would want to review the details and the solution, here is the document:

[Feedback on KE National CSIRT Implementation of O365 and Gmail (2025-08-02)](feedback_ke_national_csirt_implementation_of_0365_and_gmail_20250802.pdf)

---

## Tutorial – Setting up O365 Application for Microsoft Graph

For organizations needing to configure an O365 application to interact with Microsoft Graph securely and correctly, CSIRT Kenya also provided a setup guide. You can find the tutorial below:

[National KE CSIRT Steps for O365 Application Creation (2025-02-08)](national_ke_csirt_steps_0365_application_creation_20250208.pdf)

---
---

## 🧪 CLI Syntax

```bash
python3 shadow_server_data_analysis_system_builder_and_updater.py [task] [options]
```

### Tasks:

| Task      | Description                                                                 |
|-----------|-----------------------------------------------------------------------------|
| `email`   | Pulls IMAP emails, saves `.eml`, and extracts attachments                   |
| `refresh` | Refresh ASN and WHOIS data for existing Shadowserver files                  |
| `process` | Normalizes CSVs/JSONs, checks format, enriches with IP/ASN/geo metadata     |
| `country` | Sorts processed data by `Country` (ISO 3166-1 alpha-2 codes)                |
| `service` | Sorts processed files by Shadowserver service type (filename pattern-based) |
| `ingest`  | Ingests enriched and sorted data into MongoDB                               |
| `all`     | Executes the full pipeline sequentially: email → refresh → process → ...    |

### Options:

| Option                       | Description                                                           |
|------------------------------|-----------------------------------------------------------------------|
| `--tracker`                  | Enables global tracker mode (`auto`, `manual`, `off`)                 |
| `--tracker-service=mode`     | Set tracker mode specifically for `service` step                      |
| `--tracker-ingest=mode`      | Set tracker mode specifically for `ingest` step                       |

---

## 🔄 Full Ingestion Flow (Sequential)

```
+---------+     +---------+     +---------+     +----------+     +-----------+     +-----------+     +--------+
|  email  | --> | migrate | --> | refresh | --> | process  | --> |  country  | --> |  service  | --> | ingest |
+---------+     +---------+     +---------+     +----------+     +-----------+     +-----------+     +--------+
     │              │               │               │                 │                 │               │
     ▼              ▼               ▼               ▼                 ▼                 ▼               ▼
Pull Emails   Sort Extensions    Refresh ASN/   Normalize &     Sort by Country    Sort by Service   Ingest into              
& Extract     Unzip and Extract  WHOIS Info     Parse Reports   (ISO 3166-1)       (Report Type)     Knowledgebase
Attachments   Reports Advisories
              From Attachments
              Directory




```
### 📬 Email Ingestion Sub-Methods

| #  | Method             | Description                                                                 |
|----|--------------------|-----------------------------------------------------------------------------|
| 1  | **IMAP**           | Connects directly to mailbox via IMAP, extracts `.eml`, and saves attachments. |
| 2  | **Microsoft Graph**| Uses Microsoft Graph API with OAuth2 for inbox access and attachment parsing. |
| 3  | **Google Workspace**| Accesses Gmail API with OAuth2 credentials to retrieve and extract files.     |

---

## 🧭 Task Flow When Using `all`

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

---

## 💡 Example Usage

```bash
# Ingest emails only
python3 shadow_server_data_analysis_system_builder_and_updater.py email

# Run full pipeline with auto tracker
python3 shadow_server_data_analysis_system_builder_and_updater.py all --tracker=auto

# Only process, skip ingest
python3 shadow_server_data_analysis_system_builder_and_updater.py process --tracker-service=manual

# Custom flow (recommended for tuning)
python3 shadow_server_data_analysis_system_builder_and_updater.py email process country service
python3 shadow_server_data_analysis_system_builder_and_updater.py email refresh country service
python3 shadow_server_data_analysis_system_builder_and_updater.py refresh country service ingest
```

---

## ✅ Tips

- Use `all` or ` other combinations (to manage resources) ` to automate the full pipeline for daily CRON or service mode.
- Use `manual` tracker mode for dry-runs and QA.
- Tracker settings help avoid duplicate processing.
- Monitor MongoDB ingestion counts to validate data is flowing into your DB.

---

