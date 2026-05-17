#!/bin/bash
# Termux:Widget için ana ekran kısayolu oluşturur.
# Termux:Widget uygulaması ~/.shortcuts/ klasöründeki scriptleri widget olarak gösterir.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHORTCUTS_DIR="$HOME/.shortcuts"
SHORTCUT_FILE="$SHORTCUTS_DIR/Mix Liste Oluştur"

mkdir -p "$SHORTCUTS_DIR"
chmod 700 "$SHORTCUTS_DIR"

cat > "$SHORTCUT_FILE" <<EOF
#!/bin/bash
# Müzik klasörünü buraya gir:
MUSIC_DIR="\${1:-/sdcard/Music}"

bash "$SCRIPT_DIR/start.sh" "\$MUSIC_DIR"
EOF

chmod +x "$SHORTCUT_FILE"

echo "Kısayol oluşturuldu: $SHORTCUT_FILE"
echo ""
echo "Sonraki adım:"
echo "  1. F-Droid'den 'Termux:Widget' uygulamasını yükleyin"
echo "  2. Ana ekranda boş bir alana uzun basın → Widget ekle"
echo "  3. Termux:Widget'ı seçin → 'Mix Liste Oluştur' görünecek"
