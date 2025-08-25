#!/bin/bash
set -e

echo "⚠️  This will completely uninstall Shadow Command Center (both standard and minimised versions)."
read -rp "Are you sure you want to proceed? (y/N): " confirm

if [[ "$confirm" =~ ^[Yy]$ ]]; then
    echo "🗑️  Removing Shadow Command Center..."

    # Remove desktop entries
    rm -f ~/.local/share/applications/shadow_command_center.desktop
    rm -f ~/.local/share/applications/shadow_command_center_minimised.desktop

    # Remove icons
    rm -f ~/.local/share/icons/shadow_command_center.png
    rm -f ~/.local/share/icons/shadow_command_center_minimised.png

    # Remove binaries
    sudo rm -f /usr/bin/shadow_command_center
    sudo rm -f /usr/bin/shadow_command_center_minimised

    # Update desktop DB if available
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database "$HOME/.local/share/applications" || true
    fi

    echo "✅ Uninstallation complete."
else
    echo "❌ Uninstallation cancelled."
fi
