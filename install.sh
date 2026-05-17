#!/bin/bash
# Tek komutla kurulum — git veya GitHub hesabı gerekmez.
# Kullanım:
#   curl -fsSL https://raw.githubusercontent.com/different35/android_mix_list_-generate/main/install.sh | bash

set -e

INSTALL_DIR="$HOME/music-analyzer"
ZIP_URL="https://github.com/different35/android_mix_list_-generate/archive/refs/heads/main.zip"
TMP_ZIP="/tmp/mixliste_setup.zip"
TMP_DIR="/tmp/mixliste_setup"

echo "=== Mix Liste Oluşturucu ==="
echo ""

# Gerekli araçlar
pkg install -y curl unzip 2>/dev/null || true

# İndir
echo "İndiriliyor..."
curl -fsSL "$ZIP_URL" -o "$TMP_ZIP"

# Çıkart
rm -rf "$TMP_DIR"
unzip -q "$TMP_ZIP" -d "$TMP_DIR"
rm -f "$TMP_ZIP"

# Mevcut kurulum varsa yedekle
if [ -d "$INSTALL_DIR" ]; then
    BACKUP="${INSTALL_DIR}_yedek_$(date +%Y%m%d_%H%M%S)"
    mv "$INSTALL_DIR" "$BACKUP"
    echo "Eski kurulum yedeklendi: $BACKUP"
fi

# Yerleştir
mv "$TMP_DIR"/android_mix_list_-generate-* "$INSTALL_DIR"
rm -rf "$TMP_DIR"

chmod +x "$INSTALL_DIR/start.sh" \
         "$INSTALL_DIR/setup_termux.sh" \
         "$INSTALL_DIR/create_shortcut.sh"

# Kurulumu çalıştır
bash "$INSTALL_DIR/setup_termux.sh"
