import os
import re
import csv
import datetime
import geopandas as gpd
import pycountry
import matplotlib.pyplot as plt
import pandas as pd
import gc
import os
import requests
import zipfile
from pymongo import MongoClient
from dotenv import load_dotenv
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib import colors
from collections import defaultdict
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm



yesterday = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)).strftime('%Y-%m-%d')


def get_shapefile_path(shapefile_type="admin_0_countries"):
    """
    Ensure Natural Earth shapefile exists locally. If not, download and extract it.
    
    shapefile_type options:
        - "admin_0_countries" (Country boundaries)
        - "admin_1_states_provinces" (Regional boundaries)
    
    Returns:
        Path to the .shp file.
    """
    
    # Map shapefile type to URL and folder name
    natural_earth_urls = {
        "admin_0_countries": {
            "url": "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip",
            "folder": "data/ne_110m_admin_0_countries"
        }
    }
    
    if shapefile_type not in natural_earth_urls:
        raise ValueError("Invalid shapefile_type. Choose 'admin_0_countries'")
    
    url = natural_earth_urls[shapefile_type]["url"]
    folder = natural_earth_urls[shapefile_type]["folder"]
    
    # Create data directory if it doesn't exist
    os.makedirs("data", exist_ok=True)
    
    # Check if already exists
    shp_file = None
    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.endswith(".shp"):
                shp_file = os.path.join(folder, f)
                break
        if shp_file:
            return shp_file  # Already downloaded
    
    # If not found, download
    print(f"Downloading {shapefile_type} shapefile...")
    zip_path = f"{folder}.zip"
    response = requests.get(url)
    with open(zip_path, "wb") as f:
        f.write(response.content)
    
    # Extract
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(folder)
    
    os.remove(zip_path)  # Clean up
    
    # Return .shp path
    for f in os.listdir(folder):
        if f.endswith(".shp"):
            shp_file = os.path.join(folder, f)
            break
    
    return shp_file
shapefile_path = get_shapefile_path("admin_0_countries")
print(f"Shapefile path: {shapefile_path}")



def get_country_name(iso_code):
    try:
        return pycountry.countries.get(alpha_2=iso_code).name
    except:
        return iso_code

def safe_filename(name):
    return re.sub(r'\W+', '_', name.lower()).strip('_')

def load_asn_mapping(csv_path):
    asn_to_org = {}
    with open(csv_path, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            org = row["org_name"].strip()
            asns = row["asn"].split(",")
            for asn in asns:
                clean_asn = asn.strip()
                if clean_asn:
                    asn_to_org[clean_asn] = org
    return asn_to_org

def create_attack_map(attack_data, output_path):
    world = gpd.read_file("data/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp")
    fig, ax = plt.subplots(figsize=(14, 8))
    world.plot(ax=ax, color='lightgrey', edgecolor='white')
    world_proj = world.to_crs(epsg=3857)
    centroids_proj = world_proj.set_index('ISO_A2').centroid
    country_centroids = centroids_proj.to_crs(world.crs).to_dict()

    src_countries = set()
    dst_countries = set()

    for src_country, dst_country, count in attack_data:
        if src_country not in country_centroids or dst_country not in country_centroids:
            continue
        src_point = country_centroids[src_country]
        dst_point = country_centroids[dst_country]
        ax.plot([src_point.x, dst_point.x], [src_point.y, dst_point.y],
                color='red', linewidth=0.5 + min(count / 10, 3), alpha=0.6)
        src_countries.add(src_country)
        dst_countries.add(dst_country)

    ax.set_title(f"Visualisation of Reported Malicious Communication ({yesterday})", fontsize=16)
    ax.axis('off')

    # Prepare text
    src_list = ", ".join(sorted(src_countries))
    dst_list = ", ".join(sorted(dst_countries))
    label_text = f"Location: {src_list}   |   Malicious Communication: {dst_list}"

    # Position text just below the plot area
    fig.subplots_adjust(bottom=0.15)  # leave extra space at bottom
    fig.text(0.5, 0.08, label_text, ha="center", fontsize=10, wrap=True)

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close(fig)
    del fig, ax


def get_severity_color(severity):
    sev = severity.lower()
    if sev in ['high', 'critical']:
        return colors.red
    elif sev in ['medium']:
        return colors.orange
    elif sev in ['low']:
        return colors.green
    else:
        return colors.black




def generate_pdf_report(org_name, db_name, collection_attacks, pdf_path, cert_name):
    today_date = datetime.datetime.now().strftime("%Y-%m-%d")
    reference_number = f"{org_name[:3].upper()}-{today_date.replace('-', '')}"

    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    doc.title = f"{org_name}'s Destination Based Events Reported by Shadowserver"
    doc.author = cert_name
    doc.subject = "Destination Based Events Reported by Shadowserver"

    styles = getSampleStyleSheet()
    story = []

    # Logo (top-right)
    logo_path = "logo.png"
    if os.path.exists(logo_path):
        img = Image(logo_path, width=60, height=60)
        img.hAlign = "RIGHT"
        story.append(img)

    # Header content
    story.append(Paragraph("Destination Based Events Reported by Shadowserver", styles["Title"]))
    story.append(Paragraph(f"Organization: <b>{org_name}</b>", styles["Heading2"]))
    story.append(Paragraph(
        f'<b><font color="orange">TLP:AMBER</font></b> – confidential between the stakeholder (organization) and the {cert_name}',
        styles["Normal"]
    ))
    story.append(Paragraph(f"<b>Report Category:</b> statistical_report", styles["Normal"]))
    story.append(Paragraph(f"<b>Generated on:</b> {today_date}", styles["Normal"]))

    story.append(Spacer(1, 12))

    # Report content
    for col, data in collection_attacks.items():
        title_text = f"<b>{data.get('title', 'Untitled Report')} ({col})</b>"
        story.append(Paragraph(title_text, styles['Heading2']))
        story.append(Spacer(1, 6))

        severity_color = get_severity_color(data.get("severity", "Unknown"))
        custom_style = ParagraphStyle('SeverityStyle', parent=styles['Normal'], textColor=severity_color)

        story.append(Paragraph(f"<b>Severity:</b> {data.get('severity', 'Unknown')}", custom_style))
        story.append(Paragraph(f"<b>Description:</b> {data.get('description', 'No description available.')}", styles['Normal']))
        story.append(Paragraph(f"<b>Reference:</b> <a href='{data.get('reference', '')}'>{data.get('reference', '')}</a>", styles['Normal']))
        story.append(Spacer(1, 8))
        
        # Attack Summary
        story.append(Paragraph("<b> Reported Malicious Communication Summary:</b>", styles['Normal']))
        story.append(Paragraph("<b><i>Note:</i></b> <i>'ZZ' indicates that the destination country is unknown.</i>", styles['Normal']))
        attacks_list = sorted(data['attacks'], key=lambda x: x[2], reverse=True)
        for idx, (src, dst, count) in enumerate(attacks_list, start=1):
            src_name = get_country_name(src)
            dst_name = get_country_name(dst)
            story.append(Paragraph(f"{idx}. Malicious communication reported between {src_name} and {dst_name}: {count} events", styles['Normal']))
        story.append(Spacer(1, 12))



        # Attack Map
        story.append(Image(data['map'], width=500, height=280))
        story.append(PageBreak())

    # Footer function with TLP and page number
    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)

        x_left = 0.7 * inch
        y_footer = 0.2 * inch

        # Draw "TLP:"
        canvas.setFillColor(colors.black)
        canvas.drawString(x_left, y_footer, "TLP:")
        x_left += canvas.stringWidth("TLP:", "Helvetica", 8) + 2

        # Draw "AMBER"
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(HexColor("#FFBF00"))
        canvas.drawString(x_left, y_footer, "AMBER")
        x_left += canvas.stringWidth("AMBER", "Helvetica-Bold", 8) + 2

        # Draw "– Confidential"
        canvas.setFont("Helvetica-Bold", 8)
        canvas.setFillColor(colors.black)
        confidential_text = f"– Confidential between the stakeholder (organization) and the {cert_name}"
        canvas.drawString(x_left, y_footer, confidential_text)
        x_left += canvas.stringWidth(confidential_text, "Helvetica-Bold", 8) + 2

        # Draw reference number
        canvas.setFont("Helvetica", 8)
        canvas.drawString(x_left, y_footer, "| Reference: ")
        x_left += canvas.stringWidth("| Reference: ", "Helvetica", 8)

        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(x_left, y_footer, reference_number)

        # Page number (bottom-right)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(11 * inch, y_footer, f"Page {doc.page}")
        canvas.restoreState()

    # Build the document with custom footer
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)



def main():
    load_dotenv()
    cert_name = os.getenv("cert_name", "CERT Intelligence Team")

    mongo_uri = (
        f"mongodb://{os.getenv('mongo_username')}:{os.getenv('mongo_password')}@"
        f"{os.getenv('mongo_host', '127.0.0.1')}:{int(os.getenv('mongo_port', 27017))}/"
        f"?authSource={os.getenv('mongo_auth_source', 'admin')}"
    )

    csv_path = os.path.join("shadowserver_analysis_system", "detected_companies", "constituent_map.csv")
    asn_to_org = load_asn_mapping(csv_path)

    desc_path = os.path.join("shadowserver_url_descriptions", "shadowserver_report_types.csv")
    desc_df = pd.read_csv(desc_path)
    desc_lookup = {
        row["Filename"]: {
            "title": row.get("Title", "Untitled Report"),
            "severity": row.get("Severity", "Unknown"),
            "description": row.get("Description", "No description available."),
            "reference": row.get("URL", "N/A")
        }
        for _, row in desc_df.iterrows()
    }


    client = MongoClient(mongo_uri)
    db_names = client.list_database_names()

    yesterday = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)).date()
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")

    for db_name in db_names:
        match = re.search(r"_as(\d+)", db_name)
        if not match:
            continue
        asn = match.group(1)
        org = asn_to_org.get(asn)
        if not org:
            continue

        db = client[db_name]
        collections = [c for c in db.list_collection_names() if not c.startswith("files_")]
        yday_collections = []
        collection_attacks = {}

        org_dir = os.path.join("statistical_data", org)
        os.makedirs(org_dir, exist_ok=True)

        for col_name in collections:
            collection = db[col_name]
            yday_query = {
                "extracted_date": {
                    "$gte": datetime.datetime.combine(yesterday, datetime.time.min, tzinfo=datetime.timezone.utc),
                    "$lt": datetime.datetime.combine(yesterday + datetime.timedelta(days=1), datetime.time.min, tzinfo=datetime.timezone.utc)
                }
            }

            if collection.count_documents(yday_query, limit=1):
                yday_collections.append(col_name)
                attack_counter = defaultdict(lambda: defaultdict(int))
                raw_count = collection.count_documents(yday_query)
                valid_attack_count = 0

                for doc in collection.find(yday_query, {"src_geo": 1, "dst_geo": 1, "src_ip": 1, "http_referer_ip": 1, "http_referer_geo": 1}):
                    if doc.get("src_geo"):
                        src_geo = doc["src_geo"].upper()
                    elif doc.get("http_referer_geo"):
                        src_geo = doc["http_referer_geo"].upper()
                    else:
                        src_geo = "ZZ"

                    dst_geo = (doc.get("dst_geo") or "ZZ").upper()

                    if src_geo != "ZZ" and dst_geo != "ZZ" and src_geo != dst_geo:
                        attack_counter[src_geo][dst_geo] += 1

                #print(f"→ Raw DB Count: {raw_count}")
                #print(f"→ Valid (Filtered) Attack Entries: {valid_attack_count}")

                attacks = [(src, dst, count) for src, dsts in attack_counter.items() for dst, count in dsts.items()]
                if not attacks:
                    continue

                maps_dir = os.path.join(org_dir, "generated_threatmaps")
                os.makedirs(maps_dir, exist_ok=True)
                map_path = os.path.join(
                    maps_dir,
                    f"{safe_filename(org)}_{today_str}_{safe_filename(col_name)}_map.png"
                )
                create_attack_map(attacks, map_path)

                meta = desc_lookup.get(col_name, {})
                collection_attacks[col_name] = {
                    "attacks": attacks,
                    "map": map_path,
                    "title": meta.get("title", "Untitled Report"),
                    "severity": meta.get("severity", "Unknown"),
                    "description": meta.get("description", "No description available."),
                    "reference": meta.get("reference", "N/A")
                }


        if collection_attacks:
            print(f"\n🔷 Organisation: {org}")
            print(f"   ➤ Database: {db_name}")
            print(f"   ➤ Collections with valid attack data: {list(collection_attacks.keys())}")

            pdf_path = os.path.join(org_dir, f"{safe_filename(org)}_{today_str}_attack_report.pdf")
            generate_pdf_report(org, db_name, collection_attacks, pdf_path, cert_name)
            print(f"   ➤ PDF Report: {pdf_path}")

        gc.collect()

if __name__ == "__main__":
    main()
