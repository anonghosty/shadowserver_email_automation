#!/bin/bash

set -e

# Step 1: Get absolute path to ingestion_gui.py
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/ingestion_gui.py"

if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "❌ ingestion_gui.py not found in $SCRIPT_DIR"
    exit 1
fi

# Step 2: Create temporary C file
LAUNCHER_C=$(mktemp)

echo "📝 Writing C launcher to: $LAUNCHER_C"

# Write the C code to the file (embed the SCRIPT_DIR path)
cat > "$LAUNCHER_C" <<EOF
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char** argv) {
    // Change to the script directory
    if (chdir("${SCRIPT_DIR}") != 0) {
        perror("❌ Failed to change directory to script dir");
        return 1;
    }

    // Build the command string
    char command[2048] = "python3 \"ingestion_gui.py\"";
    for (int i = 1; i < argc; i++) {
        strcat(command, " ");
        strcat(command, argv[i]);
    }

    return system(command);
}
EOF

# ✅ DEBUG: Show the file contents before compiling
echo "🔍 C file contents:"
cat "$LAUNCHER_C"

# Step 3: Try compiling
echo "🛠️  Compiling..."
gcc -x c "$LAUNCHER_C" -o shadow_command_center

# Step 4: Clean up
rm "$LAUNCHER_C"

# Step 5: Move binary to /usr/bin
echo "🔐 Installing binary to /usr/bin/shadow_command_center (requires sudo)"
sudo mv shadow_command_center /usr/bin/shadow_command_center
sudo chmod +x /usr/bin/shadow_command_center

echo "✅ Binary installed. You can now run: shadow_command_center"

# Step 6: Create .desktop entry
DESKTOP_FILE="$HOME/.local/share/applications/shadow-command-center.desktop"
ICON_SOURCE="$SCRIPT_DIR/logo.png"   # Updated icon file to logo.png
ICON_DEST="$HOME/.local/share/icons/shadow-command-center.png"

echo "📁 Creating desktop entry at: $DESKTOP_FILE"
mkdir -p "$(dirname "$DESKTOP_FILE")"

# Copy icon if it exists
if [ -f "$ICON_SOURCE" ]; then
    echo "🖼️  Installing icon..."
    mkdir -p "$(dirname "$ICON_DEST")"
    cp "$ICON_SOURCE" "$ICON_DEST"
else
    echo "⚠️  No icon found at $ICON_SOURCE — using default application icon."
fi

# Write desktop entry
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=Shadow Command Center
Exec=shadow_command_center
Icon=shadow-command-center
Terminal=false
Type=Application
Categories=Utility;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"

# Optional: update application menu database (some desktops require it)
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database "$HOME/.local/share/applications" || true
fi

echo "✅ Desktop entry installed. You can now search for 'Shadow Command Center' in your app menu. Installation Processes Continue"

echo "🔍 Checking for Python 3..."
if ! command -v python3 &> /dev/null; then
  echo "📦 Installing python3..."
  sudo apt update
  sudo apt install -y python3
else
  echo "✅ python3 is already installed."
fi

echo "🔍 Checking for pip3..."
if ! command -v pip3 &> /dev/null; then
  echo "📦 Installing python3-pip..."
  sudo apt install -y python3-pip
else
  echo "✅ pip3 is already installed."
fi

echo "🚀 Running Python bootstrap script..."
python3 bootstrap_shadowserver_environment.py
