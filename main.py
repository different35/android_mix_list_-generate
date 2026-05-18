#!/usr/bin/env python3
import sys
import json
import time
import shutil
import sqlite3
import argparse
import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import stft

# Krumhansl-Schmuckler key-finding profiles (perceptual ratings, normalised at runtime)
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
NOTIF_ID = "mixliste_analiz"


# ── İlerleme & bildirim ───────────────────────────────────────────────────────

class ProgressReporter:
    """Terminal progress bar + termux-notification (varsa) ile canlı durum."""

    HAS_NOTIF = shutil.which("termux-notification") is not None
    HAS_VIBRATE = shutil.which("termux-vibrate") is not None

    def __init__(self, total: int):
        self.total = total
        self.current = 0
        self.t0 = time.time()
        self._track_times: list[float] = []
        self._last_t = self.t0

    # ── internal ──────────────────────────────────────────────────────────────

    def _bar(self) -> str:
        pct = self.current / max(self.total, 1)
        filled = int(30 * pct)
        return "█" * filled + "░" * (30 - filled)

    def _eta(self) -> str:
        if not self._track_times:
            return ""
        avg = sum(self._track_times) / len(self._track_times)
        secs = avg * (self.total - self.current)
        if secs < 60:
            return f"~{int(secs)}sn kaldı"
        return f"~{int(secs // 60)}dk {int(secs % 60)}sn kaldı"

    def _notify(self, title: str, content: str, ongoing: bool = True, sound: bool = False):
        if not self.HAS_NOTIF:
            return
        cmd = [
            "termux-notification",
            "--id", NOTIF_ID,
            "--title", title,
            "--content", content,
            "--priority", "low" if ongoing else "high",
        ]
        if ongoing:
            cmd.append("--ongoing")
        if sound:
            cmd.append("--sound")
        subprocess.run(cmd, capture_output=True)

    def _dismiss_notification(self):
        if self.HAS_NOTIF:
            subprocess.run(
                ["termux-notification-remove", NOTIF_ID],
                capture_output=True,
            )

    # ── public ────────────────────────────────────────────────────────────────

    def loading(self, name: str):
        """Dosya yüklenirken göster — analiz sessizliğini maskeler."""
        print(f"  ⏳ yükleniyor: {name[:50]}", flush=True)

    def track_done(self, name: str, from_cache: bool):
        now = time.time()
        if not from_cache:
            self._track_times.append(now - self._last_t)
        self._last_t = now
        self.current += 1

        pct = int(100 * self.current / max(self.total, 1))
        eta = self._eta()
        label = "[önbellek]" if from_cache else "[analiz]  "
        print(f"  {label} {self.current}/{self.total} ({pct}%)  {eta}")
        print(f"  [{self._bar()}]\n")

        notif_content = f"{self.current}/{self.total} • {name[:40]}  {eta}"
        self._notify("Mix Liste Analiz Ediliyor", notif_content)

    def finish(self, cached: int, fresh: int, playlist_path: str | None = None):
        elapsed = time.time() - self.t0
        mins, secs = divmod(int(elapsed), 60)
        time_str = f"{mins}dk {secs}sn" if mins else f"{secs}sn"

        print(f"\nToplam süre: {time_str}")
        print(f"Önbellekten: {cached}  |  Yeni analiz: {fresh}")

        self._dismiss_notification()

        content = f"{self.total} şarkı hazır ({time_str})"
        if playlist_path:
            content += f"\n{playlist_path}"
        self._notify("Mix Liste Hazır!", content, ongoing=False, sound=True)

        if self.HAS_VIBRATE:
            subprocess.run(["termux-vibrate", "-d", "300"], capture_output=True)


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
    """ffmpeg + aubio + numpy/scipy ile çalışan analizci.

    BPM: aubiotrack (C ile yazılmış, MIR endüstri standardı).
    Key: chroma + Krumhansl-Schmuckler key-finding (numpy/scipy).
    Audio I/O: ffmpeg subprocess.
    """

    SAMPLE_RATE = 22050         # Standart MIR örnekleme oranı (key analizi için)
    N_FFT_CHROMA = 8192         # Chroma için: alt oktav (C2~65Hz) ayrımı şart
    HOP_CHROMA = 2048

    def __init__(self):
        self.config_path = Path.home() / "music-analyzer" / "config" / "settings.json"
        self.load_config()
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        missing = []
        if not shutil.which("ffmpeg"):
            missing.append("ffmpeg")
        if not shutil.which("aubiotrack"):
            missing.append("aubio")
        if missing:
            sys.stderr.write(
                f"HATA: Gerekli araçlar eksik: {', '.join(missing)}\n"
                f"Termux'ta kurmak için: pkg install {' '.join(missing)}\n"
            )
            sys.exit(1)

    def load_config(self):
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        else:
            self.config = {
                "analysis_duration": 45,
                "analysis_offset": 20,
                "music_folders": ["/storage/emulated/0/Music", "/storage/emulated/0/Download"],
                "supported_formats": [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".aac"],
            }
            self.save_config()
        # Eski config'ler için varsayılan değerleri doldur
        self.config.setdefault("analysis_duration", 45)
        self.config.setdefault("analysis_offset", 20)

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

    # ── Ses yükleme (ffmpeg subprocess) ───────────────────────────────────────

    def _load_audio(self, file_path, duration=None, offset=None) -> np.ndarray | None:
        """Sesi ffmpeg ile mono float32 olarak SAMPLE_RATE'e dönüştürerek belleğe oku."""
        if duration is None:
            duration = float(self.config["analysis_duration"])
        if offset is None:
            offset = float(self.config["analysis_offset"])

        def _run(args):
            try:
                r = subprocess.run(args, capture_output=True, check=False)
                return r.returncode, r.stdout
            except (OSError, ValueError):
                return -1, b""

        base = [
            "ffmpeg", "-v", "error", "-nostdin",
            "-i", str(file_path),
            "-t", f"{duration:.3f}",
            "-f", "f32le",
            "-ac", "1",
            "-ar", str(self.SAMPLE_RATE),
            "pipe:1",
        ]
        # Önce offset'li deneyelim — intro/outro genelde gürültülü
        rc, raw = _run(["ffmpeg", "-v", "error", "-nostdin",
                        "-ss", f"{offset:.3f}",
                        "-i", str(file_path),
                        "-t", f"{duration:.3f}",
                        "-f", "f32le",
                        "-ac", "1",
                        "-ar", str(self.SAMPLE_RATE),
                        "pipe:1"])
        # Kısa dosya — baştan oku
        if rc != 0 or len(raw) < self.SAMPLE_RATE * 4:
            rc, raw = _run(base)
        if rc != 0 or len(raw) < self.SAMPLE_RATE * 4:
            return None

        y = np.frombuffer(raw, dtype=np.float32).copy()
        # Tepe normalizasyon — analiz seviye-bağımsız olsun
        peak = float(np.max(np.abs(y))) if y.size else 0.0
        if peak > 0:
            y /= peak
        return y

    # ── BPM tespiti (aubio CLI) ───────────────────────────────────────────────

    def _analyze_bpm(self, file_path) -> int | None:
        """aubiotrack ile BPM tespiti.

        aubio (C ile yazılmış MIR kütüphanesi) beat zaman damgalarını saniye
        cinsinden yazdırır. Median inter-beat-interval → BPM; medyan tek tük
        atlanmış/yanlış onset'lere karşı dayanıklıdır.
        """
        try:
            # ffmpeg ile WAV'a decode et — aubio her formatı okuyamaz, ama WAV
            # her zaman çalışır. Stdin/pipe yerine geçici dosya: aubio bazı
            # sürümlerde named pipe ile sorun yaşıyor.
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
                wav_path = tf.name
            try:
                decode = subprocess.run(
                    [
                        "ffmpeg", "-v", "error", "-nostdin", "-y",
                        "-i", str(file_path),
                        "-t", "90",            # ilk 90s yeterli
                        "-ac", "1",
                        "-ar", "44100",
                        wav_path,
                    ],
                    capture_output=True, timeout=60,
                )
                if decode.returncode != 0:
                    return None

                result = subprocess.run(
                    ["aubiotrack", "-i", wav_path],
                    capture_output=True, text=True, timeout=60,
                )
                if result.returncode != 0:
                    return None

                times = []
                for tok in result.stdout.split():
                    try:
                        times.append(float(tok))
                    except ValueError:
                        continue
                if len(times) < 8:
                    return None

                intervals = np.diff(times)
                # En kısa ve en uzun %10'u at — outlier'lara karşı koruma
                if len(intervals) > 10:
                    intervals = np.sort(intervals)
                    cut = max(1, len(intervals) // 10)
                    intervals = intervals[cut:-cut]

                median_interval = float(np.median(intervals))
                if median_interval <= 0:
                    return None

                bpm = 60.0 / median_interval
                if not (50.0 <= bpm <= 220.0):
                    return None
                return int(round(bpm))
            finally:
                try:
                    Path(wav_path).unlink()
                except OSError:
                    pass
        except (subprocess.SubprocessError, OSError) as e:
            print(f"    BPM hatası: {e}")
            return None

    # ── Ton (key) tespiti ─────────────────────────────────────────────────────

    @staticmethod
    def _estimate_tuning(mag: np.ndarray, freqs: np.ndarray) -> float:
        """Standart akorttan sapmayı yarım-ton cinsinden tahmin et (-0.5..0.5)."""
        # Her zaman çerçevesinde tepe frekansları topla, en yakın yarım-tona uzaklıklarını al
        if mag.size == 0:
            return 0.0
        valid = (freqs >= 100.0) & (freqs <= 2000.0)
        if valid.sum() < 8:
            return 0.0
        v_freqs = freqs[valid]
        v_mag = mag[valid]
        # Her sütunda en yüksek 8 binin sapması
        deviations = []
        weights = []
        for col in range(v_mag.shape[1]):
            col_mag = v_mag[:, col]
            if col_mag.max() <= 0:
                continue
            top = np.argpartition(col_mag, -8)[-8:]
            for idx in top:
                f = v_freqs[idx]
                if f <= 0:
                    continue
                midi = 12.0 * np.log2(f / 440.0) + 69.0
                dev = midi - round(midi)  # -0.5..0.5
                deviations.append(dev)
                weights.append(col_mag[idx])
        if not deviations:
            return 0.0
        deviations = np.array(deviations)
        weights = np.array(weights)
        # Ağırlıklı medyan benzeri: ağırlıklı ortalama
        wsum = weights.sum()
        if wsum <= 0:
            return 0.0
        avg = float(np.sum(deviations * weights) / wsum)
        # Aşırı kaymaları bastır
        return max(-0.5, min(0.5, avg))

    def _analyze_key_and_mode(self, file_path):
        try:
            # Ton, BPM'den daha uzun bir pencere ister: tonalite parça boyunca daha kararlı,
            # ama "yeterli akor değişimi" için en az 30s şart.
            base_dur = float(self.config["analysis_duration"])
            y = self._load_audio(file_path, duration=max(45.0, base_dur))
            if y is None or len(y) < self.SAMPLE_RATE * 8:
                return None, None

            sr = self.SAMPLE_RATE
            n_fft = self.N_FFT_CHROMA
            hop = self.HOP_CHROMA

            _, _, Z = stft(
                y, fs=sr,
                nperseg=n_fft,
                noverlap=n_fft - hop,
                window="hann",
                return_onesided=True,
                padded=False,
                boundary=None,
            )
            mag = np.abs(Z)
            freqs = np.fft.rfftfreq(n_fft, 1.0 / sr)

            # Akort sapması (semitone): -0.5..0.5 — referansı düzelt
            tuning_dev = self._estimate_tuning(mag, freqs)

            # Müzikal frekans aralığı: C2 (~65Hz) – C7 (~2093Hz)
            f_min, f_max = 65.0, 2093.0
            valid_mask = (freqs >= f_min) & (freqs <= f_max)
            v_freqs = freqs[valid_mask]
            v_mag = mag[valid_mask]
            if v_freqs.size == 0:
                return None, None

            # Her bini ait olduğu pitch class'a yumuşak (Gaussian) ata.
            # Sert mod-12 atamasından çok daha kararlı — yarım-ton sınırında titreşim azalır.
            midi = 12.0 * np.log2(v_freqs / 440.0) + 69.0 - tuning_dev
            pc_float = midi % 12.0           # 0..12
            pcs = np.arange(12)[:, None]     # 12x1
            # Dairesel uzaklık
            dist = np.minimum(np.abs(pc_float[None, :] - pcs),
                              12.0 - np.abs(pc_float[None, :] - pcs))
            # σ ≈ 0.5 yarım-ton — komşu pitch class'a sızıntı küçük
            weights = np.exp(-(dist ** 2) / (2.0 * 0.5 ** 2))   # 12 x F
            # 1/f^a ağırlığı: bas seslerin baskın olmasını dengele (a≈0.5 ılımlı)
            freq_weight = 1.0 / np.sqrt(v_freqs)
            chroma = weights @ (v_mag * freq_weight[:, None])    # 12 x T

            # Çerçeve enerjisi düşük olanları (sessizlik) at
            frame_energy = chroma.sum(axis=0)
            if frame_energy.max() <= 0:
                return None, None
            active = frame_energy > frame_energy.max() * 0.1
            if active.sum() < 5:
                return None, None

            # Çerçeve başına normalize → akor değişimleri eşit ağırlıkta sayılır
            norm = chroma[:, active] / (frame_energy[active] + 1e-12)
            chroma_mean = norm.mean(axis=1)
            # Vektörü 0-ortalamalı yap → korelasyon
            chroma_centered = chroma_mean - chroma_mean.mean()

            major_prof = MAJOR_PROFILE - MAJOR_PROFILE.mean()
            minor_prof = MINOR_PROFILE - MINOR_PROFILE.mean()

            best_score, best_key, best_mode = -np.inf, None, None
            cn = float(np.linalg.norm(chroma_centered))
            mn = float(np.linalg.norm(major_prof))
            nn = float(np.linalg.norm(minor_prof))
            if cn == 0 or mn == 0 or nn == 0:
                return None, None
            for i in range(12):
                rotated = np.roll(chroma_centered, -i)
                for profile, mode, pn in (
                    (major_prof, "major", mn),
                    (minor_prof, "minor", nn),
                ):
                    score = float(np.dot(rotated, profile) / (cn * pn))
                    if score > best_score:
                        best_score, best_key, best_mode = score, KEY_NAMES[i], mode

            return best_key, best_mode
        except Exception as e:
            print(f"    Key hatası: {e}")
            return None, None

    def get_camelot_key(self, key: str, mode: str = "major") -> str | None:
        return CAMELOT_MAP.get(key, {}).get(mode)

    def analyze_file(
        self,
        file_path,
        cache: AnalysisCache | None = None,
        progress: ProgressReporter | None = None,
    ) -> dict:
        file_path = Path(file_path)

        if cache:
            hit = cache.get(file_path)
            if hit:
                bpm_s = str(hit["bpm"]) if hit["bpm"] else "?"
                cam_s = hit["camelot"] or "?"
                print(f"    BPM: {bpm_s} | Key: {hit['key'] or '?'} {hit['mode'] or ''} | Camelot: {cam_s}")
                if progress:
                    progress.track_done(file_path.name, from_cache=True)
                return hit

        if progress:
            progress.loading(file_path.name)

        bpm = self._analyze_bpm(file_path)
        key, mode = self._analyze_key_and_mode(file_path)
        camelot = self.get_camelot_key(key, mode) if key else None
        print(f"    BPM: {bpm} | Key: {key or '?'} {mode or ''} | Camelot: {camelot or '?'}")

        result = {"file": file_path, "bpm": bpm, "key": key, "mode": mode, "camelot": camelot}
        if cache:
            cache.save(result)
        if progress:
            progress.track_done(file_path.name, from_cache=False)
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
    progress = ProgressReporter(len(music_files))
    results = []

    for fp in music_files:
        result = analyzer.analyze_file(fp, cache, progress)
        if args.rename and result["bpm"]:
            result["file"] = analyzer.update_filename(result["file"], result["bpm"], result["camelot"])
        results.append(result)

    fresh = sum(1 for r in results if not r.get("_from_cache"))
    cached_count = len(results) - fresh

    playlist_path = None
    if not args.no_playlist:
        playlist_path = Path(args.output) if args.output else Path(folder_path) / "mix_playlist.m3u"
        analyzer.generate_playlist(results, playlist_path, absolute_paths=args.absolute_paths)

    progress.finish(cached_count, fresh, str(playlist_path) if playlist_path else None)

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
