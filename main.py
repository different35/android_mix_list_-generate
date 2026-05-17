#!/usr/bin/env python3
import sys
import json
import time
import sqlite3
import argparse
from pathlib import Path

import librosa
import numpy as np
from mutagen import File

MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

KEY_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

CAMELOT_MAP = {
    'C':  {'major': '8B', 'minor': '5A'},
    'C#': {'major': '3B', 'minor': '12A'},
    'D':  {'major': '10B', 'minor': '7A'},
    'D#': {'major': '5B', 'minor': '2A'},
    'E':  {'major': '12B', 'minor': '9A'},
    'F':  {'major': '7B', 'minor': '4A'},
    'F#': {'major': '2B', 'minor': '11A'},
    'G':  {'major': '9B', 'minor': '6A'},
    'G#': {'major': '4B', 'minor': '1A'},
    'A':  {'major': '11B', 'minor': '8A'},
    'A#': {'major': '6B', 'minor': '3A'},
    'B':  {'major': '1B', 'minor': '10A'},
}

DB_PATH = Path.home() / "music-analyzer" / "cache.db"


# ── Cache ─────────────────────────────────────────────────────────────────────

class AnalysisCache:
    """SQLite-backed persistent store for track analysis results."""

    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS tracks (
                path        TEXT    PRIMARY KEY,
                mtime       REAL    NOT NULL,
                bpm         INTEGER,
                key         TEXT,
                mode        TEXT,
                camelot     TEXT,
                analyzed_at REAL    NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_tracks_mtime ON tracks(mtime);
        """)
        self._conn.commit()

    def get(self, file_path: Path) -> dict | None:
        """Return cached result if file is unchanged, else None."""
        try:
            mtime = file_path.stat().st_mtime
        except OSError:
            return None

        row = self._conn.execute(
            "SELECT bpm, key, mode, camelot, mtime FROM tracks WHERE path = ?",
            (str(file_path),)
        ).fetchone()

        if row and abs(row["mtime"] - mtime) < 1.0:
            return {
                "file": file_path,
                "bpm": row["bpm"],
                "key": row["key"],
                "mode": row["mode"],
                "camelot": row["camelot"],
                "_from_cache": True,
            }
        return None

    def save(self, result: dict):
        """Persist an analysis result."""
        fp = result["file"]
        try:
            mtime = fp.stat().st_mtime
        except OSError:
            return
        self._conn.execute(
            """INSERT OR REPLACE INTO tracks
               (path, mtime, bpm, key, mode, camelot, analyzed_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (str(fp), mtime, result["bpm"], result["key"],
             result["mode"], result["camelot"], time.time()),
        )
        self._conn.commit()

    def stats(self) -> dict:
        row = self._conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN bpm IS NOT NULL THEN 1 ELSE 0 END) AS analyzed "
            "FROM tracks"
        ).fetchone()
        return {"total": row["total"] or 0, "analyzed": row["analyzed"] or 0}

    def purge_missing(self) -> int:
        """Delete entries whose files no longer exist on disk."""
        paths = [r[0] for r in self._conn.execute("SELECT path FROM tracks").fetchall()]
        missing = [p for p in paths if not Path(p).exists()]
        if missing:
            self._conn.executemany("DELETE FROM tracks WHERE path = ?", [(p,) for p in missing])
            self._conn.commit()
        return len(missing)

    def all_tracks(self) -> list[dict]:
        """Return every cached track as a result dict."""
        rows = self._conn.execute(
            "SELECT path, bpm, key, mode, camelot FROM tracks ORDER BY path"
        ).fetchall()
        return [
            {"file": Path(r["path"]), "bpm": r["bpm"], "key": r["key"],
             "mode": r["mode"], "camelot": r["camelot"]}
            for r in rows if Path(r["path"]).exists()
        ]

    def close(self):
        self._conn.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def camelot_compatibility(key1: str, key2: str) -> int:
    if not key1 or not key2:
        return 0
    if key1 == key2:
        return 3
    num1, letter1 = int(key1[:-1]), key1[-1]
    num2, letter2 = int(key2[:-1]), key2[-1]
    if num1 == num2:
        return 2
    if letter1 == letter2 and abs(num1 - num2) in (1, 11):
        return 1
    return 0


# ── Analyzer ──────────────────────────────────────────────────────────────────

class MusicAnalyzer:
    def __init__(self):
        self.config_path = Path.home() / "music-analyzer" / "config" / "settings.json"
        self.load_config()

    def load_config(self):
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        else:
            self.config = {
                "analysis_duration": 30,
                "music_folders": ["/storage/emulated/0/Music", "/storage/emulated/0/Download"],
                "supported_formats": [".mp3", ".wav", ".m4a", ".flac"],
            }
            self.save_config()

    def save_config(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=2)

    def find_music_files(self, folder_path):
        folder = Path(folder_path)
        if not folder.exists():
            print(f"Klasör bulunamadı: {folder_path}")
            return []
        files = []
        for ext in self.config["supported_formats"]:
            files.extend(folder.glob(f"**/*{ext}"))
        return sorted(files)

    def _analyze_bpm(self, file_path) -> int | None:
        try:
            y, sr = librosa.load(str(file_path), duration=self.config["analysis_duration"])
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            return round(float(np.atleast_1d(tempo)[0]))
        except Exception as e:
            print(f"    BPM hatası: {e}")
            return None

    def _analyze_key_and_mode(self, file_path) -> tuple[str | None, str | None]:
        try:
            y, sr = librosa.load(str(file_path), duration=self.config["analysis_duration"])
            chroma = librosa.feature.chroma_stft(y=y, sr=sr)
            chroma_mean = np.mean(chroma, axis=1)
            best_score, best_key, best_mode = -np.inf, None, None
            for i in range(12):
                rotated = np.roll(chroma_mean, -i)
                for profile, mode in ((MAJOR_PROFILE, "major"), (MINOR_PROFILE, "minor")):
                    score = float(np.corrcoef(rotated, profile)[0, 1])
                    if score > best_score:
                        best_score, best_key, best_mode = score, KEY_NAMES[i], mode
            return best_key, best_mode
        except Exception as e:
            print(f"    Key hatası: {e}")
            return None, None

    def get_camelot_key(self, key: str, mode: str = "major") -> str | None:
        return CAMELOT_MAP.get(key, {}).get(mode)

    def analyze_file(self, file_path, cache: AnalysisCache | None = None) -> dict:
        file_path = Path(file_path)

        if cache:
            hit = cache.get(file_path)
            if hit:
                bpm_s = str(hit["bpm"]) if hit["bpm"] else "?"
                cam_s = hit["camelot"] or "?"
                print(f"  [önbellek] {file_path.name}")
                print(f"    BPM: {bpm_s} | Key: {hit['key'] or '?'} {hit['mode'] or ''} | Camelot: {cam_s}")
                return hit

        print(f"  [analiz]   {file_path.name}")
        bpm = self._analyze_bpm(file_path)
        key, mode = self._analyze_key_and_mode(file_path)
        camelot = self.get_camelot_key(key, mode) if key else None
        print(f"    BPM: {bpm} | Key: {key or '?'} {mode or ''} | Camelot: {camelot or '?'}")

        result = {"file": file_path, "bpm": bpm, "key": key, "mode": mode, "camelot": camelot}
        if cache:
            cache.save(result)
        return result

    def update_filename(self, file_path, bpm, camelot) -> Path:
        try:
            file_path = Path(file_path)
            stem = file_path.stem
            if " [BPM:" in stem:
                stem = stem.split(" [BPM:")[0]
            if bpm and camelot:
                new_name = f"{stem} [BPM:{bpm}] [Key:{camelot}]{file_path.suffix}"
            elif bpm:
                new_name = f"{stem} [BPM:{bpm}]{file_path.suffix}"
            else:
                return file_path
            new_path = file_path.parent / new_name
            file_path.rename(new_path)
            print(f"    → {new_name}")
            return new_path
        except Exception as e:
            print(f"  Dosya adı hatası: {e}")
            return file_path

    def sort_by_harmonic_compatibility(self, results: list) -> list:
        keyed = [r for r in results if r["camelot"]]
        no_key = [r for r in results if not r["camelot"]]
        if not keyed:
            return no_key
        ordered = [keyed.pop(0)]
        while keyed:
            current = ordered[-1]
            best_idx, best_score = 0, -1
            for i, candidate in enumerate(keyed):
                score = camelot_compatibility(current["camelot"], candidate["camelot"]) * 10
                if current["bpm"] and candidate["bpm"]:
                    diff = abs(current["bpm"] - candidate["bpm"])
                    score += 2 if diff <= 5 else (1 if diff <= 10 else 0)
                if score > best_score:
                    best_score, best_idx = score, i
            ordered.append(keyed.pop(best_idx))
        return ordered + no_key

    def generate_playlist(self, results: list, output_path, absolute_paths: bool = False) -> Path:
        output_path = Path(output_path)
        sorted_results = self.sort_by_harmonic_compatibility(results)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for r in sorted_results:
                bpm_s = str(r["bpm"]) if r["bpm"] else "?"
                cam_s = r["camelot"] if r["camelot"] else "?"
                f.write(f"#EXTINF:-1,{r['file'].stem} [BPM:{bpm_s}] [{cam_s}]\n")
                if absolute_paths:
                    f.write(f"{r['file']}\n")
                else:
                    try:
                        f.write(f"{r['file'].relative_to(output_path.parent)}\n")
                    except ValueError:
                        f.write(f"{r['file']}\n")
        print(f"\nPlaylist oluşturuldu: {output_path}  ({len(sorted_results)} parça)")
        return output_path


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Android Müzik Mix Listesi Oluşturucu",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python main.py /sdcard/Music
  python main.py /sdcard/Music --rename
  python main.py --files a.mp3 b.mp3 c.mp3
  python main.py --single sarki.mp3
  python main.py --cache-stats
  python main.py --cache-purge
        """,
    )
    parser.add_argument("path", nargs="?", help="Analiz edilecek klasör")
    parser.add_argument("--files", nargs="+", help="Belirli dosyalar")
    parser.add_argument("--single", help="Tek dosya analizi")
    parser.add_argument("--rename", action="store_true", help="Dosya adlarını güncelle")
    parser.add_argument("--output", help="Playlist çıktı yolu")
    parser.add_argument("--no-playlist", action="store_true", help="Playlist oluşturma")
    parser.add_argument("--limit", type=int, default=0, help="Maksimum dosya sayısı (0=sınırsız)")
    parser.add_argument("--absolute-paths", action="store_true", help="Playlist içinde mutlak yol")
    parser.add_argument("--no-cache", action="store_true", help="Önbelleği atla, yeniden analiz et")
    parser.add_argument("--cache-stats", action="store_true", help="Önbellek istatistiklerini göster")
    parser.add_argument("--cache-purge", action="store_true", help="Silinmiş dosyaları önbellekten temizle")
    args = parser.parse_args()

    cache = None if args.no_cache else AnalysisCache()

    # ── Cache yönetim komutları ────────────────────────────────────────────────
    if args.cache_stats:
        if not cache:
            print("Önbellek devre dışı.")
            return
        s = cache.stats()
        print(f"Önbellek: {DB_PATH}")
        print(f"  Toplam kayıt : {s['total']}")
        print(f"  Analiz edilmiş: {s['analyzed']}")
        cache.close()
        return

    if args.cache_purge:
        c = cache or AnalysisCache()
        n = c.purge_missing()
        print(f"{n} eksik kayıt temizlendi.")
        c.close()
        return

    analyzer = MusicAnalyzer()

    if cache:
        s = cache.stats()
        if s["total"]:
            print(f"Önbellek: {s['total']} şarkı kayıtlı  ({DB_PATH})\n")

    # ── Tek dosya ─────────────────────────────────────────────────────────────
    if args.single:
        fp = Path(args.single)
        if not fp.exists():
            print("Dosya bulunamadı!")
            sys.exit(1)
        result = analyzer.analyze_file(fp, cache)
        if args.rename and result["bpm"]:
            analyzer.update_filename(fp, result["bpm"], result["camelot"])
        if cache:
            cache.close()
        return

    # ── Dosya listesi veya klasör ──────────────────────────────────────────────
    if args.files:
        music_files = [Path(f) for f in args.files if Path(f).exists()]
        if not music_files:
            print("Hiç dosya bulunamadı!")
            sys.exit(1)
        folder_path = str(music_files[0].parent)
        print(f"{len(music_files)} dosya analiz edilecek\n")
    else:
        folder_path = args.path or "/storage/emulated/0/Music"
        print(f"Müzik dosyaları aranıyor: {folder_path}")
        music_files = analyzer.find_music_files(folder_path)
        if not music_files:
            print("Hiç müzik dosyası bulunamadı!")
            sys.exit(1)
        total = len(music_files)
        if args.limit > 0:
            music_files = music_files[: args.limit]
        print(f"{total} dosya bulundu, {len(music_files)} tanesi işlenecek\n")

    # ── Analiz döngüsü ────────────────────────────────────────────────────────
    results = []
    fresh = 0
    for i, fp in enumerate(music_files):
        print(f"[{i + 1}/{len(music_files)}]", end=" ")
        result = analyzer.analyze_file(fp, cache)
        if not result.get("_from_cache"):
            fresh += 1
        if args.rename and result["bpm"]:
            result["file"] = analyzer.update_filename(result["file"], result["bpm"], result["camelot"])
        results.append(result)

    cached_count = len(results) - fresh
    print(f"\nÖnbellekten: {cached_count}  |  Yeni analiz: {fresh}")

    if not args.no_playlist:
        playlist_path = Path(args.output) if args.output else Path(folder_path) / "mix_playlist.m3u"
        analyzer.generate_playlist(results, playlist_path, absolute_paths=args.absolute_paths)

    print("\n" + "=" * 58)
    print("ANALİZ ÖZETİ  (harmonik sıralama)")
    print("=" * 58)
    for r in analyzer.sort_by_harmonic_compatibility(results):
        name = r["file"].name
        if len(name) > 40:
            name = name[:37] + "..."
        bpm_s = str(r["bpm"]) if r["bpm"] else "   ?"
        key_s = f"{r['key'] or '?':>2} {r['mode'] or '':6}"
        cam_s = r["camelot"] or " ?"
        print(f"  {name:<40}  BPM:{bpm_s:>4}  {key_s}  [{cam_s}]")

    if cache:
        cache.close()


if __name__ == "__main__":
    main()
