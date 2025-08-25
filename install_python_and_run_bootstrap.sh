#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Which GUI(s) would you like to install?"
echo "1) Standard GUI (ingestion_gui.py)"
echo "2) Option B GUI (ingestion_gui_option_b.py)"
echo "3) Both"
read -rp "Enter choice [1-3]: " choice

install_gui() {
    local py_script="$1"
    local bin_name="$2"
    local desktop_name="$3"
    local desktop_file="$HOME/.local/share/applications/${bin_name}.desktop"
    local icon_source="$SCRIPT_DIR/logo.png"
    local icon_dest="$HOME/.local/share/icons/${bin_name}.png"

    if [ ! -f "$SCRIPT_DIR/$py_script" ]; then
        echo "❌ $py_script not found in $SCRIPT_DIR"
        return 1
    fi

    # Step 1: Create temporary C launcher
    LAUNCHER_C=$(mktemp)
    echo "📝 Writing C launcher for $py_script ($bin_name)..."

    cat > "$LAUNCHER_C" <<EOF
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char** argv) {
    if (chdir("${SCRIPT_DIR}") != 0) {
        perror("❌ Failed to change directory to script dir");
        return 1;
    }
    char command[2048] = "python3 \\"$py_script\\"";
    for (int i = 1; i < argc; i++) {
        strcat(command, " ");
        strcat(command, argv[i]);
    }
    return system(command);
}
EOF

    # Step 2: Compile launcher
    echo "🛠️  Compiling $bin_name..."
    gcc -x c "$LAUNCHER_C" -o "$bin_name"
    rm "$LAUNCHER_C"

    # Step 3: Install binary
    echo "🔐 Installing binary to /usr/bin/$bin_name (requires sudo)"
    sudo mv "$bin_name" "/usr/bin/$bin_name"
    sudo chmod +x "/usr/bin/$bin_name"

    echo "✅ Installed $bin_name. You can now run: $bin_name"

    # Step 4: Desktop entry
    echo "📁 Creating desktop entry at: $desktop_file"
    mkdir -p "$(dirname "$desktop_file")"

    # Copy icon if available
    if [ -f "$icon_source" ]; then
        echo "🖼️  Installing icon..."
        mkdir -p "$(dirname "$icon_dest")"
        cp "$icon_source" "$icon_dest"
    else
        echo "⚠️  No icon found at $icon_source — using default application icon."
    fi

    # Write .desktop file
    cat > "$desktop_file" <<EOF
[Desktop Entry]
Name=$desktop_name
Exec=$bin_name
Icon=${bin_name}
Terminal=false
Type=Application
Categories=Utility;
StartupNotify=true
EOF

    chmod +x "$desktop_file"

    # Update desktop DB if available
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database "$HOME/.local/share/applications" || true
    fi

    echo "✅ Desktop entry installed: $desktop_name"
}

# Handle installation choice
case $choice in
    1)
        install_gui "ingestion_gui.py" "shadow_command_center" "Shadow Command Center"
        ;;
    2)
        install_gui "ingestion_gui_option_b.py" "shadow_command_center_minimised" "Shadow Command Center (Minimised)"
        ;;
    3)
        install_gui "ingestion_gui.py" "shadow_command_center" "Shadow Command Center"
        install_gui "ingestion_gui_option_b.py" "shadow_command_center_minimised" "Shadow Command Center (Minimised)"
        ;;
    *)
        echo "❌ Invalid choice"
        exit 1
        ;;
esac

# Dependency checks
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

# Final bootstrap
echo "🚀 Running Python bootstrap script..."
python3 "$SCRIPT_DIR/bootstrap_shadowserver_environment.py"

echo "🎉 Installation complete!"
