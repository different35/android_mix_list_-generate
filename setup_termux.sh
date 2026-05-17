#!/bin/bash
# Termux kurulum scripti

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Android Mix List Generator - Kurulum ==="

# Sistem paketleri
pkg update -y
pkg install -y python python-pip clang libsndfile

# Python bağımlılıkları
pip install -r "$SCRIPT_DIR/requirements.txt"

# Çalıştırma izinleri
chmod +x "$SCRIPT_DIR/start.sh"
chmod +x "$SCRIPT_DIR/create_shortcut.sh"

# Ana ekran kısayolu oluştur
echo ""
echo "Ana ekran kısayolu oluşturuluyor..."
bash "$SCRIPT_DIR/create_shortcut.sh"

echo ""
echo "=== Kurulum tamamlandı! ==="
echo ""
echo "Kullanım:"
echo "  bash start.sh /sdcard/Music              # playlist oluştur"
echo "  bash start.sh /sdcard/Music --rename     # dosyaları yeniden adlandır"
echo "  bash start.sh --single /sdcard/Music/sarki.mp3"
