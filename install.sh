#!/bin/bash
# Mix Liste Oluşturucu — tam kurulum
# Kullanım: curl -fsSL https://raw.githubusercontent.com/different35/android_mix_list_-generate/main/install.sh | bash

set -e

INSTALL_DIR="$HOME/music-analyzer"
ZIP_URL="https://github.com/different35/android_mix_list_-generate/archive/refs/heads/main.zip"
TMP_ZIP="/tmp/mixliste_setup.zip"
TMP_DIR="/tmp/mixliste_setup"

echo ""
echo "╔══════════════════════════════════════╗"
echo "║     Mix Liste Oluşturucu Kurulum     ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── 1. Sistem paketleri ───────────────────────────────────────────────────────
echo "► Sistem paketleri kuruluyor..."
pkg update -y -q
pkg install -y -q curl unzip python python-pip clang libsndfile
echo "  ✓ Sistem paketleri hazır"
echo ""

# ── 2. Dosyaları indir ────────────────────────────────────────────────────────
echo "► Uygulama indiriliyor..."
curl -fsSL "$ZIP_URL" -o "$TMP_ZIP"
rm -rf "$TMP_DIR"
unzip -q "$TMP_ZIP" -d "$TMP_DIR"
rm -f "$TMP_ZIP"

if [ -d "$INSTALL_DIR" ]; then
    BACKUP="${INSTALL_DIR}_yedek_$(date +%Y%m%d_%H%M%S)"
    mv "$INSTALL_DIR" "$BACKUP"
    echo "  (Eski kurulum yedeklendi: $BACKUP)"
fi

mv "$TMP_DIR"/android_mix_list_-generate-* "$INSTALL_DIR"
rm -rf "$TMP_DIR"
chmod +x "$INSTALL_DIR/start.sh" "$INSTALL_DIR/create_shortcut.sh"
echo "  ✓ Dosyalar hazır"
echo ""

# ── 3. Python bağımlılıkları ──────────────────────────────────────────────────
echo "► Python kütüphaneleri kuruluyor (bu biraz sürebilir)..."
pip install -q -r "$INSTALL_DIR/requirements.txt"
echo "  ✓ Kütüphaneler hazır"
echo ""

# ── 4. Ana ekran kısayolu ─────────────────────────────────────────────────────
echo "► Ana ekran kısayolu oluşturuluyor..."

SHORTCUTS_DIR="$HOME/.shortcuts"
mkdir -p "$SHORTCUTS_DIR"
chmod 700 "$SHORTCUTS_DIR"

cat > "$SHORTCUTS_DIR/Mix Liste Oluştur" <<EOF
#!/bin/bash
bash "$INSTALL_DIR/start.sh"
EOF
chmod +x "$SHORTCUTS_DIR/Mix Liste Oluştur"

if am start -n com.termux.widget/.TermuxCreateShortcutActivity 2>/dev/null; then
    echo "  ✓ 'Ekle' düğmesine basın — kısayol ana ekrana eklenecek"
else
    echo "  ✓ Kısayol hazır (.shortcuts klasörüne eklendi)"
fi
echo ""

# ── Tamamlandı ────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════╗"
echo "║         Kurulum tamamlandı!          ║"
echo "║                                      ║"
echo "║  Ana ekrandaki kısayola basarak      ║"
echo "║  uygulamayı başlatabilirsiniz.       ║"
echo "╚══════════════════════════════════════╝"
echo ""
