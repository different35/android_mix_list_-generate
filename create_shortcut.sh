#!/bin/bash
# Ana ekrana doğrudan kısayol ekler.
# Android 8+ güvenlik kuralı: sistem bir "Ekle?" onay diyaloğu gösterir.
# Kullanıcı sadece o diyalogda "Ekle" ye basmak zorunda — başka hiçbir adım yok.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SHORTCUT_NAME="Mix Liste Oluştur"
SHORTCUTS_DIR="$HOME/.shortcuts"

# Script dosyasını .shortcuts klasörüne yaz (Termux:Widget bunu okur)
mkdir -p "$SHORTCUTS_DIR"
chmod 700 "$SHORTCUTS_DIR"

cat > "$SHORTCUTS_DIR/$SHORTCUT_NAME" <<EOF
#!/bin/bash
bash "$SCRIPT_DIR/start.sh" "\${1:-/sdcard/Music}"
EOF
chmod +x "$SHORTCUTS_DIR/$SHORTCUT_NAME"

# Termux:Widget'ın CreateShortcutActivity'sini aç.
# Bu aktivite sisteme "pinned shortcut" talebi gönderir:
# Android ekranda "Ana ekrana eklensin mi?" diyaloğu gösterir.
# Kullanıcı sadece "Ekle"ye basar → kısayol hazır.
if am start -n com.termux.widget/.TermuxCreateShortcutActivity 2>/dev/null; then
    echo ""
    echo "  Diyalog açıldı — 'Ekle' düğmesine basın, kısayol hazır!"
else
    echo ""
    echo "  [!] com.termux.widget bulunamadı, kuruluyor..."
    pkg install termux-widget -y 2>/dev/null || true
    # Tekrar dene
    am start -n com.termux.widget/.TermuxCreateShortcutActivity 2>/dev/null || {
        echo "  [!] Termux:Widget hâlâ açılamadı."
        echo "      F-Droid'den manuel olarak yükleyin: search 'Termux:Widget'"
    }
fi
