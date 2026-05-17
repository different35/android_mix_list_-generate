#!/bin/bash
# Termux kurulum scripti

set -e

echo "=== Android Mix List Generator - Kurulum ==="

# Sistem paketleri
pkg update -y
pkg install -y python python-pip clang libsndfile

# Python bağımlılıkları
pip install -r "$(dirname "$0")/requirements.txt"

# start.sh için izin
chmod +x "$(dirname "$0")/start.sh"

echo ""
echo "Kurulum tamamlandı!"
echo "Kullanım: bash start.sh /sdcard/Music"
echo "          bash start.sh /sdcard/Music --rename"
echo "          bash start.sh --single /sdcard/Music/sarki.mp3"
