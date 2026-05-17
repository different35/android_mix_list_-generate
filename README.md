# Android Mix List Generator

Termux üzerinde çalışan, Android telefonunuzdaki müzik dosyalarını analiz eden ve harmonik mixing uyumlu `.m3u` playlist oluşturan araç.

## Ne yapar?

- Her şarkının **BPM** ve **key** (ton) bilgisini tespit eder
- Major/minor modu Krumhansl-Schmuckler profilleriyle doğru tespit eder
- **Camelot Wheel** sıralamasıyla harmonik uyumlu bir playlist üretir
- İsteğe bağlı olarak dosya adlarına BPM ve key bilgisini ekler
- Sıralı çalma özelliği olan herhangi bir player'da (VLC, Poweramp, vb.) `.m3u` listesini açın

## Kurulum (Termux)

```bash
git clone https://github.com/different35/android_mix_list_-generate ~/music-analyzer
cd ~/music-analyzer
bash setup_termux.sh
```

Kurulum tamamlandığında ana ekran kısayolu otomatik oluşturulur.  
Kısayolu görmek için:
1. F-Droid'den **Termux:Widget** uygulamasını yükleyin
2. Ana ekranda boş alana uzun basın → **Widget ekle**
3. Termux:Widget'ı seçin → **Mix Liste Oluştur** görünecek

## Kullanım

```bash
# Klasör analizi + harmonik sıralı playlist oluştur
bash start.sh /sdcard/Music

# Dosya adlarını [BPM:xxx] [Key:xX] ile güncelle
bash start.sh /sdcard/Music --rename

# Playlist çıktı konumunu belirt
bash start.sh /sdcard/Music --output /sdcard/playlist.m3u

# Tek dosya analizi
bash start.sh --single /sdcard/Music/sarki.mp3

# İlk 50 dosyayı analiz et
bash start.sh /sdcard/Music --limit 50

# Mutlak yollarla playlist oluştur (farklı klasöre taşıyacaksan)
bash start.sh /sdcard/Music --absolute-paths
```

## Çıktı örneği

```
[1/120]   Deadmau5 - Strobe.mp3
    BPM: 128 | Key: A minor | Camelot: 8A
[2/120]   Eric Prydz - Call On Me.mp3
    BPM: 126 | Key: A major | Camelot: 11B
...

Playlist oluşturuldu: /sdcard/Music/mix_playlist.m3u
Toplam 120 parça
```

Playlist, Camelot Wheel komşuluğuna ve BPM yakınlığına göre otomatik sıralanır.
