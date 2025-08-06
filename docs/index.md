---
title: 01 Home
layout: default
---

# Shadowserver Report Ingestion & Intelligence Toolkit

**Author:** [Ike Owuraku Amponsah](https://www.linkedin.com/in/iowuraku)  
**Contributors:** [KeCIRT](https://ke-cirt.go.ke/)  
**License:** [MIT (Modified – No Resale)](https://github.com/anonghosty/shadowserver_email_automation/blob/main/LICENSE)

---

## 📌 Overview

This project automates the ingestion, parsing, categorization, and reporting of threat intelligence feeds from [Shadowserver](https://www.shadowserver.org/). It is built for CSIRT teams and analysts looking to streamline Shadowserver report handling and transformation into actionable intelligence.

---
## Professional Contributors

This section acknowledges the institutional input and guidance received during the resolution and mitigation issues.

1. **National CIRT of Kenya**  
   ![National CSIRT of Kenya Logo](national_kenyan_csirt_logo_20250208.jpeg)  
   **Contribution:** Provided official communication (cirt@ke-cirt.go.ke), technical mitigation steps (0365 – Microsoft Graph, Google Workspace), and tutorial documentation (PDF format).
   **Update** On August 3rd, the KeCIRT team conducted a dedicated troubleshooting session to address persistent issues related to the graph option. After a comprehensive review and collaborative debugging, the underlying bugs were successfully identified and resolved. The graph functionality is now fully operational and performing as expected.

---
## 🚀 Key Features

- Email attachment ingestion (IMAP Authentication,Microsoft Graph Authentication, Google Workspace Oauth Authentication[Coming Soon])

![IMAP](imap.png)

- ZIP, RAR, and 7z archive extraction

![Archive Sort](sorted_sample.png)

- CSV parsing, validation, and enrichment (IP, ASN, WHOIS)

![Tracker](tracker_sample.png)
![Whois Sort](whois_sample.png)
  
- Country and service-based categorization

![Country Sort](country_sort_example.png)
![Service Sort](service_sample.png)

- 3 flavored variations for report generation daily - CSV {can be used in automation}, PDF {can be be used in official reporting}, HTML {has charts and search bars}

![html_report](new_report_html_sample.png)
![Severity Pie Chart](pie_chart_severity_display_sample.png)

- MongoDB-based enrichment and storage
![Knowledge](knowledge_sample.png)

- Metadata scraping using Selenium + Chrome
![metadata](metadata_sample.png)

- Portable Dashboard Showcasing Trends and Bar Charts For Organisation,Date and Category Comparisons

![Portable Dashbboard Trends and Configuration Flavors](portable_dashboard_visualisation.png)
![Analytics Overview](analytics_overview.png)

---




## 📬 Feedback & Contributions

If you're a CSIRT team or security analyst interested in collaborating or providing feedback, feel free to reach out via [LinkedIn](https://www.linkedin.com/in/iowuraku) or email me at (iassistuontoolkits@gmail.com).

