import os
import csv
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv()

username = os.getenv("mongo_username")
password = os.getenv("mongo_password")
auth_source = os.getenv("mongo_auth_source", "admin")
host = os.getenv("mongo_host", "127.0.0.1")
port = int(os.getenv("mongo_port", 27017))

# MongoDB URI
uri = f"mongodb://{username}:{password}@{host}:{port}/?authSource={auth_source}"

# Setup log folder
log_folder = os.path.join("logging", "db_deletion_logs")
os.makedirs(log_folder, exist_ok=True)

# Timestamped CSV log path
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
csv_log_path = os.path.join(log_folder, f"deleted_dbs_{timestamp}.csv")

# Connect to MongoDB
client = MongoClient(uri)
all_dbs = client.list_database_names()

# Filter DBs containing "_as"
dbs_to_delete = [db for db in all_dbs if "_as" in db]

# Step 1: Dry run display
print("=== DRY RUN ===")
print("The following databases contain '_as' and are candidates for deletion:")
for db in dbs_to_delete:
    print(f"- {db}")

# Step 2: Ask for confirmation
if dbs_to_delete:
    choice = input("\nDo you want to proceed with deleting these databases? (yes/no): ").strip().lower()
    if choice in ['yes', 'y']:
        print("\n=== DELETION STARTED ===")
        with open(csv_log_path, mode="w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["database_name", "deleted_at"])
            for db in dbs_to_delete:
                print(f"Dropping: {db}")
                client.drop_database(db)
                deleted_at = datetime.now().isoformat()
                writer.writerow([db, deleted_at])
        print(f"=== DONE. Log saved to: {csv_log_path} ===")
    else:
        print("\nNo action taken. Deletion canceled.")
else:
    print("\nNo matching databases found.")
