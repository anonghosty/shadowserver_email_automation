---
title: Installation & Environment Bootstrapping
---
# 🧱 Installation & Environment Bootstrapping

This section covers how to prepare your system to run the **Shadowserver Report Ingestion & Intelligence Toolkit**, including OS packages, Python libraries, Chrome setup, and first-time bootstrap commands.

---

## 📦 Prerequisites

This toolkit is designed for **Linux (Ubuntu/Debian)** systems and requires the following:

- Python 3.x
- pip (Python package manager)
- MongoDB (local or remote instance)
- Google Chrome (for headless scraping)
- IMAP-accessible email inbox

> ⚠️ If using Windows or macOS, consider using WSL (Windows Subsystem for Linux) or a virtual machine.

---

## 🔧 One-Line Installation (Recommended)

To automatically install Python, pip, Chrome, MongoDB dependencies, and all required packages:

```bash
chmod +x install_python_and_run_bootstrap.sh
./install_python_and_run_bootstrap.sh


# 🛠️ Local MongoDB Installation Guide (Ubuntu 24.04)

This guide provides a hardened installation of MongoDB 8.0 on Ubuntu 24.04, including system tuning, authentication setup, and administrative best practices.

---

## ✅ Prerequisites

- Ubuntu **24.04 LTS** server
- A **non-root user** with `sudo` privileges

---

## ⚙️ System Preparation

Before installing MongoDB, configure the system to improve performance and compatibility.

### 1. 🔒 Disable Transparent Huge Pages (THP)

Create a systemd unit to disable THP on boot:

```bash
sudo nano /etc/systemd/system/disable-thp.service
```

Paste:

```ini
[Unit]
Description=Disable Transparent Huge Pages (THP)

[Service]
Type=simple
ExecStart=/bin/sh -c "echo 'never' > /sys/kernel/mm/transparent_hugepage/enabled && echo 'never' > /sys/kernel/mm/transparent_hugepage/defrag"

[Install]
WantedBy=multi-user.target
```

Then apply and enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now disable-thp.service
```

---

### 2. 📈 Increase `ulimit` for `mongod` user

Create limits config:

```bash
sudo nano /etc/security/limits.d/mongodb.conf
```

Insert:

```
mongod soft nproc 64000
mongod hard nproc 64000
mongod soft nofile 64000
mongod hard nofile 64000
```

---

### 3. 🧬 Tune Kernel Parameters

Edit system-wide settings:

```bash
sudo nano /etc/sysctl.conf
```

Add at the bottom:

```bash
fs.file-max = 2097152
vm.max_map_count = 262144
vm.swappiness = 1
```

Apply without reboot:

```bash
sudo sysctl -p
```

---

## 📦 Installing MongoDB 8.0 (APT Method)

### 1. Add GPG Key and Repository

Install GPG and curl:

```bash
sudo apt update && sudo apt install -y gnupg curl
```

Add MongoDB 8 key:

```bash
curl -fsSL https://www.mongodb.org/static/pgp/server-8.0.asc | \
sudo gpg -o /usr/share/keyrings/mongodb-server-8.0.gpg --dearmor
```

Add repository (Ubuntu 24.04 = `noble`):

```bash
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-8.0.gpg ] https://repo.mongodb.org/apt/ubuntu noble/mongodb-org/8.0 multiverse" | \
sudo tee /etc/apt/sources.list.d/mongodb-org-8.0.list
```

---

### 2. Install MongoDB

```bash
sudo apt update
sudo apt install -y mongodb-org
```

---

### 3. Start and Enable MongoDB

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mongod
sudo systemctl status mongod
```

---

## 🔐 Securing MongoDB

### 1. Create MongoDB Admin User

Start the shell:

```bash
mongosh
```

Disable telemetry (optional):

```js
disableTelemetry()
```

Switch to `admin` database:

```js
use admin
```

Create admin user:
Change 'myAdmin' to your desired admin name
```js
db.createUser({
  user: "myAdmin",
  pwd: passwordPrompt(),
  roles: [
    { role: "userAdminAnyDatabase", db: "admin" },
    { role: "readWriteAnyDatabase", db: "admin" }
  ]
})
```

Exit:

```js
quit()
```

---

### 2. Enable MongoDB Authentication

Edit the config:

```bash
sudo nano /etc/mongod.conf
```

Add or modify:

```yaml
security:
  authorization: enabled
```

Restart MongoDB:

```bash
sudo systemctl restart mongod
```

---

### 3. Test Authentication

Login using the admin user:

```bash
mongosh --port 27017 --authenticationDatabase "admin" -u "myAdmin" -p
```

After logging in:

```js
db.runCommand({ connectionStatus: 1 })
quit()
```

If `ok: 1` is returned, the setup is complete.

---

## 🧪 Test Integration With the Toolkit

Ensure `.env` is correctly configured:

```dotenv
mongo_username="myAdmin"
mongo_password="your_password_here"
mongo_auth_source="admin"
mongo_host="127.0.0.1"
mongo_port=27017
```

Then test:

```bash
python3 shadow_server_data_analysis_system_builder_and_updater.py refresh
```

---

## ✅ Summary

| Task                            | Status  |
|---------------------------------|---------|
| Transparent Huge Pages disabled | ✅      |
| `ulimit` & sysctl tuned         | ✅      |
| MongoDB 8.0 installed           | ✅      |
| Admin user created              | ✅      |
| Authentication enabled          | ✅      |
| Tested login/auth               | ✅      |

> For production, consider firewalling port 27017 and enabling TLS.

---

### 📚 Official Installation Guides

- **HowToForge Tutorial:**  
  [https://www.howtoforge.com/tutorial/install-mongodb-on-ubuntu/](https://www.howtoforge.com/tutorial/install-mongodb-on-ubuntu/)

- **MongoDB Documentation (Official for the latest release):**  
  [https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-ubuntu/](https://www.mongodb.com/docs/manual/tutorial/install-mongodb-on-ubuntu/)

These guides walk through version-specific setup across various Ubuntu distributions.

