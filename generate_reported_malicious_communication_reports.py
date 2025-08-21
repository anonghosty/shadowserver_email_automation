import os
import re
import csv
import datetime
import geopandas as gpd
import pycountry
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import pandas as pd
import gc
import requests
import zipfile
from collections import defaultdict
from pymongo import MongoClient
from dotenv import load_dotenv
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

author = "Ike Owuraku Amponsah"
linkedin_url = "https://www.linkedin.com/in/iowuraku"
docs_url = "https://anonghosty.github.io/shadowserver_email_automation/"
license_url = "https://raw.githubusercontent.com/anonghosty/shadowserver_email_automation/refs/heads/main/LICENSE"

def clickable(text, url):
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"

print("Author:", author)
print("LinkedIn:", clickable(linkedin_url, linkedin_url))
print("Documentation:", clickable(docs_url, docs_url))
print("License:", clickable(license_url, license_url))

yesterday = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)).strftime('%Y-%m-%d')

def get_shapefile_path(shapefile_type="admin_0_countries_110m"):
    natural_earth_urls = {
        "admin_0_countries_110m": {
            "url": "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip",
            "folder": "data/ne_110m_admin_0_countries"
        },
        "admin_0_countries_50m": {
            "url": "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip",
            "folder": "data/ne_50m_admin_0_countries"
        },
        "admin_0_countries_10m": {
            "url": "https://naciscdn.org/naturalearth/10m/cultural/ne_10m_admin_0_countries.zip",
            "folder": "data/ne_10m_admin_0_countries"
        }
    }

    if shapefile_type not in natural_earth_urls:
        raise ValueError("Invalid shapefile_type. Choose from: 'admin_0_countries_110m', 'admin_0_countries_50m', 'admin_0_countries_10m'.")

    url = natural_earth_urls[shapefile_type]["url"]
    folder = natural_earth_urls[shapefile_type]["folder"]
    os.makedirs("data", exist_ok=True)

    # Check if folder and .shp file already exist
    if os.path.exists(folder):
        shp_files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".shp")]
        if shp_files:
            return shp_files[0]

    # If not found, download zip
    print(f"Downloading {shapefile_type} shapefile...")
    zip_path = f"{folder}.zip"
    response = requests.get(url)
    response.raise_for_status()  # raise if bad response
    with open(zip_path, "wb") as f:
        f.write(response.content)

    # Extract zip
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(folder)
    os.remove(zip_path)

    # Verify extraction succeeded by locating .shp
    shp_files = [os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".shp")]
    if shp_files:
        print(f"Extracted shapefile(s) for {shapefile_type}:")
        for shp in shp_files:
            print(f" - {shp}")
   

    if shp_files:
        print(f"Extracted shapefile(s) for {shapefile_type}:")
        for shp in shp_files:
            print(f" - {shp}")
        return shp_files[0]  # <-- This was missing!

    raise FileNotFoundError(f"No .shp file found in {folder} after extraction.")


shapefile_cache = {}
gdf_cache = {}

def select_best_shapefile(required_codes, verbose=True):
    ignored_codes = {"ZZ"}  # codes to ignore
    filtered_codes = {code for code in required_codes if code not in ignored_codes}

    shapefile_order = ["admin_0_countries_10m", "admin_0_countries_50m", "admin_0_countries_110m"]

    for shapefile_type in shapefile_order:
        # Load shapefile path with cache
        if shapefile_type not in shapefile_cache:
            path = get_shapefile_path(shapefile_type)
            shapefile_cache[shapefile_type] = path
        else:
            path = shapefile_cache[shapefile_type]

        # Load GeoDataFrame with cache
        if shapefile_type not in gdf_cache:
            gdf_cache[shapefile_type] = gpd.read_file(path)

        gdf = gdf_cache[shapefile_type]
        available = set(gdf["ISO_A2"].dropna().str.upper())

        if filtered_codes.issubset(available):
            if verbose:
                print(f"\nGenerating Next Map(s) and Report")
            return path, shapefile_type

    # Fallback to the lowest resolution if none matched fully
    fallback_type = "admin_0_countries_110m"
    if fallback_type not in shapefile_cache:
        shapefile_cache[fallback_type] = get_shapefile_path(fallback_type)

    if verbose:
        print(f"INFO: Incase of Fallbacks: {shapefile_type} {fallback_type}")
    return shapefile_cache[fallback_type], fallback_type




def get_country_name(iso_code):
    try:
        return pycountry.countries.get(alpha_2=iso_code).name
    except:
        return iso_code

def safe_filename(name):
    return re.sub(r'\W+', '_', name.lower()).strip('_')

def load_asn_mapping(csv_path):
    mapping = {}
    with open(csv_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            org = row["org_name"].strip()
            for asn in row["asn"].split(","):
                if asn.strip():
                    mapping[asn.strip()] = org
    return mapping

def create_attack_map(attack_data, output_path, shapefile_path):
    world = gpd.read_file(shapefile_path)
    fig, ax = plt.subplots(figsize=(14, 8))
    world.plot(ax=ax, color='lightgrey', edgecolor='white')

    # Project world to metric CRS for accurate centroid calculation
    world_proj = world.to_crs(epsg=3857)
    centroids_proj = world_proj.set_index('ISO_A2').centroid

    # Convert centroids back to original geographic CRS (e.g., EPSG:4326)
    centroids = centroids_proj.to_crs(world.crs)

    # Convert to dictionary: {country_code: Point}
    centroid_dict = centroids.to_dict()

    src_set, dst_set = set(), set()
    for src, dst, count in attack_data:
        if src not in centroid_dict or dst not in centroid_dict:
            continue
        sp, dp = centroid_dict[src], centroid_dict[dst]
        ax.plot([sp.x, dp.x], [sp.y, dp.y],
                color='red', linewidth=0.5 + min(count / 10, 3), alpha=0.6)
        src_set.add(src)
        dst_set.add(dst)

    ax.set_title(f"Reported Malicious Communication ({yesterday})", fontsize=16)
    ax.axis('off')

    fig.subplots_adjust(bottom=0.15)
    label = f"From: {', '.join(sorted(src_set))} | To: {', '.join(sorted(dst_set))}"
    fig.text(0.5, 0.08, label, ha="center", fontsize=10, wrap=True)

    plt.tight_layout()
    plt.savefig(output_path)
    plt.close(fig)
    del fig, ax

    return src_set, dst_set



def get_severity_color(sev):
    s = sev.lower()
    return (
        colors.red if s in ['high', 'critical']
        else colors.orange if s == 'medium'
        else colors.green if s == 'low'
        else colors.black
    )

def generate_pdf_report(org, db, coll_atks, pdf_path, cert_name):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    ref_num = f"{org[:3].upper()}-{today.replace('-', '')}"

    doc = SimpleDocTemplate(pdf_path, pagesize=A4)
    doc.title = f"{org} Shadowserver Report"
    doc.author = cert_name

    story = []
    styles = getSampleStyleSheet()

    # Report header content
    story.append(Paragraph("Destination Based Events Reported by Shadowserver", styles["Title"]))
    story.append(Paragraph(f"Organization: <b>{org}</b>", styles["Heading2"]))
    story.append(Paragraph(
        f'<b><font color="orange">TLP:AMBER</font></b> – confidential between the stakeholder (organization) and the {cert_name}',
        styles["Normal"]))
    story.append(Spacer(1, 12))

    for col, data in coll_atks.items():
        story.append(Paragraph(f"<b>{data['title']} ({col})</b>", styles["Heading2"]))

        sev_color = get_severity_color(data.get("severity", "Unknown"))
        story.append(Paragraph(
            f"<b>Severity:</b> {data.get('severity', 'Unknown')}",
            ParagraphStyle('sev', parent=styles["Normal"], textColor=sev_color)
        ))

        story.append(Paragraph(f"<b>Description:</b> {data.get('description', '')}", styles["Normal"]))
        story.append(Spacer(1, 8))

        for idx, (src, dst, count) in enumerate(sorted(data['attacks'], key=lambda x: x[2], reverse=True), 1):
            story.append(Paragraph(
                f"{idx}. Malicious communication reported between "
                f"{get_country_name(src)} and {get_country_name(dst)}: "
                f"{count} event(s)", styles["Normal"]
            ))

        story.append(Spacer(1, 12))
        story.append(Image(data['map'], width=500, height=280))
        story.append(PageBreak())

    def header_footer(canvas_obj, doc_obj):
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 8)

        x_left = 0.7 * inch
        y_footer = 0.2 * inch

        # Draw "TLP:"
        canvas_obj.setFillColor(colors.black)
        canvas_obj.drawString(x_left, y_footer, "TLP:")
        x_left += canvas_obj.stringWidth("TLP:", "Helvetica", 8) + 2

        # Draw "AMBER"
        canvas_obj.setFont("Helvetica-Bold", 8)
        canvas_obj.setFillColor(HexColor("#FFBF00"))
        canvas_obj.drawString(x_left, y_footer, "AMBER")
        x_left += canvas_obj.stringWidth("AMBER", "Helvetica-Bold", 8) + 2

        # Draw "– Confidential"
        canvas_obj.setFont("Helvetica-Bold", 8)
        canvas_obj.setFillColor(colors.black)
        confidential_text = f"– Confidential between the stakeholder (organization) and the {cert_name}"
        canvas_obj.drawString(x_left, y_footer, confidential_text)
        x_left += canvas_obj.stringWidth(confidential_text, "Helvetica-Bold", 8) + 2

        # Draw reference number
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.drawString(x_left, y_footer, "| Reference: ")
        x_left += canvas_obj.stringWidth("| Reference: ", "Helvetica", 8)

        canvas_obj.setFont("Helvetica-Bold", 8)
        canvas_obj.drawString(x_left, y_footer, ref_num)

        # Page number (bottom-right)
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.drawRightString(11 * inch, y_footer, f"Page {doc_obj.page}")

        # Top-right logo
        logo_path = "logo.png"
        if os.path.exists(logo_path):
            logo = ImageReader(logo_path)
            page_width, page_height = A4
            canvas_obj.drawImage(
                logo,
                x=page_width - 1.5 * inch,
                y=page_height - 1.2 * inch,
                width=60,
                height=60,
                preserveAspectRatio=True,
                mask='auto'
            )

        canvas_obj.restoreState()

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)


def main():
    load_dotenv()
    cert_name = os.getenv("cert_name", "CERT Intelligence Team")
    client = MongoClient(
        f"mongodb://{os.getenv('mongo_username')}:{os.getenv('mongo_password')}@"
        f"{os.getenv('mongo_host', '127.0.0.1')}:{os.getenv('mongo_port', 27017)}/"
        f"?authSource={os.getenv('mongo_auth_source', 'admin')}"
    )

    asn_map = load_asn_mapping(os.path.join("shadowserver_analysis_system", "detected_companies", "constituent_map.csv"))
    desc_df = pd.read_csv(os.path.join("shadowserver_url_descriptions", "shadowserver_report_types.csv"))
    desc_lookup = {
        row["Filename"]: {
            "title": row.get("Title", "Untitled"),
            "severity": row.get("Severity", "Unknown"),
            "description": row.get("Description", ""),
        }
        for _, row in desc_df.iterrows()
    }

    yesterday_date = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)).date()
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")

    all_codes = set()
    dbs = client.list_database_names()
    for db_name in dbs:
        match = re.search(r"_as(\d+)", db_name)
        if not match:
            continue

        colls = client[db_name].list_collection_names()
        for col in colls:
            if col.startswith("files_"):
                continue
            query = {"extracted_date": {"$gte": datetime.datetime.combine(yesterday_date, datetime.time.min, tzinfo=datetime.timezone.utc),
                                        "$lt": datetime.datetime.combine(yesterday_date + datetime.timedelta(days=1), datetime.time.min, tzinfo=datetime.timezone.utc)}}
            for doc in client[db_name][col].find(query, {"src_geo": 1, "dst_geo": 1, "http_referer_geo": 1}):
                src = doc.get("src_geo") or doc.get("http_referer_geo")
                dst = doc.get("dst_geo")
                if src: all_codes.add(src.upper())
                if dst: all_codes.add(dst.upper())

    def clean_codes(codes):
        valid_codes = set()
        for c in codes:
            c = c.upper()
            if c == "UK":
                c = "GB"  # correct ISO code
            if len(c) == 2 and c.isalpha():
                valid_codes.add(c)
        return valid_codes


    
    all_codes = clean_codes(all_codes)
    print("Cleaned all country codes:", sorted(all_codes))					
					
    shapefile_path = select_best_shapefile(all_codes)

    dbs = client.list_database_names()

    for db_name in dbs:
        match = re.search(r"_as(\d+)", db_name)
        if not match:
            continue
        asn = match.group(1)
        org = asn_map.get(asn)
        if not org:
            continue

        # Collect country codes for this org's db
        # Collect country codes for this org's db
        required_codes = set()
        db = client[db_name]
        colls = db.list_collection_names()

        for col in colls:
            if col.startswith("files_"):
                continue

            query = {
                "extracted_date": {
                    "$gte": datetime.datetime.combine(
                        yesterday_date,
                        datetime.time.min,
                        tzinfo=datetime.timezone.utc
                    ),
                    "$lt": datetime.datetime.combine(
                        yesterday_date + datetime.timedelta(days=1),
                        datetime.time.min,
                        tzinfo=datetime.timezone.utc
                    )
                }
            }

            for doc in db[col].find(
                query,
                {"src_geo": 1, "dst_geo": 1, "http_referer_geo": 1}
            ):
                src = doc.get("src_geo") or doc.get("http_referer_geo")
                dst = doc.get("dst_geo")
                if src:
                    required_codes.add(src.upper())
                if dst:
                    required_codes.add(dst.upper())

        # Skip organisation if no country codes found (means no data)
        if not required_codes:
            continue

        # Select best shapefile for this org's country codes
        shapefile_path, shapefile_type = select_best_shapefile(required_codes)
        print(f"\nOrganisation: {org}, Database: {db_name}, selected shapefile: {shapefile_type}")

        collection_attacks = {}
        # Continue processing attacks and building reports/maps with shapefile_path...
        for col in colls:
            if col.startswith("files_"):
                continue
            query = {
                "extracted_date": {
                    "$gte": datetime.datetime.combine(yesterday_date, datetime.time.min, tzinfo=datetime.timezone.utc),
                    "$lt": datetime.datetime.combine(yesterday_date + datetime.timedelta(days=1), datetime.time.min, tzinfo=datetime.timezone.utc)
                }
            }
            if not db[col].count_documents(query):
                continue

            attack_counter = defaultdict(lambda: defaultdict(int))
            for doc in db[col].find(query, {"src_geo": 1, "dst_geo": 1, "http_referer_geo": 1}):
                src = (doc.get("src_geo") or doc.get("http_referer_geo") or "ZZ").upper()
                dst = (doc.get("dst_geo") or "ZZ").upper()
                if src != "ZZ" and dst != "ZZ" and src != dst:
                    attack_counter[src][dst] += 1

            attacks = [(src, dst, cnt) for src, dsts in attack_counter.items() for dst, cnt in dsts.items()]
            if not attacks:
                continue

            org_dir = os.path.join("statistical_data", org, "generated_threatmaps")
            os.makedirs(org_dir, exist_ok=True)
            map_path = os.path.join(org_dir, f"{safe_filename(org)}_{today_str}_{safe_filename(col)}_map.png")
            create_attack_map(attacks, map_path, shapefile_path)

            meta = desc_lookup.get(col, {})
            collection_attacks[col] = {
                "attacks": attacks,
                "map": map_path,
                "title": meta.get("title", "Untitled"),
                "severity": meta.get("severity", "Unknown"),
                "description": meta.get("description", ""),
            }

        if collection_attacks:
            pdf = os.path.join("statistical_data", org, f"{safe_filename(org)}_{today_str}_attack_report.pdf")
            generate_pdf_report(org, db_name, collection_attacks, pdf, cert_name)
            print(f"Collections in report:")
            for col, data in collection_attacks.items():
                print(f" - {col}: Map image -> {data['map']}")
            print(f"PDF generated: {pdf}")
	    
        gc.collect()


if __name__ == "__main__":
    print("\nChecking required shapefiles...")
    for shapefile_type in ["admin_0_countries_10m", "admin_0_countries_50m", "admin_0_countries_110m"]:
        try:
            path = get_shapefile_path(shapefile_type)
            print(f"✔ Found shapefile for {shapefile_type}: {path}")
        except Exception as e:
            print(f"✖ Failed to retrieve shapefile for {shapefile_type}: {e}")

    main()
