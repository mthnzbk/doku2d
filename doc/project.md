# Proje akışı ve paketleme

Motor deposunda `python -m pip install -e .` ile CLI'yi kullandığın Python ortamına
kur. Derleme de alacaksan `python -m pip install -e ".[build]"` kullan.

```sh
python -m doku2d create oyun
cd oyun
python -m doku2d run
python -m doku2d build
```

Create yalnızca boş/yeni klasöre yazar. Hazır dosyaları ezmez. Şablonun main.py'si,
assets/ içindeki düzenlenebilir Tiled haritası ve sprite'ı, doku2d.toml ayarları,
pyproject.toml ve README'si birlikte oluşturulur.

Şablonda WASD/oklar hareket, F5 kaydet, F9 yüklemedir. Işıkları toplayınca skor
artar. Saat sürgüsü DayNightCycle'ı, saydamlık sürgüsü CanvasGroup HUD'ı yönetir.
Kaydet/Yükle düğmeleri de vardır. Kullanıcı saati Settings üzerinden kapanışta
saklanır; oyun ilerlemesi ayrı slot1 kaydıdır.

## Ayarlar

```toml
[game]
name = "Benim Oyunum"
app_id = "benim-oyunum"
entry = "main.py"

[window]
width = 960
height = 640
initial_width = 1200
initial_height = 800
scale_mode = "fit"
fps_limit = 60
physics_fps = 60

[assets]
directory = "assets"

[ui]
theme = "assets/theme.toml"  # isteğe bağlı

[build]
directory = "dist"
```

`Game.from_project(Path(__file__).with_name("doku2d.toml"))` aynı ayarları ve yolları
yükler. Çalışma dizininin değişmesine bağlı değildir. CLI, `--project <klasör veya
toml>` kabul eder. Eski project_settings.toml dosyaları klasör üzerinden verildiğinde
okunabilir; yeni şablon yalnızca doku2d.toml üretir.

Varsayılan kayıt klasörü OS kullanıcı dizinidir. Açık bir yerel klasör için:

```toml
[storage]
directory = ".user-data"
```

Ayar dosyasındaki entry/assets/build/storage yolları proje içinde kalır. Assets ve
build dizinleri iç içe olamaz. Runtime'da Game constructor ile save_dir farklı bir
mutlak kullanıcı klasörüne ayrıca yönlendirilebilir.

## Çalıştırma

`run`, aynı Python ortamında yeni bir işlemde entry dosyasını proje klasöründen
çalıştırır ve çıkış kodunu aktarır. Geliştirme ortamındaki motor yolu korunur;
proje modülleri kendi kökünden bulunur.
`python -m doku2d run --frames 2` şablonu sınırlı kare sayısıyla çalıştırır.
Kendi entry dosyan da --frames argümanını desteklemelidir.

## Derleme

```sh
doku2d build
```

Motoru bulunduğu Python ortamına kurmadan çalışıyorsan `python -m doku2d build`
kullanabilirsin. Komut, Nuitka ile oyunu hedef işletim sistemi için derler. Ayar,
varlıklar ve motor verileri pakete katılır. Windows'ta çıktı
`dist/<app_id>.dist/<app_id>.exe` olur. Dağıtırken `.dist` klasörünün tamamını paylaş.

Yeni derleme başarısız olursa önceki uygulama yerinde kalır. İlk derlemede Nuitka
gerekli araçları indirmek için terminalde onay isteyebilir. Nuitka ve uyumlu bir C
derleyicisi gerekir. [Nuitka gereksinimleri](https://nuitka.net/user-documentation/user-manual.html)
