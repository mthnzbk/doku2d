# Platformlar ve derleme

| Ortam | 1.0 sürüm adayının kapsamı |
| --- | --- |
| Windows x64 | Birincil hedef. Python 3.13 ile temiz kurulum, başlangıç oyunu ve Nuitka çıktısı çalıştırıldı. GitHub iş akışı 3.11–3.13 sürümlerini kapsar. |
| Linux x86-64 | Önizleme. Ubuntu 24.04 / WSLg, Python 3.12 ile temiz kurulum, başlangıç oyunu ve Nuitka çıktısı çalıştırıldı. Yerel Linux masaüstü ayrıca doğrulanmalı. |
| macOS | Doğrulama bekliyor. Kullanılan SFML sürümünün hazır macOS paketi Apple Silicon ve macOS 15+ içindir. |
| Android, iOS ve web | 1.0 kapsamı dışında. |

Yukarıdaki hazır paket kapsamı [SFML 3.0.2.0 dağıtım dosyalarına](https://pypi.org/project/SFML/3.0.2.0/#files) dayanır.

Shader desteği bulunmayan grafik ortamlarında başlangıç oyunu, ortam rengi
ve CanvasGroup saydamlığıyla çalışır. Dinamik ışıklar ve gölgeler bu durumda
çizilmez. Kendi GLSL materyallerini kullanan oyunlar OpenGL shader desteği ister.

## Projeyi derle

Motor deposunun kökünde derleme seçeneğini kur. Motoru wheel dosyasından
kurduysan aynı Python ortamına `python -m pip install nuitka` ile Nuitka ekle.

```sh
python -m pip install -e ".[build]"
doku2d create benim_oyunum
cd benim_oyunum
doku2d build
```

- **Windows:** Çalıştırılabilir dosya `dist/<app_id>.dist/<app_id>.exe`.
- **Linux:** Çalıştırılabilir dosya `dist/<app_id>.dist/<app_id>.bin`.

Oyunu paylaşırken `.dist` klasörünün tamamını ver. Her işletim sistemi için
derlemeyi o işletim sisteminde yap. İlk Windows derlemesinde Nuitka derleyici veya
yardımcı araç indirmek için onay isteyebilir. Otomatik doğrulamada bu indirmelere
`DOKU2D_BUILD_DOWNLOAD_TOOLS=1` ile izin verilebilir.

## Ubuntu 24.04 ve WSLg

Bir grafik oturumu gerekir. WSLg kullanıyorsan doğrulamayı dağıtımın Linux
terminalinde çalıştır. Ubuntu'da Python sanal ortamları, SFML için X11/OpenGL
kitaplıkları ve derleme araçları şu şekilde kurulabilir.

```sh
sudo apt install python3-venv build-essential patchelf libxrender1 libxrandr2 libxcursor1 libxi6 libudev1 libgl1-mesa-dri libglx-mesa0 libopengl0
python3 -m venv .venv-linux
. .venv-linux/bin/activate
python -m pip install -e ".[build]"
```

Windows ve Linux sanal ortamlarını ayrı tut. Derleme ve doğrulama çıktıları için
Linux dosya sistemindeki bir dizini `--output` ile seçebilirsin.

Linux'ta derlenmiş oyun da sistemin grafik kitaplıklarını kullanır. WSL
doğrulamasında `libXrender.so.1` mevcutken oyun açıldı. Dağıtım yapılacak
Ubuntu sisteminde bunun karşılığı `libxrender1` paketidir.

## Sürüm paketini doğrula

```sh
python tools/release_check.py
python tools/release_check.py --native --download-tools
```

İlk komut wheel oluşturur, temiz bir Python ortamına kurar ve `create` ile
oluşturduğu oyunu `run` ile açar. Ardından pencere oranını, puan ve kayıt/yükleme
akışını ve bölüm değişimini doğrular. İkinci komut ayrıca `build` çıktısını proje
dizininin dışından açar. Yalnızca mevcut paketi denemek için `--wheel DOSYA`,
paket üstünde motorun test takımını çalıştırmak için `--tests` kullanılabilir.

Grafik oturumu bulunmayan bir Ubuntu çalıştırıcısında `xvfb` ve `xauth` kurup
doğrulama komutunun başına `xvfb-run -a` ekle. [Sürüm notları](../CHANGELOG.md)

## PyPI yayımlama

Yayımlama iş akışını `v<version>` biçimindeki Git etiketi başlatır. Örneğin
`v1.0.0rc1` etiketi, `pyproject.toml` içinde `1.0.0rc1` sürümünün bulunduğu
commit'i göstermelidir. Etiketle paket sürümü farklıysa derleme başlamaz.
Etiketli yayım, Windows ve Linux üzerinde temiz kurulum ve bağımsız uygulama
kontrolleri geçtikten sonra paketi PyPI'ye gönderir. GitHub Release açıklaması
ayrıca yayımlanabilir.
