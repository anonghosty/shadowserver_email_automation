---
title: 08 Portable Analytics Dashboard
---

# Portable Analytics Dashboard

## Overview

The `portable_analytics_dashboard.py` script powers an interactive, professional-grade web dashboard for threat intelligence analysis based on Shadowserver data. It allows analysts, engineers, or decision-makers to visually explore threats by category, date, and organization.

Built with Dash and Plotly, the dashboard reads from structured CSV files—generated automatically via the
`generate_statistics_reported_from_shadowserver_unverified.py` script—and provides:

* A multi-org, multi-date visual summary of detected threats
* Trend analysis between days (positive/negative threat deltas)
* Clean, exportable tables and grouped bar charts per organization

This dashboard is fully portable and runs locally in a browser.

---

## Prerequisites

Before launching the dashboard, ensure the following steps are complete:

1. **Shadowserver Reports Generated**
   The script `generate_statistics_reported_from_shadowserver_unverified.py` **must be run for today’s date** (or the desired date range).

   This generates CSV files in the format:

   ```
   statistical_data/{org}/{org}_reported_shadowserverver_events_YYYY-MM-DD.csv
   ```

2. **Knowledgebase Validation**
   The knowledgebase used by the generator script **must be pre-populated** with relevant Shadowserver intelligence.

3. **Environment Variables Set**
   Ensure that your `.env` file exists in the root project folder.

   For guidance on configuring environment variables, refer to:
   [`04_environment-configuration.md`](04_environment-configuration.md)

4. **Environment Setup Completed**
   Make sure the environment is bootstrapped according to:
   [`03_installation-and-environment-bootstrapping.md`](03_installation-and-environment-bootstrapping.md)

---

## How to Use

### 1. Launch the Dashboard

From the terminal:

```bash
python portable_analytics_dashboard.py
```

It will start a local server accessible at:

```
http://localhost:8050/
```

### 2. Interact With the Dashboard

Once the dashboard loads in your browser:

* **Organization Selection**: Choose one or more organizations (auto-detected from the folder structure).
* **Date Range Selection**: Choose one or more dates (auto-populated from CSV filenames).
* **Category Filter**: Refine the view by specific threat categories (auto-detected from data).

### 3. Data Views

The dashboard dynamically updates two main views:

#### a. **Data Summary Table**

* Shows category-level counts per selected date.
* Computes change trends (increase/decrease) between dates.
* Supports search, sort, filter, and export to Excel.

#### b. **Analytics Overview Charts**

* Professional bar charts showing per-category threat distributions.
* Visual comparison across selected dates.
* Legend and tooltips for clarity.

---

## Benefits

* **Immediate Insight**: View threat distribution across multiple dimensions without parsing raw CSVs.
* **Multi-Org, Multi-Date Comparison**: Analyze patterns across time and organizations.
* **Export-Ready Data**: Tables can be exported for use in reports or external tools.
* **Clean UI**: Aesthetically styled for decision-makers, CSIRT members, and security analysts.
* **Portable and Isolated**: No internet or cloud required; runs locally from any system with Python.

---


