#!/bin/bash
# Interaktif launcher. Termux kısayoluna tıklandığında çalışır.
# Argüman verilirse doğrudan main.py'a iletilir (CLI kullanımı için).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ $# -gt 0 ]; then
    python3 "$SCRIPT_DIR/main.py" "$@"
    exit $?
fi

# ── Termux:API kontrolü ───────────────────────────────────────────────────────
if ! command -v termux-dialog &>/dev/null; then
    echo "termux-api kuruluyor..."
    pkg install termux-api -y
fi

# JSON'dan belirtilen alanı oku
json_get() {
    python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    v = d.get('$1', '')
    print('' if v is None else v)
except:
    print('')
"
}

# ── Adım 1: Mevcut müzik klasörlerini tespit et ───────────────────────────────
DIRS=()
for d in "/sdcard/Music" "/sdcard/Download" \
         "/sdcard/WhatsApp/Media/WhatsApp Audio" \
         "/storage/emulated/0/Music" "/sdcard"; do
    [ -d "$d" ] && DIRS+=("$d")
done
DIRS+=("Ozel klasor gir")

DIR_CSV=$(printf '%s,' "${DIRS[@]}" | sed 's/,$//')

FOLDER_IDX=$(termux-dialog sheet \
    -l "Muzik klasoru secin" \
    -v "$DIR_CSV" \
    2>/dev/null | json_get index)

[ -z "$FOLDER_IDX" ] || [ "$FOLDER_IDX" = "-1" ] && exit 0

FOLDER="${DIRS[$FOLDER_IDX]}"

if [ "$FOLDER" = "Ozel klasor gir" ]; then
    FOLDER=$(termux-dialog text \
        -l "Klasor yolu" \
        -d "/sdcard/Music" \
        2>/dev/null | json_get text)
    [ -z "$FOLDER" ] && exit 0
fi

if [ ! -d "$FOLDER" ]; then
    termux-dialog confirm -l "Hata" -i "Klasor bulunamadi: $FOLDER" 2>/dev/null
    exit 1
fi

# ── Adım 2: Ne yapmak isteniyor? ─────────────────────────────────────────────
ACTION_IDX=$(termux-dialog sheet \
    -l "$FOLDER" \
    -v "Tum klasoru analiz et,Sarki sec" \
    2>/dev/null | json_get index)

[ -z "$ACTION_IDX" ] || [ "$ACTION_IDX" = "-1" ] && exit 0

# ── Adım 3a: Tüm klasör ──────────────────────────────────────────────────────
if [ "$ACTION_IDX" = "0" ]; then
    termux-toast "Analiz basliyor..." 2>/dev/null
    python3 "$SCRIPT_DIR/main.py" "$FOLDER"
    termux-toast "Playlist olusturuldu: $FOLDER/mix_playlist.m3u" 2>/dev/null
    exit 0
fi

# ── Adım 3b: Şarkı seç ───────────────────────────────────────────────────────
mapfile -t FILES < <(find "$FOLDER" -maxdepth 1 \
    \( -iname "*.mp3" -o -iname "*.wav" -o -iname "*.flac" -o -iname "*.m4a" \) \
    2>/dev/null | sort)

if [ ${#FILES[@]} -eq 0 ]; then
    termux-dialog confirm \
        -l "Muzik bulunamadi" \
        -i "$FOLDER klasorunde muzik dosyasi yok." \
        2>/dev/null
    exit 1
fi

NAMES_CSV=$(printf '%s\n' "${FILES[@]}" | xargs -I{} basename {} | \
    tr '\n' ',' | sed 's/,$//')

SELECTED_JSON=$(termux-dialog checkbox \
    -l "Analiz edilecek sarkilari secin" \
    -v "$NAMES_CSV" \
    2>/dev/null)

SELECTED_INDICES=$(echo "$SELECTED_JSON" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(' '.join(str(v['index']) for v in d.get('values', [])))
except:
    print('')
")

[ -z "$SELECTED_INDICES" ] && exit 0

SELECTED_FILES=()
for i in $SELECTED_INDICES; do
    SELECTED_FILES+=("${FILES[$i]}")
done

termux-toast "${#SELECTED_FILES[@]} sarki analiz ediliyor..." 2>/dev/null
python3 "$SCRIPT_DIR/main.py" --files "${SELECTED_FILES[@]}" --output "$FOLDER/mix_playlist.m3u"
termux-toast "Playlist olusturuldu!" 2>/dev/null
