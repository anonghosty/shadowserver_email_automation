---
title: Environment Variables Explained
---
# Environment Variables Explained

The `.env` file is used to configure runtime parameters like MongoDB access, email ingestion, metadata logic, anomaly detection, and batch processing. This enables safe, dynamic configuration without modifying the codebase.

---

## 🔐 MongoDB Settings

| Variable           | Purpose                                                                 |
|--------------------|-------------------------------------------------------------------------|
| `mongo_username`   | MongoDB username used for authentication                                |
| `mongo_password`   | Password for the MongoDB user                                           |
| `mongo_auth_source`| Authentication database (e.g., `admin`)                                |
| `mongo_host`       | MongoDB host (default: `127.0.0.1` for localhost)                       |
| `mongo_port`       | MongoDB port (default: `27017`)                                         |

> These values are required for connecting to your local or remote MongoDB database.

---

## 📩 Email Server Configuration

| Variable                                            | Purpose                                                                 |
|-----------------------------------------------------|-------------------------------------------------------------------------|
| `mail_server`                                       | IMAP mail server (e.g., `imap.gmail.com`)                               |
| `email_address`                                     | Email address that receives Shadowserver reports                        |
| `email_password`                                    | Email account password or app-specific password                         |
| `imap_shadowserver_folder_or_email_processing_folder` | IMAP folder to read from (e.g., `INBOX`, `Shadowserver`)               |

> Used to pull, authenticate, and scan Shadowserver email reports.

---

## 🧾 Report Metadata Settings (Upcoming Features)

| Variable                 | Purpose                                                             |
|--------------------------|---------------------------------------------------------------------|
| `advisory_prefix`        | Prefix used in generated advisories or alerts                      |
| `reference_nomenclature`| Prefix used in report/statistics filenames                          |
| `cert_name`              | CERT or SOC name used in reports or metadata                       |

> These fields allow you to personalize output for your CERT/SOC branding.

---

## ⚙️ Performance & Batch Processing

| Variable                                               | Purpose                                                                 |
|--------------------------------------------------------|-------------------------------------------------------------------------|
| `buffer_size`                                          | IO buffer size (affects read/write speed)                              |
| `flush_row_count`                                      | Number of rows after which buffers flush to memory/disk                |
| `tracker_batch_size`                                   | Number of rows to analyze per tracker run                              |
| `service_sorting_batch_size`                           | How many files to process at once during the `service` step            |
| `number_of_files_ingested_into_knowledgebase_per_batch`| Controls DB load per ingestion cycle                                   |

> These allow scaling to large datasets by tuning resource usage and responsiveness.

---

## 🧬 Filename Regex Matching

| Variable               | Purpose                                                                 |
|------------------------|-------------------------------------------------------------------------|
| `geo_csv_regex`        | Standard regex pattern for GEO-based Shadowserver filenames              |
| `geo_csv_fallback_regex` | New Detected Standard regex pattern for GEO-based Shadowserver filenames                     |

> Replace `<input_country_here>` with the lowercase country name (e.g., `ghana`, `kenya`).

---

## 🧭 Anomaly Detection Patterns

| Variable                  | Purpose                                                        |
|---------------------------|----------------------------------------------------------------|
| `anomaly_pattern_count`   | Total number of anomaly patterns to be validated               |
| `enable_anomaly_pattern_N`| Enables/disables the corresponding `anomaly_pattern_N`         |
| `anomaly_pattern_N`       | Regex pattern to match anomalies in Shadowserver filenames     |

> You can define multiple anomaly detection rules using numbered keys (1 to N).

---

### 🔍 Example Use Case

```dotenv
anomaly_pattern_count=3

enable_anomaly_pattern_1="true"
anomaly_pattern_1="^\d{4}-\d{2}-\d{2}-(\d+)_as\d+\.csv$"

enable_anomaly_pattern_2="true"
anomaly_pattern_2="^\d{4}-\d{2}-\d{2}-(.*?)-ghana[_-][a-z0-9\-]*_as\d+\.csv$"

enable_anomaly_pattern_3="true"
anomaly_pattern_3="^\d{4}-\d{2}-\d{2}-(.*?)-ghana-geo\.csv$"

---

# Example .env Template

# --- MongoDB ---
mongo_username="certops"
mongo_password="changeme"
mongo_auth_source="admin"
mongo_host="127.0.0.1"
mongo_port=27017

# --- Email ---
mail_server="imap.example.com"
email_address="intel@example.com"
email_password="strongpassword"
imap_shadowserver_folder_or_email_processing_folder="INBOX"

# --- Metadata ---
advisory_prefix="cert-gh-advisory-"
reference_nomenclature="cert-stat-"
cert_name="GH-CERT"

# --- Performance ---
buffer_size="2048"
flush_row_count=500
tracker_batch_size=1000
service_sorting_batch_size=1000
number_of_files_ingested_into_knowledgebase_per_batch=2000

# --- Regex Patterns ---
geo_csv_regex="^\\d{4}-\\d{2}-\\d{2}-(.*?)-ghana-geo_as\\d+\\.csv$"
geo_csv_fallback_regex="^\\d{4}-\\d{2}-\\d{2}-(.*?)-ghana_as\\d+\\.csv$"

# --- Anomaly Patterns ---
anomaly_pattern_count=3

enable_anomaly_pattern_1="true"
anomaly_pattern_1="^\\d{4}-\\d{2}-\\d{2}-(\\d+)_as\\d+\\.csv$"

enable_anomaly_pattern_2="true"
anomaly_pattern_2="^\\d{4}-\\d{2}-\\d{2}-(.*?)-ghana[_-][a-z0-9\\-]*_as\\d+\\.csv$"

enable_anomaly_pattern_3="true"
anomaly_pattern_3="^\\d{4}-\\d{2}-\\d{2}-(.*?)-ghana-geo\\.csv$"
