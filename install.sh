cat << 'EOF' > install.sh
#!/bin/bash
set -e

INSTALL_DIR="$HOME/music-analyzer"
ZIP_URL="https://github.com/different35/android_mix_list_-generate/archive/refs/heads/main.zip"
TMP_ZIP="$HOME/mixliste_setup.zip"
TMP_DIR="$HOME/mixliste_setup_dir"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║     Mix Liste Oluşturucu Kurulum     ║"
echo "╚══════════════════════════════════════╝"
echo ""

echo "► Sistem paketleri güncelleniyor..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y

echo "► Gerekli araçlar yükleniyor..."
apt-get install -y python ffmpeg termux-api curl unzip

echo "► Python kütüphaneleri yükleniyor..."
apt-get install -y python-numpy python-scipy || pip install numpy scipy

echo "► Uygulama indiriliyor..."
curl -fsSL "$ZIP_URL" -o "$TMP_ZIP"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"
unzip -q "$TMP_ZIP" -d "$TMP_DIR"
rm -f "$TMP_ZIP"

if [ -d "$INSTALL_DIR" ]; then
    BACKUP="${INSTALL_DIR}_yedek_$(date +%Y%m%d_%H%M%S)"
    mv "$INSTALL_DIR" "$BACKUP"
fi

mv "$TMP_DIR"/android_mix_list_-generate-* "$INSTALL_DIR"
rm -rf "$TMP_DIR"
chmod +x "$INSTALL_DIR/start.sh"

# Önceki kurulumdan config/cache varsa geri taşı
if [ -n "${BACKUP:-}" ]; then
    if [ -f "$BACKUP/cache.db" ]; then
        cp "$BACKUP/cache.db" "$INSTALL_DIR/" 2>/dev/null || true
    fi
    if [ -d "$BACKUP/config" ]; then
        cp -r "$BACKUP/config" "$INSTALL_DIR/" 2>/dev/null || true
    fi
fi

if [ ! -e "$HOME/storage/shared" ] && command -v termux-setup-storage >/dev/null 2>&1; then
    echo "► Termux storage izni isteniyor..."
    termux-setup-storage
    sleep 1
fi

echo "► Ana ekran kısayolu oluşturuluyor..."
SHORTCUTS_DIR="$HOME/.shortcuts"
mkdir -p "$SHORTCUTS_DIR"
chmod 700 "$SHORTCUTS_DIR"

cat > "$SHORTCUTS_DIR/Mix Liste Oluştur" << 'INNER_EOF'
#!/bin/bash
bash "$INSTALL_DIR/start.sh"
INNER_EOF
chmod +x "$SHORTCUTS_DIR/Mix Liste Oluştur"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║         Kurulum tamamlandı!          ║"
echo "╚══════════════════════════════════════╝"
echo ""
EOF
bash install.sh
