import os
import re
import csv
from datetime import datetime, timedelta
from pymongo import MongoClient
from dotenv import load_dotenv
from tqdm import tqdm

# -----------------------------------
# Load environment variables
# -----------------------------------
load_dotenv()

mongo_username = os.getenv("mongo_username")
mongo_password = os.getenv("mongo_password")
mongo_auth_source = os.getenv("mongo_auth_source", "admin")
mongo_host = os.getenv("mongo_host", "127.0.0.1")
mongo_port = int(os.getenv("mongo_port", 27017))

# -----------------------------------
# MongoDB connection
# -----------------------------------
mongo_uri = (
    f"mongodb://{mongo_username}:{mongo_password}"
    f"@{mongo_host}:{mongo_port}/"
    f"?authSource={mongo_auth_source}"
)

client = MongoClient(mongo_uri)

# -----------------------------------
# Date boundaries (UTC)
# -----------------------------------
today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
yesterday = today - timedelta(days=1)
date_str = yesterday.strftime("%Y-%m-%d")

# -----------------------------------
# Output base directory
# -----------------------------------
BASE_OUTPUT_DIR = "db_counts"
os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)

# -----------------------------------
# Match databases ending with _asXXXX
# -----------------------------------
db_pattern = re.compile(r"_as\d+$")

db_names = sorted(
    db for db in client.list_database_names()
    if db_pattern.search(db)
)

# -----------------------------------
# Scan databases with progress bars
# -----------------------------------
for db_name in tqdm(db_names, desc="Scanning databases", unit="db"):
    db = client[db_name]
    collections = db.list_collection_names()

    rows = []

    for col_name in tqdm(
        collections,
        desc=f"  {db_name}",
        unit="col",
        leave=False
    ):
        col = db[col_name]

        count = col.count_documents({
            "extracted_date": {
                "$gte": yesterday,
                "$lt": today
            }
        })

        if count > 0:
            rows.append([
                db_name,
                col_name,
                date_str,
                count
            ])

    # -----------------------------------
    # Write CSV per DB
    # -----------------------------------
    if rows:
        db_output_dir = os.path.join(BASE_OUTPUT_DIR, db_name)
        os.makedirs(db_output_dir, exist_ok=True)

        csv_path = os.path.join(
            db_output_dir,
            f"{db_name}_{date_str}.csv"
        )

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "database_name",
                "collection_name",
                "date",
                "document_count"
            ])
            writer.writerows(rows)

        # Tree-style console output
        print(f"\n{db_name}")
        for i, (_, col_name, _, count) in enumerate(rows):
            prefix = "└──" if i == len(rows) - 1 else "├──"
            print(f"{prefix} {col_name:<35} [{count}]")
