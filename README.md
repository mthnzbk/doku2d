# Doku2D

Python ile kod odaklı 2D oyun framework'ü. Nesneler `Game` içine kaydolur,
bölüm geçişleri `Scope` ile, çizim katmanları `Canvas` ile yönetilir.

## Kurulum ve ilk proje

Depoyu kullandığın Python ortamına kur:

```sh
python -m pip install -e .
python -m doku2d create benim_oyunum
cd benim_oyunum
python -m doku2d run
```

Şablon; harita, karakter, toplama, gece-gündüz, CanvasGroup HUD ve kaydet/yükle
özellikleriyle çalışır. Proje ayarları `doku2d.toml`, kaynaklar `assets/` içindedir.
F5 kaydeder, F9 yükler. Nuitka derlemesi için motor deposunda `python -m pip install -e ".[build]"` ile derleme bağımlılığını kur. Oyun klasöründe:

```sh
python -m doku2d build
```

`build`, Nuitka ile hedef işletim sisteminde bağımsız bir uygulama üretir.
Windows'ta uygulama `dist/<app_id>.dist/<app_id>.exe` altında bulunur.

## Örnekler

`python -m examples.gallery` ile örneklerin tamamını düğmelerle açabilirsin.
Galeride Gece ve Kum temaları aynı kontroller üzerinde denenebilir.

| Komut | İçerik |
| --- | --- |
| `python -m doku2d run --project examples/starter_project` | Yeni başlangıç projesi; CanvasGroup, gece-gündüz ve kayıt. |
| `python -m examples.gui_demo` | GUI kontrolleri. |
| `python -m examples.collect_game` | Üstten görünüşlü toplama oyunu. |
| `python -m examples.world_demo` | Tiled, kamera ve konumsal ses. |
| `python -m examples.platform_demo` | Platform fiziği ve animasyonlu autotile boyama. |
| `python -m examples.effects_demo` | Tween, zaman çizelgesi, parçacıklar ve gölgeler. |

## Belgeler

- [10 adımda Doku2D](doc/tutorials/README.md)
- [Sınıflar, metotlar ve özellikler](doc/api-reference.md)
- [Platformlar, temiz kurulum ve Nuitka](doc/build.md)
- [1.0 sürüm adayı notları](CHANGELOG.md)
- [Başlangıç ve çekirdek](doc/using.md)
- [CanvasGroup, ortam rengi, kaynaklar ve kayıt](doc/runtime.md)
- [Proje araçları ve paketleme](doc/project.md)
- [API temizliği ve geçiş notları](doc/api.md)
- [GUI](doc/gui.md)
- [Diyalog ağacı ve konuşma arayüzü](doc/dialogue.md)
- [Girdi, sprite animasyonu ve temel fizik](doc/gameplay.md)
- [TileMap, Tiled, kamera ve ses](doc/world.md)
- [Platform ve autotile](doc/platform.md)
- [Efektler ve ışık](doc/effects.md)

Motor kodu MIT lisanslıdır. Birlikte verilen Noto Sans, kendi OFL 1.1 lisansıyla
dağıtılır; `doku2d/assets/fonts/OFL.txt` dosyasına bakın.
