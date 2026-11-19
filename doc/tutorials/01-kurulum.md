# 1. Kurulum ve ilk proje

**Hedef:** Başlangıç oyununu açıp kodun ve varlıkların nerede olduğunu görmek.

1. Doku2D deposunu aç. CPython 3.13 ile bir sanal ortam oluştur. Windows
   PowerShell örneği:

   ```powershell
   py -3.13 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -e .
   ```

   Linux'ta `python3 -m venv .venv-linux` ve `source .venv-linux/bin/activate`
   kullan. Grafik kütüphaneleri için [platform kılavuzuna](../build.md) bak.

2. Ayrı bir oyun klasörü oluştur ve oyunu aç:

   ```sh
   doku2d create egitim
   cd egitim
   doku2d run
   ```

3. WASD veya oklarla yürü. Bir ışık topla, F5 ile kaydet, hareket et ve F9
   ile geri yükle. Saat sürgüsü gündüz-geceyi gösterir.

**Kontrol:** `main.py` giriş dosyasıdır, `doku2d.toml` çözünürlük ve varlık
yollarını belirler, `assets/level.tmj` Tiled haritasıdır. `doku2d run --frames 3`
pencereyi açıp üç kare sonra kapatır.

[Sonraki: Game ve Entity](02-oyun-dongusu.md)
