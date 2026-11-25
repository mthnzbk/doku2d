# Proje akışı ve paketleme

Motor deposunda `python -m pip install -e .` ile CLI'yi kullandığın Python ortamına
kur. Derleme de alacaksan `python -m pip install -e ".[build]"` kullan.

Motor deposunun kök dizininden `./Scripts/doku2d --help` çalıştırabilirsin.
`Scripts` dizinindeysen komut `./doku2d` olur. Windows başlatıcısını
`./Scripts/doku2d.cmd` ile de doğrudan çağırabilirsin. Başlatıcı varsa
deponun `.venv` ortamını kullanır. Kurulu paketin komutu `doku2d` olur.

```sh
python -m doku2d create oyun
cd oyun
python -m doku2d run
python -m doku2d build
```

## PNG klasöründen sprite atlası

```sh
./Scripts/doku2d atlas examples/assets/portraits --output build/portraits.json
```

Komut bir JSON ve aynı adlı PNG üretir. Sprite adları, uzantısı çıkarılmış
göreli dosya yollarıdır. Örneğin `portraits.json` ile
`SpriteAtlas.from_file(path)["keeper"]` aynı dokudaki bir bölgeyi verir.
Atlası galeri içindeki **Girdi, ses ve araçlar** ekranında da üretebilirsin.

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
icon = "assets/icon.png"
scale_mode = "fit"
fps_limit = 60
vsync = false
physics_fps = 60
physics_interpolation = false

[assets]
directory = "assets"

[ui]
theme = "assets/theme.toml"  # isteğe bağlı

[build]
directory = "dist"
icon = "assets/icon.ico"
```

`doku2d create` yeni projelere Doku2D simgesini iki biçimde ekler.
`window.icon` pencere simgesini, `build.icon` Windows yürütülebilir
dosyasına gömülen ICO'yu seçer. Kendi simgen için dosyaları değiştirebilir
veya proje içindeki başka yolları kullanabilirsin. `Game()` de varsayılan
olarak Doku2D simgesini kullanır.

`Game.from_project(Path(__file__).with_name("doku2d.toml"))` aynı ayarları ve yolları
yükler. Çalışma dizininin değişmesine bağlı değildir. CLI, `--project <klasör veya
toml>` kabul eder. Eski project_settings.toml dosyaları klasör üzerinden verildiğinde
okunabilir; yeni şablon yalnızca doku2d.toml üretir.

`vsync = true` kare sunumunu ekranın yenilemesine eşler. Bu moddayken yazılımsal
`fps_limit` devreden çıkar. Çalışma sırasında `game.vsync` ile kapatırsan
ayarlı FPS sınırı yeniden uygulanır. `physics_fps` fizik adım hızını yönetir.

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

Temiz wheel kurulumu, başlangıç oyununun kontrolü ve derlenen uygulamayı denemek
için [platform ve sürüm doğrulama rehberine](build.md) bak.
# Android

Proje dizininde `doku2d build android` komutu ARM64 telefonlar için
`dist/android/` altında bir debug APK üretir. x86‑64 emülatörü için
`doku2d build android --abi x86_64` kullanın. `--project` proje dizinini
veya doğrudan `doku2d.toml` dosyasını seçer.

Android betiği Python 3.11 veya üzeriyle doğrudan çalışır.
Motor kaynaklarını veya kurulu paketi içeren dizinden
`python doku2d/android/build_android.py --project PROJE` komutunu verin.

- Windows’ta WSL2 üzerinde Ubuntu 24.04 gerekir. Mevcut `KoraAndroidBuild`
  dağıtımı varsa betik onu kullanır. `DOKU2D_ANDROID_WSL_DISTRO` ile başka
  bir dağıtım seçilebilir.
- x86‑64 Linux ve WSL Ubuntu’da C/C++ derleyicileri, Java 17 ve aşağıdaki
  paketler gerekir.
- macOS ve ARM Linux’ta Docker çalışır durumda olmalıdır. Betik Linux
  x86‑64 derleme ortamını oluşturur ve araçları Docker biriminde saklar.

```bash
sudo apt install build-essential ca-certificates cmake curl git libbz2-dev \
    libffi-dev liblzma-dev libreadline-dev libsqlite3-dev libssl-dev ninja-build \
    openjdk-17-jdk-headless pkg-config python3 python3-venv unzip xz-utils zlib1g-dev
```

İlk derleme SDK, NDK, Gradle ve motor bağımlılıklarını indirir. SDK
lisansını kabul etmek için ilk derlemeyi etkileşimli terminalde çalıştırın.
Çıktı debug anahtarıyla imzalanır ve Android 7.0 veya üzeri cihazlara
test amaçlı kurulabilir.

Android ayarları isteğe bağlıdır. Motorun giriş dosyası, varlık klasörü,
çeviri dosyaları ve tema otomatik paketlenir. Bunların dışındaki veri
dosyalarını `include` ile ekleyin.

```toml
[android]
application_id = "org.ornek.oyun"
orientation = "landscape"
version_code = 1
version_name = "0.1.0"
include = ["maps", "data/quests.json"]
```

## Projeye özel Android dosyaları

İlk `doku2d build android` çağrısında proje kökünde iki düzenlenebilir dosya
oluşur. Komut var olan dosyaları korur ve her derlemede güncel hâllerini okur.

- `android/AndroidManifest.xml` Android izinleri, uygulama nitelikleri ve
  bağlantı filtreleri içindir. Yorum satırındaki internet izni örneğini
  açarak oyuna internet erişimi ekleyebilirsin.
- `android/res/values/strings.xml` Android’in kullandığı metinler içindir.
  Örneğin manifestteki `app_name` örneğini etkinleştirip
  `android/res/values-tr/strings.xml` ekleyerek uygulama adını
  yerelleştirebilirsin. `android/res/` altındaki diğer geçerli Android
  kaynakları da derlemeye girer. `android/res/mipmap-xxhdpi/ic_launcher.png`
  eklersen Android başlatıcı ikonu olarak o dosya kullanılır.

Gradle proje manifestini motorun manifestiyle birleştirir. Mevcut bir
niteliği değiştirmek için gerektiğinde `tools:replace` kullan.
Uygulama kimliği ve sürüm ayarları `doku2d.toml` üzerinden yönetilir.

## Telefonda veya emülatörde çalıştırma

`doku2d run android` bağlı cihazın işlemci türünü algılar, APK’yı derler,
uygulamayı kurup açar ve oyunun Android günlüklerini terminale getirir.
Oyunu açık bırakıp günlük takibini sonlandırmak için Ctrl+C kullan.

```sh
doku2d run android --project oyun
doku2d run android --project oyun --device emulator-5554
```

Tek cihaz bağlıysa otomatik seçilir. Birden fazla seçenek varsa terminalde
cihazı seçebilir veya `--device` ile seri numarasını verebilirsin.
Fiziksel telefonda USB hata ayıklamayı aç ve bağlantıyı telefondan onayla.
Komut ADB’yi PATH, Android SDK ve desteklenen yerel derleme önbelleklerinde
arar. Windows’ta USB ile bağlanan telefon için Windows Android SDK
Platform-Tools kullanılabilir. macOS’ta ADB ana sistemde çalışır.

Android’de düzenlenebilir `LineEdit` ve `TextEdit` alanları odağı aldığında
sistem klavyesi açılır. `LineEdit` klavyedeki Bitti tuşuyla
`text_submitted` sinyali gönderir. `TextEdit` Enter ile yeni satır ekler.
Şifre görünümü etkin `LineEdit` alanlarında şifre klavyesi açılır.
Klavye açıldığında oyun görünümü ekranda kalan alana sığar.
