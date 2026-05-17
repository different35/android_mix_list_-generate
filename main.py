#!/usr/bin/env python3
import sys
import json
import argparse
from pathlib import Path

import librosa
import numpy as np
from mutagen import File

# Krumhansl-Schmuckler key profiles for major/minor detection
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


def camelot_compatibility(key1: str, key2: str) -> int:
    """Return 0-3 compatibility score between two Camelot keys."""
    if not key1 or not key2:
        return 0
    if key1 == key2:
        return 3
    num1, letter1 = int(key1[:-1]), key1[-1]
    num2, letter2 = int(key2[:-1]), key2[-1]
    if num1 == num2:  # relative major/minor
        return 2
    if letter1 == letter2 and abs(num1 - num2) in (1, 11):  # adjacent on wheel
        return 1
    return 0


class MusicAnalyzer:
    def __init__(self):
        self.config_path = Path.home() / "music-analyzer" / "config" / "settings.json"
        self.load_config()

    def load_config(self):
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
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
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)

    def find_music_files(self, folder_path):
        music_files = []
        folder = Path(folder_path)
        if not folder.exists():
            print(f"Klasör bulunamadı: {folder_path}")
            return music_files
        for ext in self.config["supported_formats"]:
            music_files.extend(folder.glob(f"**/*{ext}"))
        return sorted(music_files)

    def analyze_bpm(self, file_path) -> int | None:
        try:
            y, sr = librosa.load(str(file_path), duration=self.config["analysis_duration"])
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            return round(float(np.atleast_1d(tempo)[0]))
        except Exception as e:
            print(f"  BPM analizi hatası: {e}")
            return None

    def analyze_key_and_mode(self, file_path) -> tuple[str | None, str | None]:
        """Detect key and mode (major/minor) using Krumhansl-Schmuckler profiles."""
        try:
            y, sr = librosa.load(str(file_path), duration=self.config["analysis_duration"])
            chroma = librosa.feature.chroma_stft(y=y, sr=sr)
            chroma_mean = np.mean(chroma, axis=1)

            best_score = -np.inf
            best_key = None
            best_mode = None

            for i in range(12):
                rotated = np.roll(chroma_mean, -i)
                major_score = float(np.corrcoef(rotated, MAJOR_PROFILE)[0, 1])
                minor_score = float(np.corrcoef(rotated, MINOR_PROFILE)[0, 1])
                if major_score > best_score:
                    best_score = major_score
                    best_key = KEY_NAMES[i]
                    best_mode = 'major'
                if minor_score > best_score:
                    best_score = minor_score
                    best_key = KEY_NAMES[i]
                    best_mode = 'minor'

            return best_key, best_mode
        except Exception as e:
            print(f"  Key analizi hatası: {e}")
            return None, None

    def get_camelot_key(self, musical_key: str, mode: str = 'major') -> str | None:
        return CAMELOT_MAP.get(musical_key, {}).get(mode)

    def analyze_file(self, file_path) -> dict:
        file_path = Path(file_path)
        print(f"  {file_path.name}")
        bpm = self.analyze_bpm(file_path)
        key, mode = self.analyze_key_and_mode(file_path)
        camelot = self.get_camelot_key(key, mode) if key else None
        print(f"    BPM: {bpm} | Key: {key or '?'} {mode or ''} | Camelot: {camelot or '?'}")
        return {
            'file': file_path,
            'bpm': bpm,
            'key': key,
            'mode': mode,
            'camelot': camelot,
        }

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
        """Greedy harmonic ordering using Camelot wheel + BPM proximity."""
        keyed = [r for r in results if r['camelot']]
        no_key = [r for r in results if not r['camelot']]

        if not keyed:
            return no_key

        ordered = [keyed.pop(0)]
        while keyed:
            current = ordered[-1]
            best_idx = 0
            best_score = -1
            for i, candidate in enumerate(keyed):
                score = camelot_compatibility(current['camelot'], candidate['camelot']) * 10
                if current['bpm'] and candidate['bpm']:
                    bpm_diff = abs(current['bpm'] - candidate['bpm'])
                    if bpm_diff <= 5:
                        score += 2
                    elif bpm_diff <= 10:
                        score += 1
                if score > best_score:
                    best_score = score
                    best_idx = i
            ordered.append(keyed.pop(best_idx))

        return ordered + no_key

    def generate_playlist(self, results: list, output_path, absolute_paths: bool = False) -> Path:
        """Generate .m3u playlist sorted by harmonic compatibility."""
        output_path = Path(output_path)
        sorted_results = self.sort_by_harmonic_compatibility(results)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("#EXTM3U\n")
            for r in sorted_results:
                bpm_str = str(r['bpm']) if r['bpm'] else '?'
                camelot_str = r['camelot'] if r['camelot'] else '?'
                display = f"{r['file'].stem} [BPM:{bpm_str}] [{camelot_str}]"
                f.write(f"#EXTINF:-1,{display}\n")
                if absolute_paths:
                    f.write(f"{r['file']}\n")
                else:
                    try:
                        f.write(f"{r['file'].relative_to(output_path.parent)}\n")
                    except ValueError:
                        f.write(f"{r['file']}\n")

        print(f"\nPlaylist oluşturuldu: {output_path}")
        print(f"Toplam {len(sorted_results)} parça")
        return output_path


def main():
    parser = argparse.ArgumentParser(
        description='Android Müzik Mix Listesi Oluşturucu',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python main.py /sdcard/Music
  python main.py /sdcard/Music --rename
  python main.py /sdcard/Music --output karışık.m3u
  python main.py --single sarki.mp3
        """,
    )
    parser.add_argument('path', nargs='?', help='Analiz edilecek klasör yolu')
    parser.add_argument('--rename', action='store_true', help='Dosya adlarını BPM ve key ile güncelle')
    parser.add_argument('--single', help='Tek dosya analizi')
    parser.add_argument('--output', help='Playlist çıktı dosyası (varsayılan: <klasör>/mix_playlist.m3u)')
    parser.add_argument('--no-playlist', action='store_true', help='Playlist oluşturma')
    parser.add_argument('--limit', type=int, default=0, help='Maksimum dosya sayısı (0=sınırsız)')
    parser.add_argument('--absolute-paths', action='store_true', help='Playlist içinde mutlak yol kullan')
    args = parser.parse_args()

    analyzer = MusicAnalyzer()

    if args.single:
        file_path = Path(args.single)
        if not file_path.exists():
            print("Dosya bulunamadı!")
            sys.exit(1)
        result = analyzer.analyze_file(file_path)
        if args.rename and result['bpm']:
            analyzer.update_filename(file_path, result['bpm'], result['camelot'])
        return

    folder_path = args.path or "/storage/emulated/0/Music"
    print(f"Müzik dosyaları aranıyor: {folder_path}")
    music_files = analyzer.find_music_files(folder_path)

    if not music_files:
        print("Hiç müzik dosyası bulunamadı!")
        sys.exit(1)

    total = len(music_files)
    if args.limit > 0:
        music_files = music_files[: args.limit]
    print(f"{total} dosya bulundu, {len(music_files)} tanesi analiz edilecek\n")

    results = []
    for i, file_path in enumerate(music_files):
        print(f"[{i + 1}/{len(music_files)}]", end=" ")
        result = analyzer.analyze_file(file_path)
        if args.rename and result['bpm']:
            result['file'] = analyzer.update_filename(result['file'], result['bpm'], result['camelot'])
        results.append(result)

    if not args.no_playlist:
        playlist_path = Path(args.output) if args.output else Path(folder_path) / "mix_playlist.m3u"
        analyzer.generate_playlist(results, playlist_path, absolute_paths=args.absolute_paths)

    print("\n" + "=" * 58)
    print("ANALİZ ÖZETİ  (harmonik sıralama)")
    print("=" * 58)
    for r in analyzer.sort_by_harmonic_compatibility(results):
        name = r['file'].name
        if len(name) > 40:
            name = name[:37] + "..."
        bpm_str = str(r['bpm']) if r['bpm'] else '   ?'
        key_str = f"{r['key'] or '?':>2} {r['mode'] or '':6}"
        camelot_str = r['camelot'] or ' ?'
        print(f"  {name:<40}  BPM:{bpm_str:>4}  {key_str}  [{camelot_str}]")


if __name__ == "__main__":
    main()
