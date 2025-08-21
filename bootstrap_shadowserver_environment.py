import os
import sys
import subprocess
import shutil
import zipfile
import requests
from pathlib import Path

# === Step 0: Ensure APT packages ===
print("📦 Installing system-level APT packages (requires sudo)...")
apt_packages = [
    "unzip",
    "zip",
    "p7zip-full",
    "p7zip-rar",
    "unrar",
    "libnss3",
    "libxss1",
    "libappindicator3-1",
    "fonts-liberation",
    "whois",
    "wget",
    "ca-certificates",
    "gnupg",
    "python3-tk",
    "lsb-release",
]

try:
    subprocess.run(["sudo", "apt", "update"], check=True)
    subprocess.run(["sudo", "apt", "install", "-y"] + apt_packages, check=True)
except subprocess.CalledProcessError as e:
    print(f"❌ Failed to install APT packages: {e}")
    sys.exit(1)

# === Step 1: Install Python packages from requirements.txt ===
print("🐍 Installing Python packages from requirements.txt...")
requirements_path = Path("requirements.txt")
if not requirements_path.exists():
    # fallback list
    print("⚠️ requirements.txt not found. Using inline fallback list.")
    requirements = [
        # Already present in your previous list
        "aiofiles",
        "customtkinter",
        "aiohttp",
        "async-lru",
        "beautifulsoup4",
        "bs4",
        "colorama",
        "pandas",
        "pymongo",
        "py7zr",
        "rarfile",
        "reportlab",
        "selenium",
        "tqdm",
        "msal",
        "dash",
        "python-dotenv",
        "geopandas",
        "pycountry",
        "matplotlib",
    ]
    subprocess.run([sys.executable, "-m", "pip", "install", "--break-system-packages"] + requirements, check=True)
else:
    subprocess.run([sys.executable, "-m", "pip", "install", "--break-system-packages", "-r", str(requirements_path)], check=True)


# === Step 2: Install or update Google Chrome ===
print("🌐 Checking Google Chrome installation...")
chrome_installed = shutil.which("google-chrome")
chrome_deb_url = "https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"
chrome_deb_path = "/tmp/google-chrome-stable_current_amd64.deb"

if chrome_installed:
    print("🔄 Google Chrome is already installed. Updating...")
else:
    print("📥 Google Chrome not found. Installing...")

try:
    subprocess.run(["wget", "-q", "-O", chrome_deb_path, chrome_deb_url], check=True)
    subprocess.run(["sudo", "apt", "install", "-y", chrome_deb_path], check=True)
finally:
    if os.path.exists(chrome_deb_path):
        os.remove(chrome_deb_path)

print("✅ Google Chrome setup complete.")

# === Step 3: Detect Chrome version ===
print("🧩 Detecting installed Google Chrome version...")
try:
    version_output = subprocess.check_output(["google-chrome", "--version"], text=True)
    chrome_version = version_output.strip().split()[-1]
    major_version = chrome_version.split('.')[0]
    print(f"   → Installed Chrome version: {chrome_version}")
except Exception as e:
    print(f"❌ Failed to determine Chrome version: {e}")
    sys.exit(1)

# === Step 4: Match ChromeDriver version ===
print("🌐 Fetching matching ChromeDriver version via Google JSON API...")
version_map_url = "https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json"
try:
    response = requests.get(version_map_url)
    response.raise_for_status()
except Exception as e:
    print(f"❌ Failed to fetch ChromeDriver version map: {e}")
    sys.exit(1)

version_map = response.json()
downloads = version_map.get("channels", {}).get("Stable", {}).get("downloads", {})
driver_version = version_map.get("channels", {}).get("Stable", {}).get("version", "")

linux_driver_url = ""
for entry in downloads.get("chromedriver", []):
    if entry["platform"] == "linux64":
        linux_driver_url = entry["url"]
        break

if not linux_driver_url:
    print("❌ Could not find ChromeDriver download URL for linux64.")
    sys.exit(1)

print(f"   → Matched ChromeDriver version: {driver_version}")
print(f"   → Downloading from: {linux_driver_url}")

# === Step 5: Download and install ChromeDriver ===
zip_path = "/tmp/chromedriver_linux64.zip"
install_path = "/usr/local/bin/chromedriver"

try:
    r = requests.get(linux_driver_url, stream=True)
    with open(zip_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)

    extract_dir = Path("/tmp/chromedriver_extract")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    extracted_driver = next(extract_dir.rglob("chromedriver"), None)

    if extracted_driver and extracted_driver.exists():
        subprocess.run(["sudo", "mv", str(extracted_driver), install_path])
        subprocess.run(["sudo", "chmod", "+x", install_path])
        print(f"✅ ChromeDriver installed to {install_path}")
    else:
        print("❌ ChromeDriver binary not found after extraction.")
        sys.exit(1)

finally:
    if os.path.exists(zip_path):
        os.remove(zip_path)
    shutil.rmtree("/tmp/chromedriver_extract", ignore_errors=True)


print("\n🎉 All dependencies are installed. Environment setup complete.")


