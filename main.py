#!/usr/bin/env python3
import os
import sys
import json
from pathlib import Path
import librosa
import numpy as np
from mutagen import File
import argparse

class MusicAnalyzer:
    def __init__(self):
        self.config_path = Path.home() / "music-analyzer" / "config" / "settings.json"
        self.load_config()
        
    def load_config(self):
        """Ayarları yükle"""
        if self.config_path.exists():
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
        else:
            self.config = {
                "analysis_duration": 30,  # saniye
                "music_folders": ["/storage/emulated/0/Music", "/storage/emulated/0/Download"],
                "supported_formats": [".mp3", ".wav", ".m4a", ".flac"]
            }
            self.save_config()
    
    def save_config(self):
        """Ayarları kaydet"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def find_music_files(self, folder_path):
        """Ses dosyalarını bul"""
        music_files = []
        folder = Path(folder_path)
        
        if not folder.exists():
            print(f"Klasör bulunamadı: {folder_path}")
            return music_files
            
        for ext in self.config["supported_formats"]:
            music_files.extend(folder.glob(f"**/*{ext}"))
        
        return music_files
    
    def analyze_bpm(self, file_path):
        """BPM analizi"""
        try:
            # Dosyanın ilk 30 saniyesini analiz et
            y, sr = librosa.load(file_path, duration=self.config["analysis_duration"])
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            return int(tempo)
        except Exception as e:
            print(f"BPM analizi hatası: {e}")
            return None
    
    def analyze_key(self, file_path):
        """Key analizi (basit versiyon)"""
        try:
            y, sr = librosa.load(file_path, duration=self.config["analysis_duration"])
            chroma = librosa.feature.chroma_stft(y=y, sr=sr)
            chroma_mean = np.mean(chroma, axis=1)
            
            # Basit key detection
            keys = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            key_index = np.argmax(chroma_mean)
            return keys[key_index]
        except Exception as e:
            print(f"Key analizi hatası: {e}")
            return None
    
    def get_camelot_key(self, musical_key, mode="major"):
        """Musical key'i Camelot wheel'e çevir"""
        camelot_map = {
            'C': {'major': '8B', 'minor': '5A'},
            'C#': {'major': '3B', 'minor': '12A'},
            'D': {'major': '10B', 'minor': '7A'},
            'D#': {'major': '5B', 'minor': '2A'},
            'E': {'major': '12B', 'minor': '9A'},
            'F': {'major': '7B', 'minor': '4A'},
            'F#': {'major': '2B', 'minor': '11A'},
            'G': {'major': '9B', 'minor': '6A'},
            'G#': {'major': '4B', 'minor': '1A'},
            'A': {'major': '11B', 'minor': '8A'},
            'A#': {'major': '6B', 'minor': '3A'},
            'B': {'major': '1B', 'minor': '10A'}
        }
        
        if musical_key in camelot_map:
            return camelot_map[musical_key][mode]
        return None
    
    def analyze_file(self, file_path):
        """Tek dosya analizi"""
        print(f"\nAnaliz ediliyor: {file_path.name}")
        
        # BPM analizi
        bpm = self.analyze_bpm(file_path)
        print(f"BPM: {bpm}")
        
        # Key analizi
        key = self.analyze_key(file_path)
        camelot = self.get_camelot_key(key) if key else None
        print(f"Key: {key} (Camelot: {camelot})")
        
        return {
            'file': file_path,
            'bpm': bpm,
            'key': key,
            'camelot': camelot
        }
    
    def update_filename(self, file_path, bpm, camelot):
        """Dosya adını güncelle"""
        try:
            old_name = file_path.stem
            extension = file_path.suffix
            
            # Eğer zaten analiz bilgisi varsa temizle
            if " [BPM:" in old_name:
                old_name = old_name.split(" [BPM:")[0]
            
            # Yeni isim oluştur
            if bpm and camelot:
                new_name = f"{old_name} [BPM:{bpm}] [Key:{camelot}]{extension}"
            elif bpm:
                new_name = f"{old_name} [BPM:{bpm}]{extension}"
            else:
                return False
                
            new_path = file_path.parent / new_name
            file_path.rename(new_path)
            print(f"Dosya adı güncellendi: {new_name}")
            return True
            
        except Exception as e:
            print(f"Dosya adı güncellenirken hata: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description='Termux Müzik Analiz Aracı')
    parser.add_argument('path', nargs='?', help='Analiz edilecek klasör yolu')
    parser.add_argument('--rename', action='store_true', help='Dosya adlarını güncelle')
    parser.add_argument('--single', help='Tek dosya analizi')
    
    args = parser.parse_args()
    
    analyzer = MusicAnalyzer()
    
    if args.single:
        # Tek dosya analizi
        file_path = Path(args.single)
        if file_path.exists():
            result = analyzer.analyze_file(file_path)
            if args.rename and result['bpm']:
                analyzer.update_filename(file_path, result['bpm'], result['camelot'])
        else:
            print("Dosya bulunamadı!")
        return
    
    # Klasör analizi
    folder_path = args.path if args.path else "/storage/emulated/0/Music"
    
    print(f"Müzik dosyaları aranıyor: {folder_path}")
    music_files = analyzer.find_music_files(folder_path)
    
    if not music_files:
        print("Hiç müzik dosyası bulunamadı!")
        return
    
    print(f"{len(music_files)} dosya bulundu\n")
    
    results = []
    for i, file_path in enumerate(music_files[:10]):  # İlk 10 dosya test için
        print(f"İlerleme: {i+1}/{min(10, len(music_files))}")
        result = analyzer.analyze_file(file_path)
        results.append(result)
        
        if args.rename and result['bpm']:
            analyzer.update_filename(result['file'], result['bpm'], result['camelot'])
    
    # Özet
    print("\n" + "="*50)
    print("ANALİZ ÖZETİ")
    print("="*50)
    for result in results:
        print(f"{result['file'].name}")
        print(f"  BPM: {result['bpm']} | Key: {result['key']} | Camelot: {result['camelot']}")

if __name__ == "__main__":
    main()