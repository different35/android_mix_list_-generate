# Mix Liste Oluşturucu

Android telefonunuzdaki müzikleri analiz eder, harmonik olarak uyumlu bir çalma listesi oluşturur. Kurulum bir kez yapılır, sonrasında ana ekrandaki kısayola basmak yeterli.

## Kurulum (bir kez)

Termux'u açın ve şu komutu çalıştırın:

```bash
git clone https://github.com/different35/android_mix_list_-generate ~/music-analyzer && bash ~/music-analyzer/setup_termux.sh
```

Kurulum bitince "**Ekle**" diyaloğu açılır — ekrana basın, kısayol ana ekrana eklenir.

## Kullanım

1. Ana ekrandaki **Mix Liste Oluştur** kısayoluna bas
2. Müzik klasörünü seç
3. **Tüm klasörü analiz et** veya **Şarkı seç**
4. Şarkı seçtiysen listeden işaretle → **Tamam**
5. Bitti — playlist hazır, bildirim gelir

Oluşturulan `mix_playlist.m3u` dosyasını VLC, Poweramp veya sıralı çalma destekleyen herhangi bir player ile açın.

## Ne yapar?

Her şarkının BPM ve tonunu tespit eder, Camelot Wheel uyumuna göre sıralar. Bir şarkıdan diğerine geçişler harmonik olarak uyumlu olur — DJ mixing mantığıyla.

Analiz sonuçları cihazda saklanır. Aynı şarkı bir daha analiz edilmez, her açılışta anında yüklenir.
