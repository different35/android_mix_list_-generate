#!/bin/bash
# Mix Liste Oluşturucu — tam kurulum (Termux için)
# Kullanım:
#   curl -fsSL https://raw.githubusercontent.com/different35/android_mix_list_-generate/main/install.sh | bash

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

# ── 1. Ortam kontrolü ─────────────────────────────────────────────────────────
if [ -z "$PREFIX" ] || [ "${PREFIX#*com.termux}" = "$PREFIX" ]; then
    echo "UYARI: Bu betik Termux ortamı için tasarlandı."
    echo "       Termux dışında çalıştırıyorsanız paket isimleri farklı olabilir."
    echo ""
fi

# ── 2. Sistem paketleri ───────────────────────────────────────────────────────
# Termux paket reposu hepsini önceden derlenmiş olarak verir; pip ile numpy/scipy
# derlemeye kalkışmak Android ARM'de saatler sürer ve genelde başarısız olur.
echo "► Sistem paketleri kuruluyor (numpy, scipy, ffmpeg, termux-api)..."
pkg update -y -q

# Zorunlu paketler
# - ffmpeg: tüm ses formatları için decoder (mp3, m4a, flac, ogg, opus, aac)
# - aubio:  C-tabanlı MIR kütüphanesi → güvenilir BPM tespiti (aubiotrack CLI)
# - python-numpy/scipy: önceden derlenmiş yerel paketler (chroma + key tespiti)
pkg install -y -q \
    curl unzip \
    python python-pip \
    ffmpeg aubio \
    python-numpy python-scipy

# Termux:API (bildirim/dialog için — yoksa CLI moduna düşeriz)
pkg install -y -q termux-api || \
    echo "  (termux-api kurulamadı — bildirim/dialog devre dışı kalacak, sorun değil)"

echo "  ✓ Sistem paketleri hazır"
echo ""

# Hızlı doğrulama: kritik araçlar PATH'te mi?
for need in python ffmpeg aubiotrack; do
    if ! command -v "$need" >/dev/null 2>&1; then
        echo "HATA: '$need' kurulamadı. Kuruluma yeniden deneyin."
        exit 1
    fi
done
# numpy & scipy import edilebiliyor mu?
if ! python - <<'PY' 2>/dev/null
import numpy, scipy   # noqa: F401
PY
then
    echo "HATA: numpy/scipy import edilemiyor. 'pkg install python-numpy python-scipy' deneyin."
    exit 1
fi

# ── 3. Dosyaları indir ────────────────────────────────────────────────────────
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

echo "  ✓ Dosyalar hazır"
echo ""

# ── 4. Storage izni ───────────────────────────────────────────────────────────
if [ ! -e "$HOME/storage/shared" ] && command -v termux-setup-storage >/dev/null 2>&1; then
    echo "► Termux storage izni isteniyor (müzik klasörüne erişim için)..."
    termux-setup-storage
    sleep 1
fi

# ── 5. Ana ekran kısayolu ─────────────────────────────────────────────────────
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
