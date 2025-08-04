# === Built-in libraries ===
import os
import io
import sys
import re
import gc
import ssl
import csv
import json
import time
import shutil
import asyncio
import hashlib
import imaplib
import zipfile
import tarfile
import gzip
import warnings
import json
import subprocess
import requests
from io import StringIO
from datetime import datetime
from functools import wraps
from email import message_from_bytes
from email.header import decode_header
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

# === Third-party libraries ===
import msal
import aiohttp
import aiofiles
import py7zr
import rarfile
import colorama
import asyncio
import pandas as pd
from pymongo import MongoClient, InsertOne
from pymongo.errors import BulkWriteError
from pymongo.errors import OperationFailure
from async_lru import alru_cache
from colorama import Fore, Style
from bs4 import BeautifulSoup
from tqdm import tqdm
from dotenv import load_dotenv
from email import message_from_bytes
from email.header import decode_header
from email.policy import default as default_policy
# === Email parsing ===
import email
from email.header import decode_header

# ========== CONSTANTS ==========
load_dotenv(dotenv_path=".env", override=True)
timestamp_now = datetime.now().strftime("%Y-%m-%d_%H%M")
log_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ✅ Define base directories first
attachments_dir = "attachments_documents_backup"
metadata_dir = "received_emails_metadata"
eml_export_dir = "exported_eml"
logging_dir = "logging"
tracker_dir = "file_tracking_system"
graph_tracker_path = os.path.join(tracker_dir, "graph_uid_tracker.json")

# Folder creation logic

def load_last_received_timestamp(graph_last_received_path):
    if os.path.exists(graph_last_received_path):
        try:
            with open(graph_last_received_path, "r") as f:
                return json.load(f).get("last_received")
        except Exception as e:
            print(f"⚠️ Error reading timestamp tracker: {e}")
    return None  
        
def save_last_received_timestamp(graph_last_received_path, latest_time):
    try:
        with open(graph_last_received_path, "w") as f:
            json.dump({"last_received": latest_time}, f)
        print(f"🕒 Updated last received timestamp: {latest_time}")
    except Exception as e:
        print(f"⚠️ Error saving timestamp tracker: {e}")
graph_last_received_path = os.path.join(tracker_dir, "graph_last_received.json")
last_received_time = load_last_received_timestamp(graph_last_received_path)        

for folder in [attachments_dir, metadata_dir, eml_export_dir, logging_dir, tracker_dir]:
    if not os.path.exists(folder):
        os.makedirs(folder)

#New Implementation Will Clean Up After
CONFIG_DIR = os.path.expanduser("~/.config/email_ingestion")
CONFIG_FILE = os.path.join(CONFIG_DIR, "ingestion_config.json")

def ensure_config_dir():
    os.makedirs(CONFIG_DIR, exist_ok=True)

def save_last_choice(option):
    ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        json.dump({"last_selected": option}, f)

def load_last_choice(force_reset=False):
    if force_reset:
        return None
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                if data.get("last_selected") in {"1", "2", "3"}:
                    return data["last_selected"]
        except Exception:
            pass
    return None

    
def get_env(key, default=None):
    value = os.getenv(key, default)
    if value is None:
        raise ValueError(f"[ENV Error] Missing environment variable: {key}")
    return value
    
def load_graph_uids():
    if os.path.exists(graph_tracker_path):
        with open(graph_tracker_path, "r") as f:
            return set(json.load(f))
    return set()
    
def save_graph_uids(uids):
    with open(graph_tracker_path, "w") as f:
        json.dump(sorted(list(uids)), f)

        

# === MongoDB Config ===
mongo_username = os.getenv("mongo_username")
mongo_password = os.getenv("mongo_password")
mongo_auth_source = os.getenv("mongo_auth_source", "admin")
mongo_host = os.getenv("mongo_host", "127.0.0.1")
mongo_port = int(os.getenv("mongo_port", 27017))
target_user = mongo_username
target_db = mongo_auth_source

print("\n🔐 MongoDB Configuration:")
print(f"  - Username       : {mongo_username}")
print(f"  - Password       : {'*' * len(mongo_password) if mongo_password else 'None'}")
print(f"  - Auth Source    : {mongo_auth_source}")
print(f"  - Host           : {mongo_host}")
print(f"  - Port           : {mongo_port}")

#========= DB USER ROLES DIAGNOSTIC RUN ===========

mongo_encoded_user = quote_plus(mongo_username)
mongo_encoded_pass = quote_plus(mongo_password)
uri = f"mongodb://{mongo_encoded_user}:{mongo_encoded_pass}@{mongo_host}:{mongo_port}/?authSource={mongo_auth_source}"
client = MongoClient(uri)
admin_db = client[mongo_auth_source]


try:
    user_data = admin_db.command("usersInfo", {"user": target_user, "db": target_db})
except OperationFailure as e:
    print(f"❌ Could not fetch user info: {e}")
    exit(1)

if not user_data.get("users"):
    print(f"❌ User '{target_user}' not found in DB '{target_db}'.")
    exit(1)

user_info = user_data["users"][0]
current_roles = [r["role"] for r in user_info["roles"]]

print(f"\n🔍 Current roles for {target_user}@{target_db}:")
for role in current_roles:
    print(f" - {role}")

# === Define required baseline roles ===
required_roles = ["readWriteAnyDatabase", "dbAdminAnyDatabase"]
missing_roles = [role for role in required_roles if role not in current_roles]

if missing_roles:
    print("\n🚨 This appears to be the first run for user role diagnostics.")
    print("The following essential roles are missing for full administrative scripting:")
    for role in missing_roles:
        print(f" - {role}@admin")

    proceed = input("\nDo you want to grant these roles to the user now? (yes/no): ").strip().lower()
    if proceed not in ["yes", "y"]:
        print("❌ Operation cancelled by user.")
    else:
        try:
            admin_db.command("grantRolesToUser", target_user, roles=[
                {"role": role, "db": "admin"} for role in missing_roles
            ])
            print("\n✅ Roles successfully applied.")
        except OperationFailure as e:
            print(f"\n❌ Failed to update roles: {e}")
            exit(1)

        # Show updated roles
        updated_info = admin_db.command("usersInfo", {"user": target_user, "db": target_db})["users"][0]
        updated_roles = [r["role"] for r in updated_info["roles"]]

        print(f"\n📜 Updated roles for {target_user}@{target_db}:")
        for role in updated_roles:
            print(f" - {role}")
else:
    print("\n✅ All required roles are already assigned. No changes needed.")


# === Email Config ===
mail_server = os.getenv("mail_server")
email_address = os.getenv("email_address")
password = os.getenv("email_password")
imap_folder = os.getenv("imap_shadowserver_folder_or_email_processing_folder", "inbox").strip('"')
# Retrieve from environment
email_provider       = os.getenv("email_provider", "graph")
graph_tenant_id      = os.getenv("graph_tenant_id", "unknown-tenant")
graph_client_id      = os.getenv("graph_client_id", "unknown-client-id")
graph_client_secret  = os.getenv("graph_client_secret", "")
graph_user_email     = os.getenv("graph_user_email", "user@example.com")


def mask_email(email):
    if "@" in email:
        local, domain = email.split("@", 1)
        masked_local = "*" * len(local)
        return f"{masked_local}@{domain}"
    return "*" * 5

def mask_secret(secret):
    return "*" * len(secret) if secret else "None"



# Mask sensitive values
masked_graph_email     = mask_email(graph_user_email)
masked_client_secret   = mask_secret(graph_client_secret)
masked_email_address   = mask_email(email_address)
# Output
print("\n🔐 Microsoft Graph Configuration:")
print(f"  - Provider                : {email_provider}")
print(f"  - Tenant ID              : {graph_tenant_id}")
print(f"  - Client ID              : {graph_client_id}")
print(f"  - Mailbox Email          : {masked_graph_email}")

print("\n📧 IMAP Configuration:")
print(f"  - Mail Host               : {mail_server}")
print(f"  - Email Address           : {masked_email_address}")
print(f"  - Email Password          : {'*' * len(password) if password else 'None'}")
print(f"  - IMAP Folder to Monitor  : {imap_folder}")


# === Regex Patterns ===
raw_fallback = os.getenv("geo_csv_fallback_regex", "")
raw_primary = os.getenv("geo_csv_regex", "")

print("\n📁 Regex Patterns(Safety: Fallback Runs in Code First Before Primary to Detect Unique Codes:")
print(f"  - Raw Primary    : {raw_primary}")
print(f"  - Raw Fallback   : {raw_fallback}")


with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=DeprecationWarning)
    try:
        GEO_CSV_PATTERN = re.compile(raw_primary.encode().decode("unicode_escape"))
        print(f"  ✅ Compiled Primary Pattern: {GEO_CSV_PATTERN.pattern}")
    except re.error as e:
        GEO_CSV_PATTERN = None
        print(f"  ❌ Failed to compile primary pattern: {e}")

    try:
        GEO_CSV_FALLBACK_PATTERN = re.compile(raw_fallback.encode().decode("unicode_escape"))
        print(f"  ✅ Compiled Fallback Pattern: {GEO_CSV_FALLBACK_PATTERN.pattern}")
    except re.error as e:
        GEO_CSV_FALLBACK_PATTERN = None
        print(f"  ❌ Failed to compile fallback pattern: {e}")


# Display Performance Settings (safe defaults)
shadowserver_buffer_size = int(os.getenv("buffer_size", "1024"))
shadowserver_flush_row_count_threshold = int(os.getenv("flush_row_count", "100"))
shadowserver_tracker_update_batch_size = int(os.getenv("tracker_batch_size", "1000"))
shadowserver_service_sorting_batch_size = int(os.getenv("service_sorting_batch_size", "1000"))
shadowserver_knowledgebase_ingestion_file_batch_size = int(
    os.getenv("number_of_files_ingested_into_knowledgebase_per_batch", "2000")
)

# Print configuration for performance-related settings
print("\n📊 [Shadowserver Performance Configuration]")
print(f"  • Buffer size for in-memory operations:                   {shadowserver_buffer_size}")
print(f"  • Row count threshold before flush to disk:               {shadowserver_flush_row_count_threshold}")
print(f"  • Tracker update batch size per cycle:                    {shadowserver_tracker_update_batch_size}")
print(f"  • Batch size for categorizing and sorting services:       {shadowserver_service_sorting_batch_size}")
print(f"  • File ingestion batch size for knowledgebase insertion:  {shadowserver_knowledgebase_ingestion_file_batch_size}\n")



# Base directories
root_directory = "shadowserver_analysis_system/sorted_companies_by_country"
asn_map_path = "shadowserver_analysis_system/detected_companies/asn_org_map.csv"



# ====== Future Plans  ======
BUFFER_SIZE = int(os.getenv("buffer_size", "1024"))
FLUSH_ROW_COUNT = int(os.getenv("flush_row_count", "100"))  # Tune based on memory budget

# SSL Context for IMAP connections
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

# Initialize colorama
colorama.init(autoreset=True)

# ========== COMMON HELPERS ==========

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def load_tracker(path):
    if os.path.exists(path):
        with open(path, 'r') as f:
            return set(json.load(f))
    return set()

def save_tracker(path, data_set):
    with open(path, 'w') as f:
        json.dump(sorted(data_set), f, indent=2)

def write_log_csv(folder, logname, headers, row):
    ensure_dir(folder)
    path = os.path.join(folder, logname)
    is_new = not os.path.exists(path)
    with open(path, "a", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(headers)
        writer.writerow(row)

# ========== HASHING FUNCTION ==========

async def hash_line(row):
    """
    Canonical hash:
    - Strip all whitespace
    - Lowercase strings
    - Sort fields alphabetically
    - Build consistent JSON string
    - Hash it
    """
    cleaned_row = {}
    for k, v in row.items():
        if isinstance(v, str):
            cleaned_value = v.strip().lower()
            cleaned_row[k] = cleaned_value
        else:
            cleaned_row[k] = v

    ordered_row = dict(sorted(cleaned_row.items()))
    json_string = json.dumps(ordered_row, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(json_string.encode('utf-8')).hexdigest()

# ========== DATABASE HELPERS ==========

async def get_dynamic_database(org_folder, asn, client):
    raw_name = f"{org_folder}-as{asn}".replace("-", "_").replace(".", "_")
    db_name = raw_name[-63:] if len(raw_name) > 63 else raw_name
    return client[db_name]

async def create_database_and_collections(category, db):
    db_collection = db[category]
    db_collection.create_index([("filename", 1), ("category", 1), ("line_hash", 1)], unique=True)

    discovered_fields_collection = db[f"discovered_fields_{category}"]
    files_collection = db[f"files_{category}"]
    files_collection.create_index([("filename", 1), ("category", 1), ("ingested", 1)])

    return db_collection, discovered_fields_collection, files_collection

async def count_total_files(category_path):
    return sum(len(files) for _, _, files in os.walk(category_path))

def update_discovered_fields(collection, category, field_name):
    return collection.update_one(
        {"category": category, "field_name": field_name},
        {"$setOnInsert": {"category": category, "field_name": field_name}},
        upsert=True
    )

# ========== DECORATORS ==========

def set_user_agent(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        headers = kwargs.get('headers', {})
        headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36'
        kwargs['headers'] = headers
        return await func(*args, **kwargs)
    return wrapper

# ========== ASYNC DOWNLOADERS ==========

@set_user_agent
@alru_cache
async def download_attachment(session, url, filename):
    async with session.get(url) as response:
        with open(filename, 'wb') as f:
            while True:
                chunk = await response.content.read(1024)
                if not chunk:
                    break
                f.write(chunk)

# ========== FILE EXTRACTION ==========

def extract_archive(file_path, ext, output_dir):
    try:
        if ext == "zip":
            with zipfile.ZipFile(file_path, 'r') as zf:
                zf.extractall(output_dir)
        elif ext == "tar":
            with tarfile.open(file_path) as tf:
                tf.extractall(output_dir)
        elif ext in ["gz", "tgz"]:
            with gzip.open(file_path, 'rb') as f_in:
                out_path = os.path.join(output_dir, os.path.basename(file_path).replace('.gz', ''))
                with open(out_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        elif ext == "7z":
            with py7zr.SevenZipFile(file_path, mode='r') as archive:
                archive.extractall(path=output_dir)
        elif ext == "rar":
            with rarfile.RarFile(file_path) as rf:
                rf.extractall(path=output_dir)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to extract {file_path}: {e}")
        return False







async def main_email_ingestion():
    print("Attempting to establish connection to the mail IMAP server...")



    # ✅ Ensure folders exist
    for d in [attachments_dir, metadata_dir, eml_export_dir, logging_dir, tracker_dir]:
        ensure_dir(d)

    # ✅ Tracker and log paths
    metadata_tracker = os.path.join(tracker_dir, "metadata_saved_uids.json")
    eml_tracker = os.path.join(tracker_dir, "eml_exported_uids.json")

    # ✅ Load previously seen UIDs
    saved_metadata_uids = load_tracker(metadata_tracker)
    saved_eml_uids = load_tracker(eml_tracker)
    last_seen_uid = max(saved_eml_uids, key=int) if saved_eml_uids else None
    print(f"[Tracker] Loaded {len(saved_eml_uids)} saved EML UIDs.")
    if last_seen_uid:
        print(f"[Tracker] Last seen UID from tracker: {last_seen_uid}")
    else:
        print("[Tracker] No previous UID found. Starting from the beginning.")
    None


    metadata_log_file = f"metadata_log_{timestamp_now}.csv"
    eml_log_file = f"eml_export_log_{timestamp_now}.csv"

    imap = None
    try:
        imap = imaplib.IMAP4_SSL(mail_server, ssl_context=context)
        print("Connection established successfully.")
        imap.login(email_address, password)
        print("Logged in successfully.")
        imap_folder = os.getenv("imap_shadowserver_folder_or_email_processing_folder", "inbox").strip('"')
        imap.select(imap_folder)


        # === Fetch Emails ===
        status, email_ids = imap.uid('search', None, 'ALL')
        email_ids = email_ids[0].split()

        if last_seen_uid:
            email_ids = [eid for eid in email_ids if int(eid) > int(last_seen_uid)]

        print(f"[IMAP] Found {len(email_ids)} new email(s) after UID {last_seen_uid or 'none'}")
        if not email_ids:
            print("[IMAP] No new emails to process. Exiting gracefully.")
            imap.logout()
            return  # Exit the async main


        async with aiohttp.ClientSession() as session:
             for email_id in email_ids:
                typ, uid_data = imap.uid('fetch', email_id, '(UID)')
                uid = uid_data[0].decode().split('UID ')[-1].split(')')[0]
                print(f"\n[Email] Checking UID: {uid}", end="\n", flush=True)
                if last_seen_uid and int(uid) <= int(last_seen_uid):
                    print(f"\n[Skip] UID {uid} already processed. Skipping.", end="\n", flush=True)
                    continue

                status, email_data = imap.uid('fetch', email_id, "(RFC822)")


                raw_email = email_data[0][1]
                msg = email.message_from_bytes(raw_email)
                email_size = len(raw_email)

                # === Export EML ===
                if uid not in saved_eml_uids:
                    eml_path = os.path.join(eml_export_dir, f"{uid}.eml")
                    with open(eml_path, "wb") as eml_file:
                        eml_file.write(raw_email)

                    write_log_csv(
                        os.path.join(logging_dir, "eml_exports"),
                        eml_log_file,
                        ["timestamp", "uid", "filename", "export_path"],
                        [log_time_str, uid, f"{uid}.eml", eml_path]
                    )
                    saved_eml_uids.add(uid)

                # === Skip if metadata already extracted ===
                if uid in saved_metadata_uids:
                    continue

                sender = msg.get("From")
                receiver = msg.get("To")
                date = msg.get("Date")

                received_headers = msg.get_all("Received", [])
                ip_addresses = []
                for header in received_headers:
                    ip_addresses += re.findall(r'\[(\d{1,3}(?:\.\d{1,3}){3})\]', header)

                sending_ip = ip_addresses[0] if ip_addresses else None
                receiving_ip = ip_addresses[-1] if len(ip_addresses) > 1 else None

                attachment_count = 0
                total_attachment_size = 0

                for part in msg.walk():
                    if part.get_content_maintype() == "multipart" or part.get("Content-Disposition") is None:
                        continue
                    filename = part.get_filename()
                    payload = part.get_payload(decode=True)
                    if payload:
                        total_attachment_size += len(payload)
                        attachment_count += 1
                        if filename:
                            decoded_filename = decode_header(filename)[0][0]
                            if isinstance(decoded_filename, bytes):
                                decoded_filename = decoded_filename.decode('utf-8', errors='replace')
                            attachment_path = os.path.join(attachments_dir, decoded_filename)
                            if not os.path.exists(attachment_path):
                                with open(attachment_path, "wb") as f:
                                    f.write(payload)
                                print(f"\rDownloaded {decoded_filename}", end="\r", flush=True)


                                write_log_csv(
                                    os.path.join(logging_dir, "folder_arrivals"),
                                    f"attachments_arrival_log_{timestamp_now}.csv",
                                    ["timestamp", "filename", "destination_folder"],
                                    [log_time_str, decoded_filename, attachments_dir]
                                )

                # === Extract links ===
                links = []
                body = ""
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type in ["text/html", "text/plain"]:
                        charset = part.get_content_charset() or "utf-8"
                        try:
                            body = part.get_payload(decode=True).decode(charset, errors='replace')
                        except Exception:
                            body = ""
                        break

                # ✅ Use BeautifulSoup only if body resembles HTML
                if "<" in body and ">" in body:
                    soup = BeautifulSoup(body, "html.parser")
                    links = [a['href'] for a in soup.find_all('a', href=True)]

                # ✅ Fallback to plain regex if no HTML found
                if not links:
                    links = re.findall(r'(https?://[^\s\'"<>]+)', body)

                # === Save metadata to CSV
                metadata_file = os.path.join(metadata_dir, f"{uid}.csv")
                with open(metadata_file, "w", newline='', encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "uid", "from", "to", "date",
                        "sending_ip", "receiving_ip",
                        "email_size_bytes", "total_attachment_size_bytes",
                        "attachment_count", "link_count", "links"
                    ])
                    writer.writerow([
                        uid, sender, receiver, date,
                        sending_ip, receiving_ip,
                        email_size, total_attachment_size,
                        attachment_count, len(links), ", ".join(links)
                    ])

                write_log_csv(
                    os.path.join(logging_dir, "email_metadata"),
                    metadata_log_file,
                    ["timestamp", "uid", "metadata_file"],
                    [log_time_str, uid, metadata_file]
                )
                saved_metadata_uids.add(uid)

        # ✅ Save trackers at the end
        save_tracker(metadata_tracker, saved_metadata_uids)
        save_tracker(eml_tracker, saved_eml_uids)

        # ✅ Close IMAP connection at the very end
        imap.logout()
        print("\nLogged out from IMAP server.", end="\n", flush=True)

    except imaplib.IMAP4.error as e:
        print(f"[IMAP Error] {e}")
    except Exception as e:
        print(f"[General Error] {e}")


async def attachment_sorting_shadowserver_report_migration():
    print("\n[Processor] Starting attachment sorting and Shadowserver report migration...\n")

    # === SORT ATTACHMENTS BY EXTENSION ===
    sorted_base = "sorted_attachments"
    ensure_dir(sorted_base)

    print("\n[Sorter] Starting to move attachments by extension...\n")
    for root, dirs, files in os.walk(attachments_dir):
        for file in files:
            ext = os.path.splitext(file)[1].lower().strip(".")
            if not ext:
                continue
            ext_folder = os.path.join(sorted_base, f"{ext}_sorted")
            ensure_dir(ext_folder)
            src = os.path.join(root, file)
            dst = os.path.join(ext_folder, file)
            if not os.path.exists(dst):
                shutil.move(src, dst)
                print(f"\r[Sort] Processing: {ext_folder}", end="\r", flush=True)
            else:
                print(f"\r[Sort] already sorted: {file}", end="\r", flush=True)

    # === UNZIP & ARCHIVE HANDLING ===
    unzipped_dir = "unzipped_backup"
    ensure_dir(unzipped_dir)

    archive_exts = ["zip", "rar", "tar", "gz", "7z"]
    archive_tracker_paths = {ext: os.path.join(tracker_dir, f"unzipped_{ext}.json") for ext in archive_exts}
    archive_trackers = {ext: load_tracker(path) for ext, path in archive_tracker_paths.items()}
    archive_logs = {ext: f"unzip_log_{timestamp_now}.csv" for ext in archive_exts}

    print("\n[Unzipper] Scanning sorted folders for archives...\n")
    for ext in archive_exts:
        sorted_folder = os.path.join(sorted_base, f"{ext}_sorted")
        if not os.path.exists(sorted_folder):
            print(f"[Unzipper] Skipping {ext}: No sorted folder found.")
            continue

        output_folder = os.path.join(unzipped_dir, f"{ext}_unzipped")
        ensure_dir(output_folder)

        for file in os.listdir(sorted_folder):
            if file in archive_trackers[ext]:
                print(f"\r[Unzipper] already extracted: {file}", end="\r", flush=True)
                continue

            archive_path = os.path.join(sorted_folder, file)
            print(f"\r[Unzipper] Extracting: {archive_path} → {output_folder}", end="\r", flush=True)

            success = extract_archive(archive_path, ext, output_folder)
            if success:
                archive_trackers[ext].add(file)

                write_log_csv(
                    os.path.join(logging_dir, f"unzipping_{ext}"),
                    archive_logs[ext],
                    ["timestamp", "zip_file_path", "destination_folder"],
                    [log_time_str, archive_path, output_folder]
                )

                write_log_csv(
                    os.path.join(logging_dir, "folder_arrivals"),
                    f"{ext}_unzip_arrival_log_{timestamp_now}.csv",
                    ["timestamp", "filename", "destination_folder"],
                    [log_time_str, file, output_folder]
                )
            else:
                print(f"\r[Unzipper][ERROR] Failed to extract: {file}", end="\r", flush=True)

    for ext, path in archive_tracker_paths.items():
        save_tracker(path, archive_trackers[ext])

    # ==== SHADOWSERVER FILE RELOCATION ====
    shadowserver_base = "shadowserver_analysis_system"
    shadowserver_dest = os.path.join(shadowserver_base, "received_shadowserver_reports")
    ensure_dir(shadowserver_dest)

    print("\n[Shadowserver] Searching for CSV files with date-prefixed names in unzipped folders...\n")
    shadowserver_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}-.*\.csv$", re.IGNORECASE)

    for root, dirs, files in os.walk(unzipped_dir):
        for file in files:
            if shadowserver_pattern.match(file):
                src_path = os.path.join(root, file)
                dest_path = os.path.join(shadowserver_dest, file)
                if not os.path.exists(dest_path):
                    shutil.move(src_path, dest_path)
                    print(f"\r[Shadowserver] Moved: {file} → {shadowserver_dest}", end="\r", flush=True)
                else:
                    print(f"\r[Shadowserver] Skipped (already exists): {file}", end="\r", flush=True)

    # ==== DISSEMINATED ADVISORY CSV RELOCATION ====
    advisories_base = "dissemenated_advisories_system"
    advisories_dest = os.path.join(advisories_base, "attached_csv_reports")
    ensure_dir(advisories_dest)

    advisory_sorted_dir = os.path.join("sorted_attachments", "csv_sorted")
    advisory_prefix = os.getenv("advisory_prefix")

    print(f"\n[Advisories] Searching for advisory CSVs starting with {advisory_prefix}...\n")
    if os.path.exists(advisory_sorted_dir):
        for file in os.listdir(advisory_sorted_dir):
            if file.startswith(advisory_prefix) and file.endswith(".csv"):
                src_path = os.path.join(advisory_sorted_dir, file)
                dest_path = os.path.join(advisories_dest, file)
                if not os.path.exists(dest_path):
                    shutil.move(src_path, dest_path)
                    print(f"\r[Advisories] Moved: {file} → {advisories_dest}", end="\r", flush=True)
                else:
                    print(f"\r[Advisories] Skipped (already exists): {file}", end="\r", flush=True)

    # ==== DISSEMINATED ADVISORY PDF RELOCATION ====
    advisory_pdf_dest = os.path.join(advisories_base, "attached_pdf_reports")
    ensure_dir(advisory_pdf_dest)

    advisory_pdf_dir = os.path.join("sorted_attachments", "pdf_sorted")

    print(f"\n[Advisories] Searching for advisory PDFs starting with {advisory_prefix}...\n")
    if os.path.exists(advisory_pdf_dir):
        for file in os.listdir(advisory_pdf_dir):
            if file.startswith(advisory_prefix) and file.endswith(".pdf"):
                src_path = os.path.join(advisory_pdf_dir, file)
                dest_path = os.path.join(advisory_pdf_dest, file)
                if not os.path.exists(dest_path):
                    shutil.move(src_path, dest_path)
                    print(f"\r[Advisories] Moved: {file} → {advisory_pdf_dest}", end="\r", flush=True)
                else:
                    print(f"\r[Advisories] Skipped (already exists): {file}", end="\r", flush=True)


import re
from email import message_from_bytes
from email.policy import default as default_policy

async def ingest_microsoft_graph():
    print("🔐 Authenticating with Microsoft Graph API...")
    authority = f"https://login.microsoftonline.com/{graph_tenant_id}"
    scope = ["https://graph.microsoft.com/.default"]

    app = msal.ConfidentialClientApplication(
        client_id=graph_client_id,
        authority=authority,
        client_credential=graph_client_secret 
    )

    result = app.acquire_token_silent(scope, account=None)
    if not result:
        result = app.acquire_token_for_client(scopes=scope)

    if "access_token" not in result:
        print("❌ Failed to obtain access token:", result.get("error_description"))
        return

    print("✅ Successfully authenticated to Microsoft Graph.")

    # === Load trackers ===
    os.makedirs(tracker_dir, exist_ok=True)

    if os.path.exists(graph_tracker_path):
        with open(graph_tracker_path, "r") as f:
            seen_uids = set(json.load(f))
    else:
        seen_uids = set()

    graph_last_received_path = os.path.join(tracker_dir, "graph_last_received.json")
    last_received_time = load_last_received_timestamp(graph_last_received_path)

    # === Build Graph API endpoint ===
    filter_clause = f"&$filter=receivedDateTime gt {last_received_time}" if last_received_time else ""
    graph_endpoint = (
        f"https://graph.microsoft.com/v1.0/users/{graph_user_email}/mailFolders/inbox/messages"
        f"?$top=200&$orderby=receivedDateTime desc{filter_clause}"
    )

    headers = {
        "Authorization": f"Bearer {result['access_token']}",
        "Content-Type": "application/json"
    }

    response = requests.get(graph_endpoint, headers=headers)
    if response.status_code != 200:
        print(f"❌ Error fetching emails: {response.status_code} - {response.text}")
        return

    emails = response.json().get("value", [])
    print(f"📬 Retrieved {len(emails)} email(s) from inbox.")

    new_uids = set()
    latest_time = last_received_time

    for email_entry in emails:
        message_id = str(email_entry.get("id")).strip()
        if message_id in seen_uids:
            continue

        subject = email_entry.get("subject")
        sender = email_entry.get("from", {}).get("emailAddress", {}).get("address")
        received_time = email_entry.get("receivedDateTime")

        print(f"\n📧 Email: '{subject}' from {sender} at {received_time}")

        mime_url = f"https://graph.microsoft.com/v1.0/users/{graph_user_email}/messages/{message_id}/$value"
        raw_response = requests.get(mime_url, headers=headers)

        if raw_response.status_code != 200:
            print(f"⚠️ Failed to get MIME content for message {message_id}: {raw_response.status_code}")
            continue

        raw_email = raw_response.content
        eml_path = os.path.join(eml_export_dir, f"{message_id}.eml")
        with open(eml_path, "wb") as f:
            f.write(raw_email)

        # === MIME Parsing for Attachments or Shadowserver Links ===
        msg = message_from_bytes(raw_email, policy=default_policy)
        attachment_found = False
        attachment_names = []

        for part in msg.walk():
            content_disposition = part.get("Content-Disposition", "")
            if "attachment" in content_disposition.lower():
                filename = part.get_filename()
                if filename:
                    attachment_found = True
                    attachment_names.append(filename)
                    attachment_path = os.path.join(attachment_dir, filename)
                    with open(attachment_path, "wb") as f:
                        f.write(part.get_payload(decode=True))
                    print(f"📎 Attachment found and saved: {filename}")

        if not attachment_found:
            print("📭 No attachments found. Scanning body for Shadowserver links...")
            body_text = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body_text += part.get_content()
            else:
                body_text = msg.get_content()

            shadow_links = re.findall(r'https://dl\.shadowserver\.org/\S+', body_text)
            if shadow_links:
                print(f"🔗 Found {len(shadow_links)} Shadowserver link(s):")
                for link in shadow_links:
                    print(f"   • {link}")
                write_log_csv(
                    os.path.join(logging_dir, "shadow_links"),
                    f"shadow_links_log_{log_time_str[:10]}.csv",
                    ["timestamp", "uid", "url"],
                    [[log_time_str, message_id, link] for link in shadow_links]
                )
            else:
                print("❌ No Shadowserver links found in body.")

        # === Final Log and State Tracking ===
        write_log_csv(
            os.path.join(logging_dir, "eml_exports"),
            f"eml_export_log_{log_time_str[:10]}.csv",
            ["timestamp", "uid", "filename", "export_path"],
            [log_time_str, message_id, f"{message_id}.eml", eml_path]
        )

        if attachment_found:
            print(f"✅ Attachments processed: {', '.join(attachment_names)}")
        else:
            print("ℹ️ No attachments. Shadowserver link scan completed.")

        new_uids.add(message_id)
        seen_uids.add(message_id)
        if received_time and (not latest_time or received_time > latest_time):
            latest_time = received_time

    if new_uids:
        with open(graph_tracker_path, "w") as f:
            json.dump(sorted(list(seen_uids)), f)
        print(f"📝 Saved {len(new_uids)} new UID(s) to tracker.")
    else:
        print("ℹ️ No new emails to ingest.")

    if latest_time:
        save_last_received_timestamp(graph_last_received_path, latest_time)










async def main_refresh_shadowserver_whois():
    print("\n[ASN Refresh] Verifying all ASN entries in ASN map for updates...")

    asn_map_csv = os.path.join("shadowserver_analysis_system", "detected_companies", "asn_org_map.csv")
    if os.path.exists(asn_map_csv):
        asn_df = pd.read_csv(asn_map_csv, dtype=str)
        updated_rows = 0

        # Ensure country_code column exists
        if "country_code" not in asn_df.columns:
            asn_df["country_code"] = ""

        for i, row in asn_df.iterrows():
            asn = row["asn"]
            current_org = row["org_name"]
            current_folder = row["org_folder"]
            current_country = str(row["country_code"]).strip() if pd.notna(row["country_code"]) else ""

            print(f"[ASN Refresh] Checking ASN {asn}...")

            try:
                cmd = ['whois', '-h', 'whois.cymru.com', f" -v as{asn}"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                print(f"[WHOIS] Raw for ASN {asn}:\n{result.stdout.strip()}\n")
                lines = result.stdout.strip().split('\n')

                if len(lines) >= 2:
                    data_line = lines[1]
                    parts = [part.strip() for part in data_line.split('|')]

                    if len(parts) >= 5:
                        new_country_code = parts[1].lower() if parts[1] else ""
                        as_name = parts[-1]

                        # === Special Handling ===
                        is_name_invalid = as_name.strip() in {"", ","}
                        folder_name = re.sub(r'\W+', '_', as_name.strip().lower())
                        is_folder_invalid = folder_name.strip() in {"", "_"}

                        # Reserved ASN
                        if "-Reserved AS-, ZZ" in as_name:
                            as_name = "-Reserved AS-, ZZ"
                            folder_name = f"reserved_as_{asn}"
                            new_country_code = "reserved"
                            print(f"[ASN Refresh] ASN {asn} is reserved. Setting special fields.")

                        # NO_NAME ASN
                        elif as_name.strip().upper() == "NO_NAME":
                            as_name = "no_name"
                            folder_name = "no_name"
                            new_country_code = "no_name"
                            print(f"[ASN Refresh] ASN {asn} is NO_NAME. Setting special fields.")

                        # Invalid WHOIS data
                        elif is_name_invalid or is_folder_invalid:
                            as_name = "not_found"
                            folder_name = "not_found"
                            new_country_code = "unknown"
                            print(f"🚨 [ASN Refresh] ASN {asn} WHOIS returned invalid data. Forcing to 'not_found'.")

                        # Compare and update
                        changes = False

                        if current_org != as_name:
                            print(f"✅ [ASN Refresh] ASN {asn} org name changed: '{current_org}' → '{as_name}'")
                            asn_df.at[i, "org_name"] = as_name
                            changes = True

                        if current_folder != folder_name:
                            print(f"✅ [ASN Refresh] ASN {asn} org folder changed: '{current_folder}' → '{folder_name}'")
                            asn_df.at[i, "org_folder"] = folder_name
                            changes = True

                        if current_country in {"", "unknown", "lookup_error"} or current_country != new_country_code:
                            print(f"🌍 [ASN Refresh] ASN {asn} country code changed: '{current_country}' → '{new_country_code}'")
                            asn_df.at[i, "country_code"] = new_country_code
                            changes = True

                        if changes:
                            updated_rows += 1

                        time.sleep(1)
                    else:
                        print(f"[ASN Refresh][WARN] Unexpected WHOIS format for ASN {asn}: {data_line}")
                else:
                    print(f"[ASN Refresh][WARN] No WHOIS response for ASN {asn}")

            except Exception as e:
                print(f"[ASN Refresh][ERROR] Failed WHOIS lookup for ASN {asn}: {e}")

        # Save after processing
        if updated_rows > 0:
            asn_df.to_csv(asn_map_csv, index=False)
            print(f"\n✅ [ASN Refresh] Updated {updated_rows} entries saved to: {asn_map_csv}")
        else:
            print("[ASN Refresh] No updates were needed.")

        # === Post-save recheck ===
        print("\n=== Post-Save Validation of CSV ===")
        confirm_df = pd.read_csv(asn_map_csv, dtype=str)

        for check_asn in confirm_df["asn"]:
            row = confirm_df[confirm_df["asn"] == check_asn]
            if not row.empty:
                org_name_val = row.iloc[0]["org_name"]
                org_folder_val = row.iloc[0]["org_folder"]
                country_val = row.iloc[0]["country_code"]

                print(f"[Confirm CSV] ASN {check_asn} → org='{org_name_val}', folder='{org_folder_val}', country='{country_val}'")

                if org_name_val.strip() in {"", ","} or org_folder_val.strip() in {"", "_"}:
                    print(f"🚨 [Confirm CSV] ASN {check_asn} still invalid after save. Forcing 'not_found'.")
                    confirm_df.loc[confirm_df["asn"] == check_asn, "org_name"] = "not_found"
                    confirm_df.loc[confirm_df["asn"] == check_asn, "org_folder"] = "not_found"

                if pd.isna(country_val) or str(country_val).strip() in {"", "unknown", "lookup_error"}:
                    print(f"🌍 [Confirm CSV] ASN {check_asn} still missing country after save. Setting to 'unknown'.")
                    confirm_df.loc[confirm_df["asn"] == check_asn, "country_code"] = "unknown"

            else:
                print(f"🚨 [Confirm CSV] ASN {check_asn} not found in CSV!")

        confirm_df.to_csv(asn_map_csv, index=False)
        print("\n✅ [Final Save] All corrections written to CSV.\n")






async def main_shadowserver_processing():
    # ==== SHADOWSERVER ASN-BASED ORGANISATION FILTERING ====

    # ✅ Define base directories first
    attachments_dir = "attachments_documents_backup"
    metadata_dir = "received_emails_metadata"
    eml_export_dir = "exported_eml"
    logging_dir = "logging"
    tracker_dir = "file_tracking_system"

    # ✅ ASN map and related directories
    asn_map_dir = os.path.join("shadowserver_analysis_system", "detected_companies")
    ensure_dir(asn_map_dir)

    asn_map_csv = os.path.join(asn_map_dir, "asn_org_map.csv")

    # ✅ Shadowserver report directories
    shadowserver_dir = os.path.join("shadowserver_analysis_system", "received_shadowserver_reports")
    reported_base = os.path.join("shadowserver_analysis_system", "reported_companies")
    ensure_dir(reported_base)

    print("\n[Shadowserver] Resolving ASN fields and relocating reports...")
    def load_known_asns():
        if os.path.exists(asn_map_csv):
            df = pd.read_csv(asn_map_csv, dtype=str)
            if "country_code" not in df.columns:
                df["country_code"] = ""
            return dict(zip(df["asn"], df["org_folder"])), df
        else:
            return {}, pd.DataFrame(columns=["asn", "org_name", "org_folder", "country_code"])
    # === Tracker setup ===
    asn_filter_tracker_path = os.path.join(tracker_dir, "asn_filtered_shadowserver_reports.json")
    asn_filtered_files = load_tracker(asn_filter_tracker_path)

    # === ASN Map CSV setup ===
    def resolve_asn_org(asn, known_asns, new_asns):
        asn_str = str(asn)
        if asn_str in known_asns:
            folder = known_asns[asn_str]
            print(f"[Cached] ASN {asn} → Folder: {folder}")
            return folder

        try:
            cmd = ['whois', '-h', 'whois.cymru.com', f" -v as{asn}"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            print(f"\n[WHOIS] Raw response for ASN {asn}:\n{result.stdout.strip()}\n")
            lines = result.stdout.strip().split('\n')

            if len(lines) >= 2:
                data_line = lines[1]
                print(f"[WHOIS] Parsed line for ASN {asn}: {data_line}")
                parts = [part.strip() for part in data_line.split('|')]

                if len(parts) == 5:
                    new_country_code = parts[1].lower() if parts[1] else ""
                    as_name = parts[-1]

                    is_name_invalid = as_name.strip() in {"", ","}
                    folder_name = re.sub(r'\W+', '_', as_name.strip().lower())
                    is_folder_invalid = folder_name.strip() in {"", "_"}

                    # Reserved ASN handling
                    if "-Reserved AS-, ZZ" in as_name:
                        as_name = "-Reserved AS-, ZZ"
                        folder_name = f"reserved_as_{asn_str}"
                        new_country_code = "reserved"
                        print(f"[WHOIS] ASN {asn} is reserved. Setting special fields.")

                    # NO_NAME ASN handling
                    elif as_name.strip().upper() == "NO_NAME":
                        as_name = "no_name"
                        folder_name = "no_name"
                        new_country_code = "no_name"
                        print(f"[WHOIS] ASN {asn} is NO_NAME. Setting special fields.")

                    # Invalid name/folder handling
                    elif is_name_invalid or is_folder_invalid:
                        as_name = "not_found"
                        folder_name = "not_found"
                        new_country_code = "unknown"
                        print(f"🚨 [ASN WHOIS] ASN {asn} WHOIS returned invalid data. Forcing to 'not_found'.")

                    # Update caches
                    known_asns[asn_str] = folder_name
                    new_asns[asn_str] = {
                        "asn": asn_str,
                        "org_name": as_name,
                        "org_folder": folder_name,
                        "country_code": new_country_code
                    }

                    print(f"[INLINE CHECK] ASN {asn} → org_name='{as_name}', org_folder='{folder_name}', country_code='{new_country_code}'")

                    time.sleep(1)
                    return folder_name

                else:
                    print(f"[ASN WHOIS][WARN] Unexpected format for ASN {asn}: {data_line}")
            else:
                print(f"[ASN WHOIS][WARN] No valid WHOIS response for ASN {asn}")

        except Exception as e:
            print(f"[ASN WHOIS][ERROR] ASN {asn} resolution failed: {e}")

        return None


    async def process_shadowserver_files():
        known_asns, asn_df = load_known_asns()
        new_asns = {}
        org_map = {}

        for file in os.listdir(shadowserver_dir):
            if not file.endswith(".csv"):
                continue
            if file in asn_filtered_files:
                print(f"\r[Tracker] Skipping already processed file: {file}", end="\r", flush=True)
                continue

            file_path = os.path.join(shadowserver_dir, file)
            try:
                df = pd.read_csv(file_path)
            except Exception as e:
                print(f"[SKIP] Could not read {file}: {e}")
                continue

            asn_field = next((col for col in df.columns if col in ["asn", "src_asn", "http_referer_asn"]), None)

            if not asn_field:
                # No ASN field found. Handle as "other_intelligence_gh"
                print(f"[Info] No ASN field found in {file}. Assigning to 'other_intelligence_gh'")
                folder_name = "other_intelligence_gh"
                target_dir = os.path.join(reported_base, folder_name)
                ensure_dir(target_dir)

                save_path = os.path.join(target_dir, file)
                df.to_csv(save_path, index=False)
                print(f"[Save] {file} saved to {folder_name}/")

                asn_filtered_files.add(file)
                save_tracker(asn_filter_tracker_path, asn_filtered_files)

                # Optionally save an audit CSV for traceability
                audit_base_dir = os.path.join("shadowserver_analysis_system", "organisation_file_audits")
                ensure_dir(audit_base_dir)
                audit_save_path = os.path.join(audit_base_dir, f"{os.path.splitext(file)[0]}_audit.csv")
                audit_df = pd.DataFrame([{
                    "asn": "N/A",
                    "expected_rows": len(df),
                    "saved_rows": len(df),
                    "save_file": file,
                    "org_folder": folder_name,
                    "status": "OK"
                }])
                audit_df.to_csv(audit_save_path, index=False)

                print(f"[Audit Save] Audit file generated for non-ASN file: {audit_save_path}")
                continue

            # Normalize ASN values
            df[asn_field] = df[asn_field].astype(str).str.extract(r"(\d+)", expand=False)
            df[asn_field] = pd.to_numeric(df[asn_field], errors='coerce').astype("Int64")
            df = df.dropna(subset=[asn_field])
            unique_asns = df[asn_field].dropna().unique()



            # === Resolve all ASN folders first
            for asn in unique_asns:
                folder = resolve_asn_org(asn, known_asns, new_asns)
                if folder:
                    org_map[asn] = folder

            sem = asyncio.Semaphore(10)

            async def async_save_filtered_csv(asn, folder_name, df, file, asn_field):
                async with sem:
                    filtered = df[df[asn_field] == asn]
                    if filtered.empty:
                        return None

                    target_dir = os.path.join(reported_base, folder_name)
                    ensure_dir(target_dir)

                    base_name, ext = os.path.splitext(file)
                    base_name = re.sub(r'_as\d+$', '', base_name)
                    save_name = f"{base_name}_as{asn}{ext}"
                    save_path = os.path.join(target_dir, save_name)

                    csv_buffer = StringIO()
                    filtered.to_csv(csv_buffer, index=False)
                    original_hash = hashlib.md5(csv_buffer.getvalue().encode("utf-8")).hexdigest()

                    async with aiofiles.open(save_path, mode='w', encoding='utf-8') as f:
                        await f.write(csv_buffer.getvalue())

                    async with aiofiles.open(save_path, mode='r', encoding='utf-8') as f:
                        saved_content = await f.read()
                        saved_hash = hashlib.md5(saved_content.encode("utf-8")).hexdigest()

                    if original_hash != saved_hash:
                        print(f"\n[Validation ❌] Hash mismatch for {save_name}. Retrying...")
                        async with aiofiles.open(save_path, mode='w', encoding='utf-8') as f:
                            await f.write(csv_buffer.getvalue())

                        async with aiofiles.open(save_path, mode='r', encoding='utf-8') as f:
                            retry_content = await f.read()
                            retry_hash = hashlib.md5(retry_content.encode("utf-8")).hexdigest()

                        if retry_hash != original_hash:
                            print(f"\n🚨 [FATAL] Validation still failed after retry for {save_name}")
                            sys.exit(1)
                        else:
                            print(f"\n[Validation ✅] Retry succeeded for {save_name}")
                    else:
                        print(f"\r[Shadowserver] {file} → ASN {asn} → {folder_name} → Hash verified: {save_name}", end="\r", flush=True)

                    expected_row_count = len(filtered)
                    line_count_with_header = saved_content.count('\n')
                    saved_row_count = line_count_with_header - 1

                    return {
                        "asn": str(asn),
                        "expected_rows": expected_row_count,
                        "saved_rows": saved_row_count,
                        "saved_lines_with_header": line_count_with_header,
                        "save_file": save_name,
                        "org_folder": folder_name,
                        "status": "OK" if expected_row_count == saved_row_count else "MISMATCH"
                    }


            # === Launch tasks
            tasks = [
                async_save_filtered_csv(asn, folder_name, df, file, asn_field)
                for asn, folder_name in org_map.items()
            ]

            file_audit_records = await asyncio.gather(*tasks)
            file_audit_records = [r for r in file_audit_records if r is not None]

            # === Save Audit CSV immediately after processing the file
            audit_base_dir = os.path.join("shadowserver_analysis_system", "organisation_file_audits")
            ensure_dir(audit_base_dir)

            audit_save_path = os.path.join(audit_base_dir, f"{os.path.splitext(file)[0]}_audit.csv")
            audit_df = pd.DataFrame(file_audit_records)
            audit_df.to_csv(audit_save_path, index=False, columns=[
                "asn", "expected_rows", "saved_rows", "saved_lines_with_header", "save_file", "org_folder", "status"
            ])

            print(f"\n[Audit Save] Audit file generated: {audit_save_path}")

            # === Optional: Pretty Print Audit Table
            if not audit_df.empty:
                print("\n[Audit Table]")
                for _, row in audit_df.iterrows():
                    status = "OK" if row["expected_rows"] == row["saved_rows"] else "MISMATCH"
                    color = Fore.GREEN if status == "OK" else Fore.RED
                    header_check = ""

                    if (row.get("saved_rows") is not None) and (row.get("saved_lines_with_header") is not None):
                        if row["saved_lines_with_header"] != row["saved_rows"] + 1:
                            header_check = " 🚨 [Header Mismatch]"

                    asn_display = row["asn"]
                    if asn_display == "N/A":
                        asn_display = Fore.YELLOW + "N/A" + Style.RESET_ALL

                    print(
                        color
                        + f" ASN: {asn_display} | Expected: {row['expected_rows']} | Saved: {row['saved_rows']} "
                          f"| Lines with Header: {row['saved_lines_with_header']} | File: {row['save_file']} "
                          f"| Org: {row['org_folder']} | Status: {status}{header_check}"
                        + Style.RESET_ALL
                    )
                    row["status"] = status


                if any(row["expected_rows"] != row["saved_rows"] for _, row in audit_df.iterrows()):
                    print(Fore.RED + "\n🚨 [FATAL] One or more saved files did not match expected row count. Exiting.\n" + Style.RESET_ALL)
                    sys.exit(1)


            # === Save new ASN mappings if any
            if new_asns:
                new_df = pd.DataFrame.from_dict(new_asns, orient='index')
                final_df = pd.concat([asn_df, new_df], ignore_index=True).drop_duplicates(subset="asn")

                final_df["org_name"] = final_df["org_name"].fillna("").apply(
                    lambda x: "not_found" if x.strip() == "," or x.strip() == "" else x.strip()
                )
                final_df["org_folder"] = final_df["org_folder"].fillna("").apply(
                    lambda x: "not_found" if x.strip() == "_" or x.strip() == "" else x.strip()
                )

                bad_orgs = final_df[final_df["org_name"].isin([",", "", "not_found"])]
                bad_folders = final_df[final_df["org_folder"].isin(["_", "", "not_found"])]

                if not bad_orgs.empty or not bad_folders.empty:
                    print("\n🚨 [ASN FIX WARNING] Detected unresolved entries:")
                    if not bad_orgs.empty:
                        print("[Unresolved org_name]:")
                        print(bad_orgs[["asn", "org_name"]].to_string(index=False))
                    if not bad_folders.empty:
                        print("[Unresolved org_folder]:")
                        print(bad_folders[["asn", "org_folder"]].to_string(index=False))
                else:
                    print("✅ [ASN FIX] All org_name and org_folder values are clean.")

                final_df.to_csv(asn_map_csv, index=False)
                print(f"[ASN Cache] Updated with {len(new_asns)} new entries.")

            # === Mark file as filtered
            asn_filtered_files.add(file)
            save_tracker(asn_filter_tracker_path, asn_filtered_files)


    await process_shadowserver_files() 




async def sort_shadowserver_by_country(use_tracker=False, country_tracker_mode="manual"):
    print("\n[Country Sorter] Organising reported companies by ASN country code...")

    # === Tracker Mode Logic ===
    BATCH_SIZE = int(os.getenv("tracker_batch_size", "1000"))
    tracker_dir = "file_tracking_system"
    country_tracker_path = os.path.join(tracker_dir, "country_sort_tracker.json")

    if country_tracker_mode == "auto":
        use_tracker = True  # you can add logic like: if file count > threshold

    if use_tracker:
        print(f"🌍 [Country Task] Tracker is ENABLED ({country_tracker_mode.upper()} mode)")
    else:
        print(f"🌍 [Country Task] Tracker is DISABLED ({country_tracker_mode.upper()} mode)")

    # === Directories
    asn_map_dir = os.path.join("shadowserver_analysis_system", "detected_companies")
    reported_base = os.path.join("shadowserver_analysis_system", "reported_companies")
    sorted_country_base = os.path.join("shadowserver_analysis_system", "sorted_companies_by_country")
    ensure_dir(sorted_country_base)

    timestamp_now = datetime.now().strftime("%Y-%m-%d_%H%M")
    log_folder = os.path.join("logging", "shadowserver_country_sort")
    ensure_dir(log_folder)
    country_log_path = os.path.join(log_folder, f"country_sort_log_{timestamp_now}.csv")

    country_map_csv = os.path.join(asn_map_dir, "asn_org_map.csv")

    # ✅ Special Handling: Ensure map file exists and inject fallback
    if os.path.exists(country_map_csv):
        country_df = pd.read_csv(country_map_csv, dtype=str)
    else:
        country_df = pd.DataFrame(columns=["asn", "org_name", "org_folder", "country_code"])

    if not (country_df["org_folder"] == "other_intelligence_gh").any():
        print("[Special Handling] 'other_intelligence_gh' not found in map. Adding manually...")
        special_entry = {
            "asn": "N/A",
            "org_name": "other_intelligence_gh",
            "org_folder": "other_intelligence_gh",
            "country_code": "other_intelligence_gh"
        }
        country_df = pd.concat([country_df, pd.DataFrame([special_entry])], ignore_index=True)
        country_df.drop_duplicates(subset=["org_folder"]).to_csv(country_map_csv, index=False)
        print("[Special Handling] Map file updated with 'other_intelligence_gh'.")

    # === Load tracker if enabled
    if use_tracker and os.path.exists(country_tracker_path):
        with open(country_tracker_path, "r") as tf:
            country_tracker = json.load(tf)
    else:
        country_tracker = {}

    existing_country_map = country_df.set_index("asn").to_dict("index")

    # === WHOIS Lookup
    for idx, row in country_df.iterrows():
        asn = row["asn"]
        org_name = row["org_name"]
        if "-Reserved AS-, ZZ" in org_name:
            continue
        if asn not in existing_country_map or not existing_country_map[asn].get("country_code"):
            print(f"[WHOIS] Looking up ASN {asn} ({org_name})...")
            try:
                cmd = ['whois', '-h', 'whois.cymru.com', f" -v as{asn}"]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 2:
                    parts = [part.strip() for part in lines[1].split('|')]
                    country_code = parts[1].lower()
                    country_df.at[idx, "country_code"] = country_code
                    print(f"[WHOIS] ASN {asn} → {country_code}")
                else:
                    country_df.at[idx, "country_code"] = "unknown"
            except Exception:
                country_df.at[idx, "country_code"] = "lookup_error"
            time.sleep(1)

    # === Save updated country map
    country_df.to_csv(country_map_csv, index=False)
    print("[Step 1] WHOIS updates completed.\n")

    # === Move Files
    print("[Step 2] Reloading updated country map...")
    country_df = pd.read_csv(country_map_csv, dtype=str)

    async def move_one_file(src_item, dest_item, asn, org_name, org_folder, country_code, writer):
        try:
            if not os.path.exists(dest_item):
                shutil.move(src_item, dest_item)
                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    asn, org_name, org_folder, country_code, dest_item, "moved"
                ])
                if use_tracker:
                    country_tracker.setdefault(org_folder, []).append(os.path.basename(dest_item))
                return True
            else:
                writer.writerow([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    asn, org_name, org_folder, country_code, dest_item, "skipped (exists)"
                ])
                return False
        except Exception as e:
            print(f"❌ [Error Moving] {src_item}: {e}")
            return False

    with open(country_log_path, "w", encoding="utf-8", newline='') as log_f:
        writer = csv.writer(log_f)
        writer.writerow(["timestamp", "asn", "org_name", "org_folder", "country_code", "destination_path", "status"])

        print("[Step 3] Starting per-organization processing...\n")

        for _, row in country_df.iterrows():
            asn = row["asn"]
            org_name = row["org_name"]
            org_folder = row["org_folder"]
            country_code = row["country_code"]

            org_path = os.path.join(reported_base, org_folder)
            if not os.path.isdir(org_path):
                print(f"[Skip] {org_folder}: Folder does not exist.\n")
                continue

            print(f"[Country Sorter {country_code}] Now scanning: {org_folder}")
            file_counter = 0
            org_files = [item for item in os.listdir(org_path) if os.path.isfile(os.path.join(org_path, item))]

            if not org_files:
                print(f"[Skip: {org_folder}] No files found.\n")
                continue

            for file_name in org_files:
                if use_tracker and file_name in country_tracker.get(org_folder, []):
                    continue

                src_item = os.path.join(org_path, file_name)
                dest_item = os.path.join(sorted_country_base, country_code, org_folder, file_name)
                ensure_dir(os.path.dirname(dest_item))

                moved = await move_one_file(src_item, dest_item, asn, org_name, org_folder, country_code, writer)
                if moved:
                    file_counter += 1
                    print(f"[Country Sorter: {country_code}/{org_folder}] Files_processed: {file_counter} → {file_name}")

            if file_counter == 0:
                print(f"[Country Sorter: {org_folder}] Update → No new files moved.")
            else:
                print(f"[Country Sorter: {org_folder}] Update →  {file_counter} file(s) moved.\n")

    # === Save tracker if enabled
    if use_tracker:
        with open(country_tracker_path, "w") as tf:
            json.dump(country_tracker, tf, indent=2)

    print(f"\n[Country Sorter] ✅ Completed. Log saved to {country_log_path}\n", flush=True)

async def main_sort_country_code_only(use_tracker=False, country_tracker_mode="manual"):
    await sort_shadowserver_by_country(use_tracker=use_tracker, country_tracker_mode=country_tracker_mode)


async def sort_shadowserver_by_service(use_tracker=False, service_tracker_mode="manual"):
    print("\n[Service Sorter] Sorting shadowserver reports by service name using country map...")

    BATCH_SIZE = int(os.getenv("service_sorting_batch_size", "1000"))

    asn_map_dir = os.path.join("shadowserver_analysis_system", "detected_companies")
    sorted_base = os.path.join("shadowserver_analysis_system", "sorted_companies_by_country")
    tracker_dir = "file_tracking_system"

    country_map_csv = os.path.join(asn_map_dir, "asn_org_map.csv")
    service_tracker_path = os.path.join(tracker_dir, "service_sort_tracker.json")

    ensure_dir(sorted_base)

    if not os.path.exists(country_map_csv):
        print("[Service Sorter] Country map file not found. Skipping sorting.")
        return

    if service_tracker_mode == "auto":
        total_files = sum(
            len(files)
            for root, _, files in os.walk(sorted_base)
            if any(f.endswith(".csv") for f in files)
        )
        use_tracker = total_files > 3000

    if use_tracker and os.path.exists(service_tracker_path):
        with open(service_tracker_path, "r") as tf:
            service_tracker = json.load(tf)
    else:
        service_tracker = {}


    def validate_env_regex(key):
        """
        Validates that the regex pattern defined in the environment under `key`:
        - Compiles successfully
        - Has at least one capture group for .group(1) usage

        Logs warnings or errors accordingly.
        """
        pattern = os.getenv(key, "").strip('"')

        if not pattern:
            return  # Nothing to validate

        try:
            compiled = re.compile(pattern)
            if compiled.groups < 1:
                print(f"[Warning] Pattern '{key}' has no capture group — .group(1) will fail.")
        except re.error as e:
            print(f"[Error] Invalid regex in '{key}': {e}")

    # Validate standard and fallback regex patterns
    validate_env_regex("GEO_CSV_REGEX")
    validate_env_regex("geo_csv_fallback_regex")

    # Get the range value from .env
    anomaly_pattern_count = int(os.getenv("anomaly_pattern_count", "0"))

    # Loop based on that range
    for i in range(1, anomaly_pattern_count + 1):
        enabled_key = f"enable_anomaly_pattern_{i}"
        pattern_key = f"anomaly_pattern_{i}"

        enabled = os.getenv(enabled_key, "false").strip('"').lower() == "true"

        if enabled:
            validate_env_regex(pattern_key)
        else:
            print(f"[Info] Skipping {pattern_key} — disabled or not set.")


    @alru_cache(maxsize=1024)
    async def match_service_name(filename):
        original_filename = filename
        cleaned_filename = filename  # Might be updated after fallback cleanup

        # Step 1: Attempt fallback regex
        fallback_regex = os.getenv("geo_csv_fallback_regex", "").strip('"')
        if fallback_regex:
            try:
                fallback_match = re.match(fallback_regex, filename)
                if fallback_match:
                    print(f"[Service Sorter] Fallback pattern matched: {filename}")
                    reporting_code_match = re.search(r"-\d{3}", filename)
                    if reporting_code_match:
                        reporting_code = reporting_code_match.group(0)
                        print(f"[Service Sorter] Reporting code detected: {reporting_code}")
                        cleaned_filename = filename.replace(reporting_code, "")
                        print(f"[Service Sorter] Cleaned filename after removing reporting code: {cleaned_filename}")
                    else:
                        print(f"[Service Sorter] No reporting code found, using fallback-matched filename as-is.")
                else:
                    print(f"[Service Sorter] Fallback regex did not match — skipping reporting code cleanup: {filename}")
            except re.error as e:
                print(f"[Service Sorter] Invalid fallback regex: {e}")
        else:
            print("[Service Sorter] No fallback regex defined.")

        # Step 2: Attempt standard GEO regex on cleaned filename
        geo_csv_regex = os.getenv("geo_csv_regex", "").strip('"')
        if geo_csv_regex:
            try:
                geo_match = re.match(geo_csv_regex, cleaned_filename)
                if geo_match:
                    print(f"[Service Sorter] Matched standard GEO format: {cleaned_filename}")
                    return {
                        "pattern_type": "geo",
                        "pattern_id": 0,
                        "service_name": geo_match.group(1),
                        "match_obj": geo_match,
                        "cleaned_filename": cleaned_filename
                    }
                else:
                    print(f"[Service Sorter] GEO regex did not match: {cleaned_filename}")
            except re.error as e:
                print(f"[Service Sorter] Invalid geo_csv_regex: {e}")
        else:
            print("[Service Sorter] No standard geo regex defined.")

        # Step 3: Try anomaly patterns
        i = 1
        while True:
            enable_key = f"enable_anomaly_pattern_{i}"
            pattern_key = f"anomaly_pattern_{i}"

            if enable_key not in os.environ and pattern_key not in os.environ:
                break

            enabled = os.getenv(enable_key, "false").lower() == "true"
            pattern = os.getenv(pattern_key, "").strip('"')

            if enabled and pattern:
                try:
                    print(f"[Service Sorter] Trying anomaly pattern {i}: {pattern}")
                    anomaly_match = re.match(pattern, cleaned_filename)
                    if anomaly_match:
                        print(f"[Service Sorter] Matched anomaly pattern {i}: {cleaned_filename}")
                        return {
                            "pattern_type": f"anomaly_{i}",
                            "pattern_id": i,
                            "service_name": anomaly_match.group(1) if anomaly_match.re.groups >= 1 else None,
                            "match_obj": anomaly_match,
                            "cleaned_filename": cleaned_filename
                        }
                except re.error as e:
                    print(f"[Service Sorter] Invalid regex in {pattern_key}: {e}")
            i += 1

        print(f"[Service Sorter] No known pattern matched: {original_filename}")
        return {
            "pattern_type": None,
            "pattern_id": -1,
            "service_name": None,
            "match_obj": None,
            "cleaned_filename": original_filename
        }













    try:
        df = pd.read_csv(country_map_csv, dtype=str)
        service_totals = {}
        folder_totals = {}

        timestamp_now = datetime.now().strftime("%Y-%m-%d_%H%M")
        log_folder = os.path.join("logging", "shadowserver_sorting")
        ensure_dir(log_folder)
        movement_log_path = os.path.join(log_folder, f"sort_log_{timestamp_now}.csv")

        move_tasks = []

        async def move_one(src, dest, file, service, country, org, writer, task_id):
            try:
                if not os.path.exists(dest):
                    shutil.move(src, dest)
                    log_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    writer.writerow([log_time, country, org, service, file, dest])
                    if use_tracker:
                        service_tracker.setdefault(org, []).append(file)
                    return True
                else:
                    return False
            except Exception as e:
                print(f"🚨 [Error Move[{task_id}]] {file}: {e}")
                return False

        with open(movement_log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "country_code", "org_folder", "service_name", "original_filename", "destination_path"])

            for _, row in df.iterrows():
                country_code = str(row.get("country_code", "")).strip()
                org_folder = str(row.get("org_folder", "")).strip()

                if not country_code or not org_folder or country_code == "nan" or org_folder == "nan":
                    print(f"[Service Sorter] Skipping invalid row: {row.to_dict()}")
                    continue

                org_path = os.path.join(sorted_base, country_code, org_folder)

                if not os.path.isdir(org_path):
                    print(f"[Service Sorter] Skipping missing folder: {org_path}")
                    continue

                print(f"\n[Service Sorter ({country_code})] Now scanning: {org_folder}")
                file_counter = 0

                for file in os.listdir(org_path):
                    if use_tracker and file in service_tracker.get(org_folder, []):
                        continue

                    file_path = os.path.join(org_path, file)
                    if not os.path.isfile(file_path):
                        continue

                    result = await match_service_name(file)
                    if result["service_name"]:
                        service_name = result["service_name"]
                        clean_name = result["cleaned_filename"]

                        service_folder = os.path.join(org_path, service_name)
                        ensure_dir(service_folder)

                        dest_path = os.path.join(service_folder, file)

                        task_success = await move_one(
                            src=file_path,
                            dest=dest_path,
                            file=file,
                            service=service_name,
                            country=country_code,
                            org=org_folder,
                            writer=writer,
                            task_id=file_counter + 1
                        )

                        if task_success:
                            file_counter += 1
                            print(f"[Service Sorter: {country_code}/{org_folder}] Files_processed {file_counter}: {service_name} → {file}")
                            service_totals[service_name] = service_totals.get(service_name, 0) + 1
                            folder_totals[org_folder] = folder_totals.get(org_folder, 0) + 1

        if use_tracker:
            with open(service_tracker_path, "w") as tf:
                json.dump(service_tracker, tf, indent=2)

        print(f"\n[Service Sorter] ✅ Completed sorting.\n")

        print("\n[Service Sorter] Per-organization folder summary:")
        for folder, count in folder_totals.items():
            print(f"  - {folder}: {count} file(s) sorted.")

        print("\n[Service Sorter] Per-service breakdown:")
        for service, count in sorted(service_totals.items()):
            print(f"  - {service}: {count} file(s)")

    except Exception as e:
        print(f"[Service Sorter][ERROR] Failed to sort: {e}")
        

async def main_sort_service_only(use_tracker=False, service_tracker_mode="manual"):
    await sort_shadowserver_by_service(use_tracker=use_tracker, service_tracker_mode=service_tracker_mode)

                        

async def shadowserver_knowledgebase_ingestion_only(use_tracker=False, tracker_mode="manual"):
    mongo_client = MongoClient(
        mongo_host, mongo_port,
        username=mongo_username,
        password=mongo_password,
        authSource=mongo_auth_source
    )

    total_file_counter = 0
    completed_categories = []

    # Load ASN map
    asn_df = pd.read_csv(asn_map_path, dtype=str)

    for _, row in asn_df.iterrows():
        org_folder = row["org_folder"]
        asn = row["asn"]
        country_code = row["country_code"]
        org_path = os.path.join(root_directory, country_code, org_folder)

        if not os.path.isdir(org_path):
            continue

        db = await get_dynamic_database(org_folder, asn, mongo_client)

        for category in os.listdir(org_path):
            category_path = os.path.join(org_path, category)
            if not os.path.isdir(category_path):
                continue

            db_collection, discovered_fields_collection, files_collection = await create_database_and_collections(category, db)
            total_files = await count_total_files(category_path)

            # ✅ Pass use_tracker and tracker_mode into ingestion
            file_counter = await main_shadowserver_knowledgebase_ingestion(
                category_path,
                category,
                country_code,
                db_collection,
                discovered_fields_collection,
                files_collection,
                total_files,
                org_folder,
                use_tracker=use_tracker,
                tracker_mode=tracker_mode
            )

            total_file_counter += file_counter
            completed_categories.append(f"{country_code}/{org_folder}/{category}")
            print(f"\n[Knowledgebase] Completed: {country_code}/{org_folder}/{category} → {file_counter}/{total_files} files.", end="\n", flush=True)

            del db_collection, discovered_fields_collection, files_collection
            gc.collect()

    print(f"\n✅ [Knowledgebase] Total files processed: {total_file_counter}")
    print("✅ Completed categories:", completed_categories)

    mongo_client.close()







async def main_shadowserver_knowledgebase_ingestion(
    directory,
    category,
    country_code,
    db_collection,
    discovered_fields_collection,
    files_collection,
    total_files,
    org_folder,
    use_tracker=False,
    tracker_mode="manual"  # NEW: manual or auto
):
    file_counter = 0
    batch_counter = 0

    # === Determine final tracker behavior ===
    if tracker_mode == "auto":
        use_tracker = total_files > 2000

    if use_tracker:
        tracker_dir = "file_tracking_system"
        knowledgebase_tracker_dir = "knowledgebase_tracker"
        ensure_dir(os.path.join(tracker_dir, knowledgebase_tracker_dir))
        processed_tracker_path = os.path.join(tracker_dir, knowledgebase_tracker_dir, f"processed_files_{category}.json")
        processed_files = load_tracker(processed_tracker_path)
    else:
        processed_tracker_path = None
        processed_files = set()

    # === Walk all files ===
    files_list = []
    for root, _, files in os.walk(directory):
        for filename in files:
            file_path = os.path.join(root, filename)
            files_list.append(file_path)

    FILE_BATCH_SIZE = int(os.getenv("number_of_files_ingested_into_knowledgebase_per_batch", "2000"))
    total_files_found = len(files_list)

    for batch_start in range(0, total_files_found, FILE_BATCH_SIZE):
        batch_files = files_list[batch_start:batch_start + FILE_BATCH_SIZE]
        batch_counter += 1
        bulk_operations = []

        for file_path in batch_files:
            filename = os.path.basename(file_path)

            if filename in processed_files:
                print(f"[Tracker] SKIP {filename}", end="\r", flush=True)
                continue

            if files_collection.find_one({"filename": filename, "category": category, "ingested": True}):
                processed_files.add(filename)
                continue

            lines_to_hash = set()
            existing_hashes = set(
                doc["line_hash"]
                for doc in db_collection.find({"filename": filename, "category": category}, {"line_hash": 1})
            )

            file_successfully_ingested = True

            try:
                if filename.endswith(".csv"):
                    async with aiofiles.open(file_path, "r", encoding="utf-8", buffering=8192) as f:
                        content = await f.read()
                        lines = content.splitlines()

                        if not lines:
                            continue

                        headers = [h.strip() for h in next(csv.reader(io.StringIO(lines[0])))]

                        for line in lines[1:]:
                            if not line.strip():
                                continue

                            reader = csv.reader(io.StringIO(line))
                            fields = next(reader)

                            if not fields or len(fields) != len(headers):
                                continue

                            row = dict(zip(headers, fields))
                            line_hash = await hash_line(row)

                            if line_hash in existing_hashes or line_hash in lines_to_hash:
                                continue

                            row = {k: (v.strip().lower() if isinstance(v, str) else v) for k, v in row.items()}
                            row.update({
                                "filename": filename,
                                "category": category,
                                "line_hash": line_hash,
                                "geo_folder": country_code
                            })

                            timestamp_str = row.get("timestamp")
                            if timestamp_str:
                                try:
                                    date_entry = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                                    row.setdefault("logged_date", date_entry.strftime("%Y-%m-%d %H:%M:%S"))
                                    row["extracted_date"] = date_entry
                                except ValueError:
                                    pass

                            bulk_operations.append(InsertOne(row))
                            lines_to_hash.add(line_hash)
                            del row

                elif filename.endswith(".json"):
                    async with aiofiles.open(file_path, 'r', encoding="utf-8", buffering=1) as jsonfile:
                        try:
                            json_data = await jsonfile.read()
                            json_object = json.loads(json_data)

                            line_hash = await hash_line(json_object)

                            if line_hash not in existing_hashes:
                                json_object = {k: (v.strip().lower() if isinstance(v, str) else v) for k, v in json_object.items()}
                                json_object.update({
                                    "filename": filename,
                                    "category": category,
                                    "line_hash": line_hash,
                                    "geo_folder": country_code
                                })

                                timestamp_str = json_object.get("timestamp")
                                if timestamp_str:
                                    try:
                                        date_entry = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                                        json_object.setdefault("logged_date", date_entry.strftime("%Y-%m-%d %H:%M:%S"))
                                        json_object["extracted_date"] = date_entry
                                    except ValueError:
                                        pass

                                bulk_operations.append(InsertOne(json_object))

                        except Exception as e:
                            print(f"❌ JSON parse error in {filename}: {e}")
                            file_successfully_ingested = False
                        finally:
                            del json_data
                            del json_object
                            gc.collect()

                else:
                    print(f"⚪ Unknown file type: {filename}")
                    continue

            except Exception as e:
                print(f"❌ Error ingesting file {filename}: {e}")
                file_successfully_ingested = False

            if file_successfully_ingested:
                print(f"[Summary ({org_folder}  → {category}) ] {filename} → Inserted: {len(lines_to_hash)}")
                files_collection.update_one(
                    {"filename": filename, "category": category},
                    {"$set": {"ingested": True, "path": file_path}},
                    upsert=True
                )
                processed_files.add(filename)
                file_counter += 1

                if use_tracker and processed_tracker_path:
                    save_tracker(processed_tracker_path, processed_files)

        if bulk_operations:
            await flush_bulk_operations(db_collection, bulk_operations)

        print(f"[Knowledgebase ({org_folder})] Category: {category}, Files processed: {file_counter}/{total_files} (Batch {batch_counter})", end="\r", flush=True)

    if use_tracker and processed_tracker_path:
        save_tracker(processed_tracker_path, processed_files)

    return file_counter






async def flush_bulk_operations(collection, operations):
    if not operations:
        return 0
    try:
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: collection.bulk_write(operations, ordered=False)
        )
        return 0  # No Mongo duplicates detected at insert time
    except BulkWriteError as bwe:
        skipped = len(bwe.details.get('writeErrors', []))
        print(f"[BulkWriteError] Skipped {skipped} duplicates during batch insert.")
        return skipped
    finally:
        operations.clear()








# ========== MAIN TASKS ==========

async def main_email_ingestion_only():
    await main_email_ingestion()

async def main_refresh_shadowserver_whois_only():
    await main_refresh_shadowserver_whois()

async def main_shadowserver_processing_only():
    await main_shadowserver_processing()

async def main_sort_country_code_only(use_tracker=False, country_tracker_mode="manual"):
    print(f"🌍 [Country Task] Tracker is {'ENABLED' if use_tracker else 'DISABLED'} ({country_tracker_mode.upper()} mode)")
    await sort_shadowserver_by_country(use_tracker=use_tracker, country_tracker_mode=country_tracker_mode)

async def main_sort_service_only(use_tracker=False, service_tracker_mode="manual"):
    print(f"📂 [Service Task] Tracker is {'ENABLED' if use_tracker else 'DISABLED'} ({service_tracker_mode.upper()} mode)")
    await sort_shadowserver_by_service(use_tracker=use_tracker, service_tracker_mode=service_tracker_mode)

async def main_knowledgebase_ingestion_only(use_tracker=False, tracker_mode="manual"):
    print(f"🧠 [Knowledgebase Task] Tracker is {'ENABLED' if use_tracker else 'DISABLED'} ({tracker_mode.upper()} mode)")
    await shadowserver_knowledgebase_ingestion_only(use_tracker=use_tracker, tracker_mode=tracker_mode)

async def main_attachment_sorting_migration_only():
    await attachment_sorting_shadowserver_report_migration()

# ========== MAIN SELECTOR ==========

async def main():


    if len(sys.argv) < 2:
        print("Usage: python3 shadow_server_data_analysis_system_builder_and_updater.py [email|migrate|refresh|process|country|service|ingest|all] [--tracker] [--tracker=auto] [--tracker-service=auto|manual|off] [--tracker-ingest=auto|manual|off]")
        sys.exit(1)

    tasks = [arg.lower() for arg in sys.argv[1:] if not arg.startswith("--")]
    flags = [arg.lower() for arg in sys.argv[1:] if arg.startswith("--")]
    force_reset_email = "--reset-email-method" in flags

    # === Global tracker override ===
    global_tracker_enabled = False
    global_tracker_mode = "manual"

    if "--tracker" in flags:
        global_tracker_enabled = True
        global_tracker_mode = "manual"
    elif "--tracker=auto" in flags:
        global_tracker_enabled = True
        global_tracker_mode = "auto"

    # === Task-specific tracker flags ===
    def parse_tracker_flag(flag_list, key):
        match = next((f for f in flag_list if f.startswith(f"--tracker-{key}=")), None)
        if match:
            value = match.split("=")[1]
            if value == "off":
                return False, "manual"
            elif value == "manual":
                return True, "manual"
            elif value == "auto":
                return True, "auto"
        return global_tracker_enabled, global_tracker_mode

    service_use_tracker, service_tracker_mode = parse_tracker_flag(flags, "service")
    ingest_use_tracker, ingest_tracker_mode = parse_tracker_flag(flags, "ingest")
    country_use_tracker, country_tracker_mode = parse_tracker_flag(flags, "country")

    # === Task Descriptions ===
    print("\n🛠️  Selected Tasks:")
    for task in tasks:
        if task == "email":
            print("• email   → Pull Emails Including Shadowserver Reports, Save As EML and Extract Attachments")
        elif task == "refresh":
            print("• refresh → Refresh Stored ASN/WHOIS Metadata from Previous Shadowserver Reports")
        elif task == "process":
            print("• process → Parse and Normalize Shadowserver CSV/JSON files")
        elif task == "migrate":
            print("• migrate → Sort Attachments, Extract Archives, and Relocate Shadowserver Reports and Advisories From Downloaded Attachment Directory")
        elif task == "country":
            print("• country → Sort Processed Shadowserver Reports by Country Code")
        elif task == "service":
            print("• service → Sort Processed Shadowserver Reports by Detected Service Type via Filename Pattern Analysis")
        elif task == "ingest":
            print("• ingest  → Ingest Cleaned Shadowserver Data into Knowledgebase as Databases and Collections")
        elif task == "all":
            print("• all     → Run All Tasks Sequentially (email, refresh, migrate, country, service, ingest)")
        else:
            print(f"❌ Unknown task '{task}' — valid options are: email, refresh, migrate, country, service, ingest, all")
            sys.exit(1)

    # === Tracker Configuration Summary ===
    print("\n📦 Tracker Configuration:")
    print(f"• service  → {'ENABLED' if service_use_tracker else 'DISABLED'} ({service_tracker_mode.upper()} mode)")
    print(f"• ingest   → {'ENABLED' if ingest_use_tracker else 'DISABLED'} ({ingest_tracker_mode.upper()} mode)")
    print(f"• country  → {'ENABLED' if country_use_tracker else 'DISABLED'} ({country_tracker_mode.upper()} mode)\n")

    # === Email Source Selection (for both 'email' and 'all') ===
    async def handle_email_ingestion(force_reset=False):
        selected = None

        if not force_reset:
            selected = load_last_choice(force_reset=force_reset)

        if not selected:
            print("\n📥 Select email ingestion method:")
            print("1. IMAP (e.g., Shadowserver inbox)")
            print("2. Microsoft Graph (Microsoft 365)")
            print("3. Google Workspace (Gmail API)")
            selected = input("Enter option [1-3]: ").strip()

            if selected in {"1", "2", "3"}:
                save_last_choice(selected)
            else:
                print("❌ Invalid option. Skipping email task.")
                return

        if selected == "1":
            await main_email_ingestion_only()
        elif selected == "2":
            print("[TODO] Microsoft Graph ingestion not implemented yet.")
            await ingest_microsoft_graph()
        elif selected == "3":
            print("[TODO] Google Workspace ingestion not implemented yet.")
            await ingest_google_workspace()
    
        # === Execute all tasks ===
    if "all" in tasks:
        await handle_email_ingestion(force_reset=force_reset_email)
        await main_attachment_sorting_migration_only()
        await main_refresh_shadowserver_whois_only()
        await main_shadowserver_processing_only()
        await main_sort_country_code_only(use_tracker=country_use_tracker, country_tracker_mode=country_tracker_mode)
        await main_sort_service_only(use_tracker=service_use_tracker, service_tracker_mode=service_tracker_mode)
        await main_knowledgebase_ingestion_only(use_tracker=ingest_use_tracker, tracker_mode=ingest_tracker_mode)
        return

    # === Execute selected tasks ===
    for task in tasks:
        if task == "email":
            await handle_email_ingestion(force_reset=force_reset_email)
        elif task == "migrate":
            await main_attachment_sorting_migration_only()
        elif task == "refresh":
            await main_refresh_shadowserver_whois_only()
        elif task == "process":
            await main_shadowserver_processing_only()
        elif task == "country":
            await main_sort_country_code_only(use_tracker=country_use_tracker, country_tracker_mode=country_tracker_mode)
        elif task == "service":
            await main_sort_service_only(use_tracker=service_use_tracker, service_tracker_mode=service_tracker_mode)
        elif task == "ingest":
            await main_knowledgebase_ingestion_only(use_tracker=ingest_use_tracker, tracker_mode=ingest_tracker_mode)


if __name__ == "__main__":
    asyncio.run(main())





