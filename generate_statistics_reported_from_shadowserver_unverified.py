import os
import csv
import gc
import sys
import time
import hashlib
import ipaddress
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient, UpdateOne
from tqdm import tqdm
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
)
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_JUSTIFY
from jinja2 import Template


load_dotenv(dotenv_path=".env", override=True)
today_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
ascii_banner_logo = r"""
_______ _     _ _______ ______   _____  _  _  _ _______ _______  ______ _    _ _______  ______       ______ _______  _____   _____   ______ _______                          
|______ |_____| |_____| |     \ |     | |  |  | |______ |______ |_____/  \  /  |______ |_____/      |_____/ |______ |_____] |     | |_____/    |                             
______| |     | |     | |_____/ |_____| |__|__| ______| |______ |    \_   \/   |______ |    \_      |    \_ |______ |       |_____| |    \_    |                             
                                                                                                                                                                             
 ______ _______ __   _ _______  ______ _______ _______ _____  _____  __   _      _______  _____   _____                                                                      
|  ____ |______ | \  | |______ |_____/ |_____|    |      |   |     | | \  |         |    |     | |     | |                                                                   
|_____| |______ |  \_| |______ |    \_ |     |    |    __|__ |_____| |  \_|         |    |_____| |_____| |_____ .      
"""

# Define ASCII art for "Shadowserver Statistics" (Small)
ascii_author_banner = r"""
______  __   __      _____ _     _ _______       _____  _  _  _ _     _  ______ _______ _     _ _     _      _______ _______  _____   _____  __   _ _______ _______ _     _  
|_____]   \_/          |   |____/  |______      |     | |  |  | |     | |_____/ |_____| |____/  |     |      |_____| |  |  | |_____] |     | | \  | |______ |_____| |_____|  
|_____]    |         __|__ |    \_ |______      |_____| |__|__| |_____| |    \_ |     | |    \_ |_____|      |     | |  |  | |       |_____| |  \_| ______| |     | |     | .                                                                                
"""

# Get today's date


# Print ASCII art
print("\033[1m" + ascii_banner_logo + "\033[0m")
print(ascii_author_banner)
print("IP Statistical Version  |   Today's Date:", today_date)


def spinning_wheel(seconds):
    chars = ['|', '/', '-', '\\']
    i = 0
    for _ in range(seconds * 10):
        sys.stdout.write('\r' + chars[i % 4])
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1
    sys.stdout.write('\r')  # Clear the line
    sys.stdout.flush()

# Change the argument to control how many seconds you want the animation to run
spinning_wheel(5)  # Will run for 5 seconds
print("Ready Processing")


# === Config ===
CSV_MAP_PATH = "shadowserver_analysis_system/detected_companies/constituent_map.csv"
OUTPUT_DIR = "statistical_data"
# Load lowercase .env keys into UPPERCASE Python variables
MONGO_HOST = os.getenv("mongo_host", "127.0.0.1")
MONGO_PORT = int(os.getenv("mongo_port", 27017))
MONGO_USERNAME = os.getenv("mongo_username")
MONGO_PASSWORD = os.getenv("mongo_password")
MONGO_AUTH_SOURCE = os.getenv("mongo_auth_source", "admin")

# Confirm loaded values
print("\n🔐 MongoDB Environment Configuration:")
print(f"  - MONGO_HOST        : {MONGO_HOST}")
print(f"  - MONGO_PORT        : {MONGO_PORT}")
print(f"  - MONGO_USERNAME    : {MONGO_USERNAME}")
print(f"  - MONGO_PASSWORD    : {'*' * len(MONGO_PASSWORD) if MONGO_PASSWORD else 'None'}")
print(f"  - MONGO_AUTH_SOURCE : {MONGO_AUTH_SOURCE}")

# === Date Range (Yesterday) ===
yesterday_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1)
yesterday_end = yesterday_start + timedelta(days=1)

# === MongoDB Client ===
client = MongoClient(
    MONGO_HOST,
    MONGO_PORT,
    username=MONGO_USERNAME,
    password=MONGO_PASSWORD,
    authSource=MONGO_AUTH_SOURCE
)

# === Load Organization → ASN Mapping ===
constituent_df = pd.read_csv(CSV_MAP_PATH)
org_asn_map = {
    row['org_name']: [asn.strip() for asn in str(row['asn']).split(',')]
    for _, row in constituent_df.iterrows()
}

# === Match Databases by _as{ASN} Suffix ===
all_dbs = client.list_database_names()
asn_db_map = {}
prefix_ip_counter = {}  # Keeps track of inferred prefixes and how many IPs fall under them



def infer_prefix(ip_str):
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        if isinstance(ip_obj, ipaddress.IPv4Address):
            # Infer /24 CIDR
            return f"{ip_obj.exploded.rsplit('.', 1)[0]}.0/24"
        elif isinstance(ip_obj, ipaddress.IPv6Address):
            return f"{ip_obj.exploded.split(':')[0]}::/64"
    except ValueError:
        return None

for org, asns in org_asn_map.items():
    for asn in asns:
        for db_name in all_dbs:
            if db_name.endswith(f"_as{asn}"):
                asn_db_map.setdefault((org, asn), []).append(db_name)

# === Extract Unique IPs and Save (One File per Org) ===
# === Extract Unique IPs and Save (One File per Org) ===
for org, asns in tqdm(org_asn_map.items(), desc="Processing Organizations"):
    org_ip_summary = {}
    prefix_ip_counter = {}  # Keeps track of inferred prefixes and how many IPs fall under them

    def infer_prefix(ip_str):
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            if isinstance(ip_obj, ipaddress.IPv4Address):
                return f"{ip_obj.exploded.rsplit('.', 1)[0]}.0/24"
            elif isinstance(ip_obj, ipaddress.IPv6Address):
                return f"{ip_obj.exploded.split(':')[0]}::/64"
        except ValueError:
            return None

    for asn in asns:
        for db_name in all_dbs:
            if not db_name.endswith(f"_as{asn}"):
                continue

            db = client[db_name]
            print(f"\n✅ [{org}] ASN {asn} → Database found: {db_name}")

            for coll_name in db.list_collection_names():
                if coll_name.startswith("files_") or coll_name.startswith("discovered_fields_"):
                    continue

                # Step 1: Only scan collections with extracted_date from yesterday
                extracted_date_query = {
                    "extracted_date": {
                        "$gte": yesterday_start,
                        "$lt": yesterday_end
                    }
                }

                if db[coll_name].count_documents(extracted_date_query) == 0:
                    continue

                # Step 2: Query documents for IPs
                query = {
                    "extracted_date": {
                        "$gte": yesterday_start,
                        "$lt": yesterday_end
                    },
                    "$or": [
                        {"ip": {"$exists": True}},
                        {"src_ip": {"$exists": True}},
                        {"http_referer_ip": {"$exists": True}}
                    ]
                }

                cursor = db[coll_name].find(query)

                for doc in cursor:
                    for ip_field in ["ip", "src_ip", "http_referer_ip"]:
                        ip = doc.get(ip_field)
                        if not ip:
                            continue

                        is_prefix = "/" in ip
                        if is_prefix:
                            ip_val = None
                            prefix_val = ip
                            entry_key = prefix_val
                        else:
                            ip_val = ip
                            prefix_val = infer_prefix(ip)
                            entry_key = ip_val
                            if prefix_val:
                                prefix_ip_counter.setdefault(prefix_val, set()).add(ip_val)

                        asn_val = doc.get("asn") or doc.get("src_asn") or doc.get("http_referer_asn")

                        if entry_key not in org_ip_summary:
                            org_ip_summary[entry_key] = {
                                "asn": set(),
                                "categories": {},
                                "timestamp": yesterday_start.strftime("%Y-%m-%d"),
                                "ip": ip_val,
                                "prefix": prefix_val
                            }

                        org_ip_summary[entry_key]["asn"].add(str(asn_val))
                        org_ip_summary[entry_key]["categories"].setdefault(coll_name, 0)
                        org_ip_summary[entry_key]["categories"][coll_name] += 1

                        asn_str = str(asn_val)
                        if "asn_category_map" not in org_ip_summary[entry_key]:
                            org_ip_summary[entry_key]["asn_category_map"] = {}
                        org_ip_summary[entry_key]["asn_category_map"].setdefault(asn_str, set())
                        org_ip_summary[entry_key]["asn_category_map"][asn_str].add(coll_name)

    # === Add IP count to prefix ===
    for entry in org_ip_summary.values():
        prefix = entry.get("prefix")
        if prefix and prefix in prefix_ip_counter:
            count = len(prefix_ip_counter[prefix])
            entry["prefix"] = f"{prefix} ({count})"

    # === Write merged results for this org ===
    try:
        if org_ip_summary:
            print(f"🧠 [{org}] Writing {len(org_ip_summary)} unique IPs to CSV...")
            save_path = os.path.join(OUTPUT_DIR, org)
            os.makedirs(save_path, exist_ok=True)
            filename_base = f"{org.lower().replace(' ', '_')}_reported_shadowserverver_events_{today_date}"
            csv_path = os.path.join(save_path, f"{filename_base}.csv")

            def clean_category_name(cat):
                # Remove trailing suffix like -318
                return cat.rsplit('-', 1)[0].strip() if '-' in cat else cat.strip()

            # Step 1: Write CSV
            with open(csv_path, mode='w', newline='') as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["timestamp", "org_name", "asn", "ip_address", "prefix", "category", "asn_category_map"]
                )
                writer.writeheader()

                for _, details in org_ip_summary.items():
                    # Clean and group categories
                    cleaned_categories = {}
                    for raw_cat, count in details["categories"].items():
                        clean_cat = clean_category_name(raw_cat)
                        cleaned_categories[clean_cat] = cleaned_categories.get(clean_cat, 0) + count

                    category_string = ", ".join([
                        f"{cat}[{count}]" for cat, count in sorted(cleaned_categories.items())
                    ])

                    # Clean asn_category_map
                    cleaned_asn_map = {}
                    for asn, cats in details.get("asn_category_map", {}).items():
                        cleaned_cats = {clean_category_name(c) for c in cats}
                        cleaned_asn_map[asn] = cleaned_cats

                    asn_map_string = ", ".join([
                        f"{asn}({', '.join(sorted(cats))})"
                        for asn, cats in sorted(cleaned_asn_map.items())
                    ])

                    writer.writerow({
                        "timestamp": details["timestamp"],
                        "org_name": org,
                        "asn": ", ".join(sorted(details["asn"])),
                        "ip_address": details.get("ip") or "",
                        "prefix": details.get("prefix") or "",
                        "category": category_string,
                        "asn_category_map": asn_map_string
                    })




            # Step 2: Generate Reference Number from CSV Hash and PDF
            with open(csv_path, "rb") as f:
                csv_hash = hashlib.sha256(f.read()).hexdigest()
            prefix = os.getenv("reference_nomenclature", "cert-stat-")  # Default in case not set
            reference_number = f"{prefix}{csv_hash[:10]}"
            reference_db = client["reference_system"]
            org_collection = reference_db[org.lower().replace(" ", "_")]
            org_collection.create_index("reference_number", unique=True)

            if not org_collection.find_one({"reference_number": reference_number}):
                org_collection.insert_one({
                    "org_name": org,
                    "filename": f"{filename_base}.csv",
                    "reference_number": reference_number,
                    "generated_on": today_date,
                    "report_category": "statistical_report",
                    "tlp_label": "AMBER"
                })
                print(f"🗃️ Reference logged for {org}")
            else:
                print(f"📌 Reference already exists for {org}, skipping insert.")

            # Step 3: Generate PDF
            pdf_path = os.path.join(save_path, f"{filename_base}.pdf")
            doc = SimpleDocTemplate(
                pdf_path,
                pagesize=landscape(A4),
                rightMargin=30,
                leftMargin=30,
                topMargin=30,
                bottomMargin=30
            )
            doc.title = f"{org}'s Reported Events from Shadowserver"
            cert_name = os.getenv("cert_name", "default-cert")
            doc.author = cert_name
            doc.subject = "Daily Reported Events from Shadowserver"
            styles = getSampleStyleSheet()
            story = []

            logo_path = "logo.png"
            if os.path.exists(logo_path):
                img = Image(logo_path, width=60, height=60)
                img.hAlign = "RIGHT"
                story.append(img)

            story.append(Paragraph("Reported Events from Shadowserver", styles["Title"]))
            story.append(Paragraph(f"Organization: <b>{org}</b>", styles["Heading2"]))
            story.append(Paragraph(f'<b><font color="orange">TLP:AMBER</font></b> – confidential between the stakeholder (organization) and the {cert_name}', styles["Normal"]))
            story.append(Paragraph(f"Reference Number: <b>{reference_number}</b>", styles["Normal"]))
            story.append(Paragraph(f"Associated CSV File: {os.path.basename(csv_path)}", styles["Normal"]))
            story.append(Paragraph(f"Report Category: <b>statistical_report</b>", styles["Normal"]))
            story.append(Paragraph(f"Generated on: {today_date}", styles["Normal"]))
            story.append(Spacer(1, 12))

 # Summary Analysis 
            total_ips = sum(1 for entry in org_ip_summary.values() if entry.get("ip"))
            total_prefixes = len(set(
                entry.get("prefix").split(" ")[0]
                for entry in org_ip_summary.values()
                if entry.get("prefix")
            ))
            styles["Normal"].alignment = TA_JUSTIFY
            summary_text = f'''
            As of {today_date}, Shadowserver reported a total of <b>{total_ips}</b> unique IP addresses with 
            <b>{total_prefixes}</b> prefixes observed in the datasets for {org}. These are identified as either malicious, misconfigured, or 
            indicative of information-based events. The table(s) below summarize the prefix ranges and the number of IPs observed under each range, 
            which require further investigation. Each IP entry also indicates how many categories it was reported in, aiding in the assessment of threat recurrence. 
            In the ASN→Category Map section, cases where multiple ASNs appear for a single IP across different categories are highlighted. This may suggest ASN 
            switching behavior or overlapping advertisements misconfigurations. Prefix calculations are general due to the volume 
            of IPs from all organizations during report generation. Further lookup is required for selected issues to be worked on as advisories to the concerned organizations.
            '''


            story.append(Paragraph("<b>Executive Summary</b>", styles["Heading2"]))
            story.append(Spacer(1, 6))
            story.append(Paragraph(summary_text, styles["Normal"]))  # Ensure TA_JUSTIFY is
            story.append(Spacer(1, 12))
            
            
            # Table Data
            story.append(Paragraph("<b>Reported as Malicious, Misconfigured or Information Based Events</b>", styles["Heading3"]))

            table_data = [["IP Address", "Prefix(es) [Lookup Required]", "ASN(s)", "Categories", "ASN→Category Map"]]

            data_rows = []
            for ip, details in sorted(org_ip_summary.items()):
                prefix = ", ".join(sorted(details.get("prefix", "").split(",")))

                # Clean categories
                cleaned_categories = {}
                for raw_cat, count in details["categories"].items():
                    clean_cat = clean_category_name(raw_cat)
                    cleaned_categories[clean_cat] = cleaned_categories.get(clean_cat, 0) + count
                cat_str = ", ".join([
                    f"{cat}[{count}]" for cat, count in sorted(cleaned_categories.items())
                ])

                asn_str = ", ".join(sorted(details["asn"]))

                # Clean ASN→Category Map
                cleaned_asn_map = {
                    asn: {clean_category_name(cat) for cat in cats}
                    for asn, cats in details.get("asn_category_map", {}).items()
                }
                asn_map_str = ", ".join([
                    f"{asn}({', '.join(sorted(cats))})"
                    for asn, cats in sorted(cleaned_asn_map.items())
                ])

                data_rows.append([
                    Paragraph(ip, styles["Normal"]),
                    Paragraph(prefix, styles["Normal"]),
                    Paragraph(asn_str, styles["Normal"]),
                    Paragraph(cat_str, styles["Normal"]),
                    Paragraph(asn_map_str, styles["Normal"]),
                ])

            data_rows.sort(key=lambda row: row[0].text)  

            table_data.extend(data_rows)

            table = Table(table_data, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2a2a2a")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ]))

            story.append(table)

            # === Add Prefix Summary Analysis on a new page ===
            story.append(PageBreak())  # Start a new page
            story.append(Paragraph("<b>Recorded Prefix(es) from Analysis</b>", styles["Heading3"]))
            # Prefix summary table
            prefix_summary_table = [["Prefix(es) [Lookup Required]", "IP Count(s)"]]
            prefix_counts = {}
            for entry in org_ip_summary.values():
                prefix = entry.get("prefix")
                if prefix and "(" in prefix:
                    prefix_label = prefix.split(" ")[0]
                    count = int(prefix.split("(")[-1].rstrip(")"))
                    prefix_counts[prefix_label] = count

            for prefix, count in sorted(prefix_counts.items(), key=lambda x: x[1], reverse=True):
                prefix_summary_table.append([prefix, str(count)])

            prefix_table = Table(prefix_summary_table, hAlign='LEFT')
            prefix_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2a2a2a")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ]))
            story.append(prefix_table)
            #Add Category Summary on new Page 
            
            # === Load Shadowserver report metadata ===
            report_metadata = {}
            metadata_dir = "shadowserver_url_descriptions"
            metadata_file = "shadowserver_report_types.csv"
            metadata_path = os.path.join(metadata_dir, metadata_file)

            if os.path.isdir(metadata_dir):
                print(f"✅ Folder found: {metadata_dir}")
            else:
                print(f"❌ Folder NOT found: {metadata_dir}")

            if os.path.isfile(metadata_path):
                print(f"✅ File found: {metadata_file}")
            else:
                print(f"❌ File NOT found: {metadata_file}")

            with open(metadata_path, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    filename_field = (row.get("Filename") or "").strip().lower()
                    if filename_field:
                        for fn in filename_field.split(","):
                            report_metadata[fn.strip()] = {
                                "Severity": row.get("Severity", "").strip(),
                                "Title": row.get("Title", "").strip(),
                                "Description": row.get("Description", "").strip(),
                                "URL": row.get("URL", "").strip()
                            }

            story.append(PageBreak())  # Start a new page
            story.append(Paragraph("<b>Recorded Category Summary</b>", styles["Heading3"]))

            def clean_category_name(cat):
                if '-' in cat:
                    return cat.rsplit('-', 1)[0].strip()
                return cat.strip()

            # Build cleaned category counts from org_ip_summary
            category_counts = {}
            for entry in org_ip_summary.values():
                for category, count in entry.get("categories", {}).items():
                    clean_cat = clean_category_name(category)
                    category_counts[clean_cat] = category_counts.get(clean_cat, 0) + count


            # === Define severity sort order and color map ===
            severity_priority = {
                "CRITICAL": 0,
                "HIGH": 1,
                "MEDIUM": 2,
                "LOW": 3,
                "INFO": 4,
                "LOOKUP": 5
            }

            severity_colors = {
                "CRITICAL": "#ff4c4c",   # red
                "HIGH": "#ff9900",       # orange
                "MEDIUM": "#ffc107",     # amber
                "LOW": "#17a2b8",        # cyan
                "INFO": "#6c757d",       # gray
                "LOOKUP": "#cccccc"    # light gray
            }

            # Prepare table rows with metadata
            category_rows = []
            for category, count in category_counts.items():
                meta = report_metadata.get(category.lower(), {})
                severity = meta.get("Severity", "LOOKUP")
                severity_color = severity_colors.get(severity, "#cccccc")

                severity_cell = Paragraph(f'<font color="{severity_color}"><b>{severity}</b></font>', styles["Normal"])
                title_cell = Paragraph(meta.get("Title", ""), styles["Normal"])
                description_cell = Paragraph(meta.get("Description", ""), styles["Normal"])
                category_cell = Paragraph(category, styles["Normal"])
                count_cell = str(count)
                url = meta.get("URL", "").strip()
                url_cell = Paragraph(f'<link href="{url}">{url}</link>', styles["Normal"]) if url else Paragraph("-", styles["Normal"])

                category_rows.append((
                    severity_priority.get(severity, 99),  # sort key
                    severity_cell,
                    title_cell,
                    description_cell,
                    category_cell,
                    count_cell,
                    url_cell
                ))

            # Sort rows by severity
            category_rows.sort(key=lambda x: x[0])

            # Final table data
            category_summary_table = [[
                "Severity", 
                "Title", 
                "Description",
                "Category", 
                "IP Count(s)", 
                "Reference URL"
            ]]
            for row in category_rows:
                category_summary_table.append(list(row[1:]))

            category_table = Table(category_summary_table, hAlign='LEFT', colWidths=[60, 120, 200, 100, 60, 180])
            category_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2a2a2a")),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
                ('WORDWRAP', (0, 0), (-1, -1), 'CJK'),  # ✅ Enable word wrap for all cells
            ]))
            story.append(category_table)



            def add_page_number(canvas, doc):
                canvas.saveState()
                canvas.setFont("Helvetica", 8)

                x_left = 0.7 * inch
                y_footer = 0.2 * inch

                # Draw "TLP:"
                canvas.setFillColor(colors.black)
                canvas.drawString(x_left, y_footer, "TLP:")
                x_left += canvas.stringWidth("TLP:", "Helvetica", 8) + 2

                # Draw "AMBER" in bold amber
                canvas.setFont("Helvetica-Bold", 8)
                canvas.setFillColor(HexColor("#FFBF00"))  # Amber color
                canvas.drawString(x_left, y_footer, "AMBER")
                x_left += canvas.stringWidth("AMBER", "Helvetica-Bold", 8) + 2

                # Draw "– Confidential" in bold black
                canvas.setFont("Helvetica-Bold", 8)
                canvas.setFillColor(colors.black)
                confidential_text = "– Confidential"
                canvas.drawString(x_left, y_footer, confidential_text)
                x_left += canvas.stringWidth(confidential_text, "Helvetica-Bold", 8) + 2

                # Draw " | Reference: " in normal
                canvas.setFont("Helvetica", 8)
                reference_prefix = "| Reference: "
                canvas.drawString(x_left, y_footer, reference_prefix)
                x_left += canvas.stringWidth(reference_prefix, "Helvetica", 8)

                # Draw reference number in bold
                canvas.setFont("Helvetica-Bold", 8)
                canvas.drawString(x_left, y_footer, reference_number)

                # Right side page number
                canvas.setFont("Helvetica", 8)
                canvas.drawRightString(11 * inch, y_footer, f"Page {doc.page}")

                canvas.restoreState()




            doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
            print(f"📄 PDF report saved to {pdf_path} with reference {reference_number}")

            # === Step 4: Generate Offline HTML Report ===
            html_path = os.path.join(save_path, f"{filename_base}.html")
            from jinja2 import Template

            # Load basic HTML template (you should create 'report_template.html')
            with open("report_template.html", encoding="utf-8") as f:
                template = Template(f.read())

            html_content = template.render(
                org_name=org,
                reference_number=reference_number,
                generated_on=today_date,
                summary_text=summary_text,
                ip_table_rows=[
                    {
                        "ip": ip,
                        "prefix": ", ".join(sorted(details.get("prefix", "").split(","))),
                        "asn": ", ".join(sorted(details.get("asn", []))),
                        "categories": ", ".join([
                            f"{clean_category_name(k)}[{v}]"
                            for k, v in sorted(details.get("categories", {}).items())
                        ]),
                        "asn_map": ", ".join([
                            f"{asn}({', '.join(sorted({clean_category_name(c) for c in cats}))})"
                            for asn, cats in sorted(details.get("asn_category_map", {}).items())
                        ])
                    } for ip, details in org_ip_summary.items()
                ],
                prefix_counts=list(prefix_counts.items()),
                category_rows=[
                    {
                        "severity": report_metadata.get(cat.lower(), {}).get("Severity", "LOOKUP"),
                        "title": report_metadata.get(cat.lower(), {}).get("Title", ""),
                        "description": report_metadata.get(cat.lower(), {}).get("Description", ""),
                        "category": cat,
                        "count": count,
                        "url": report_metadata.get(cat.lower(), {}).get("URL", "")
                    } for cat, count in category_counts.items()
                ]
            )

            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            print(f"🌐 HTML report saved to {html_path} with reference {reference_number}")

        else:
            print(f"⚠️ No extracted_date matches for {org}.")

    finally:
        del org_ip_summary
        del prefix_ip_counter
        gc.collect()
        print(f"🧹 Memory cleaned up for {org}")

