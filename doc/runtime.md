# Canvas, ortam rengi, kaynaklar ve kayıt

Çalışan örnek: `python -m doku2d run --project examples/starter_project`.
Saat sürgüsü gece-gündüz rengini, diğer sürgü HUD grubunun saydamlığını değiştirir.
F5/Kaydet ilerlemeyi kaydeder; F9/Yükle geri getirir.

## CanvasGroup

```python
from doku2d import CanvasGroup, Panel, Label

group = game.add(CanvasGroup(canvas=game.ui.canvas))
group.position = (24, 18)
panel = group.add(Panel())
panel.size = (400, 90)
label = group.add(Label(text="Merhaba"))
label.position = (16, 16)
group.opacity = .5
```

Görseller önce tek saydam yüzeyde birleşir; `opacity` ve `color` o sonuca bir kez
uygulanır. Üst üste binen parçalar tek tek yarı saydam çizilmiş gibi koyulaşmaz.
Üyeler normal Game nesneleridir; yeni bir SceneTree/Node/parent API'si yoktur.
Üyeleri ayrıca game.add ile eklemek gerekmez. Grubun konum/dönüş/ölçeği üyelerin
yerel dönüşümüne uygulanır. Üyeler aynı Canvas'ı paylaşır ve kendi içlerinde
z_index ile sıralanır; grubun z_index değeri bütün yüzeyin dış sırasıdır.

`group.members` salt okunur tuple, `remove(member)` gruptan ayırma,
`remove(member, free=True)` ayrıca oyundan kaldırmadır. Ayırma yerel koordinatları
korur. Grup kaldırılınca kaydettiği üyeler de kaldırılır. `visible=False` üyeleri
çizimden ve GUI hedeflemesinden çıkarır; yalnızca opacity=0 yapmak girdi kapatmaz.
`member_added(member)` / `member_removed(member)` sinyalleri vardır.

Gruplar bağımsız görseller içindir. İç içe grup, fizik gövdesi, harita, ışık veya
ses nesnesi gruba eklenmez. Fizik yerleşimini grup dönüşümüyle görselden ayırıp
bozmamak için bu durumlar açık hata verir. Popuplar ayrı UI katmanında çizilir.
Yüzey pencere boyutunda önbelleklenir ve yeniden boyutlandırmada yenilenir;
eski etkisiz fit_margin/clear_margin/use_mipmaps ayarları kaldırıldı.

## AmbientLight ve DayNightCycle

`AmbientLight`, eski `CanvasModulate` adının açıklayıcı karşılığıdır; iki ad da aynı
sınıfı gösterir. Ortam rengini aynı Canvas içindeki görsellere uygular. Varsayılan
world üzerindeki ortam, ekran Canvas'ındaki HUD'ı etkilemez.

```python
from doku2d import AmbientLight, DayNightCycle

ambient = game.add(AmbientLight(color=(45, 55, 80)))
# Basit bir geçiş:
t = ambient.create_tween()
t.tween_property(ambient, "color", (255, 255, 255), 3)
```

Doğrudan gece-gündüz döngüsü için ayrı AmbientLight eklemek gerekmez:

```python
cycle = game.add(DayNightCycle(day_length=180, time=8))
cycle.time = 23       # saat, 0–24 aralığına sarılır
cycle.day_length = 90 # gerçek saniye / oyun günü
cycle.pause()
cycle.resume()
```

Gece, şafak, gündüz ve gün batımı renkleri hazırdır. `colors` ile değiştirilebilir:

```python
cycle.colors = [(0, (25, 35, 65)), (6, (220, 160, 130)),
                (12, (255, 255, 255)), (18, (220, 145, 110)),
                (24, (25, 35, 65))]
```

Saatler benzersiz olmalı, 0 ve 24 bulunmalı ve bu iki renk eşit olmalıdır.
Geçişler lineerdir. `day` tamamlanan gün sayısı, `speed_scale` hız çarpanı,
`playing` oynatma durumudur. `phase`: night/dawn/day/dusk.
`time_changed(hour)`, `day_changed(day)`, `phase_changed(phase)` sinyalleri vardır.
`enabled=False` renk etkisini kapatır; saati durdurmak için pause kullanılır.
Varsayılan olarak oyun duraklayınca döngü de durur. `process_mode="always"`
olduğunda duraklamada da devam eder.

Aynı Canvas'a birden fazla ortam rengi eklenirse renkler çarpılır. Gündüz-gece
ışığını tekrar çarpmak istemiyorsan tek DayNightCycle kullan.

## Kaynak yönetimi

Her Game kendi `Resources` nesnesini taşır; `Resource` eski uyumluluk adıdır.

```python
game = Game(project_root=project_dir, asset_root="assets")
texture = game.resources.get_texture("res://hero.png")
font = game.resources.get_font("fonts/ui.ttf")
sound = game.resources.get_sound("click.wav")
world = game.add(game.resources.load_map("level.tmj", collisions=True))
```

Normal göreli yollar ve res://, asset_root'a göre çözülür. Mutlak yollar da kabul
edilir. `resolve(path)` çözülen yolu verir. Aynı dosya için Texture/Font/SoundBuffer
önbellekte paylaşılır; oyuncunun çalma durumu veya TileMap hücreleri paylaşılmaz.
`get_map` önbellekteki parser verisinin kopyasını, `load_map` yeni bir TileMap'i
verir. Haritalar aynı atlas dokusunu kullanır. Tiled görsel yolları ilgili TMX/TSX
konumuna göre çözülmeye devam eder.

Sprite/AnimatedSprite yol girdileri Game'e eklenince bu cache'e bağlanır:

```python
sprite = Sprite("res://hero.png")
game.add(sprite)
```

Kaydı yapılmadan önce doku None olabilir. Bir fizik gövdesinin sprite'ı da otomatik
bağlanır. Kayıttan önce boyut/kare doğrulaması gerekiyorsa `resources=game.resources`
constructor parametresi veya önceden yüklenmiş Texture verilebilir.
TileSet/TileMap da resources parametresi kabul eder. Harita dosyasının yolunu Game
asset kökünden çözmek için `resources.load_map` veya
`TileMap.from_tiled(path, resources=game.resources)` kullan.

Partikül ve PointLight özel dokuları da kayıtta cache'e bağlanır. Native Texture
vermek her zaman mümkündür. GUI'nin varsayılan Noto Sans fontu motorla ve OFL
lisansıyla gelir; sistem fontuna bağımlı değildir ve aynı cache üzerinden yüklenir.

`get_text`, `get_json`, `preload(*paths)`, `unload(path)`, `clear()` ve `cache_info`
vardır. JSON/map sonuçları bağımsız kopyalardır. Unload, halen kullanılan Texture
örneklerini bozmaz; sonraki yüklemede yeni örnek oluşturur. Game kapanınca cache
temizlenir. Uzun müziklerin stream oynatımı ayrı ses örnekleri kullanır.

## Kayıt ve ayarlar

```python
game.saves.save("slot1", {"version": 1, "score": 12,
                          "position": list(player.position),
                          "hour": cycle.time, "day": cycle.day})
data = game.saves.load("slot1", default={"score": 0})
```

SaveStore JSON slotları kullanır. Önce geçici dosya yazılıp flush/fsync yapılır,
sonra aynı dizinde atomik replace uygulanır. Geçersiz veri eski kaydı değiştirmez.
Bozuk JSON `SaveError` verir; eksik dosya default değerini döndürür.
`exists`, `list_slots`, `delete` de vardır. Slot adı harf/rakam/alt çizgi/tire olabilir;
dizin geçişi kabul edilmez. Native motor nesneleri yerine JSON verisi kaydet.
Sürüm/migration şeması oyunun sorumluluğudur; örnek version alanını kontrol eder.

```python
game.settings["music_volume"] = 65
game.settings["controls"] = {"jump": "space"}
game.settings.save()  # veya Game kapanırken otomatik flush
```

Settings bir MutableMapping'dir; iç içe sözlük değişiklikleri de kapanışta fark edilir.
Sadece okumak yeni dosya oluşturmaz. Geçerli ayar verileri settings.json'a yazılır.
İlerleme slotlarını settings'ten ayrı tut.

Varsayılan klasör uygulama app_id'sine göre kullanıcı veri dizinindedir:
Windows LocalAppData, macOS Application Support, Linux XDG_DATA_HOME veya
~/.local/share altında doku2d/app_id. `game.saves.root` gerçek klasörü verir.
`Game(save_dir=...)` ile açık klasör seçilebilir. Yol göreliyse project_root'a göredir.
Örneğin yerel .user-data klasörü kullanır; oluşturulan yeni şablon varsayılan OS
kullanıcı dizinini kullanır. Kayıt dosyaları dağıtım ZIP'ine alınmaz.


## Bölüm ömrü ve mantıksal çözünürlük

`EntityScope` bir bölümün nesnelerini ve bağlantılarını birlikte toplar. Aynı anda
birden fazla kapsam açık olabilir.

```python
level = game.create_scope()
level.add(tile_map)
level.add(player)
level.connect(player.defeated, on_defeat)
level.defer(start_wave)
# Bölümden çıkarken:
level.close()
```

Kapsamdaki bir nesnenin ekleme, güncelleme veya olay işleme kodu `game.add`
çağırırsa yeni nesne aynı kapsama girer. Dışarıdan eklerken `level.add` kullan.
Kapanış bekleyen nesneleri ve gecikmeli işleri iptal eder, `level.connect` ile
kurulan bağlantıları koparır ve kayıtlı üyeleri kaldırır. Oyun boyunca kalacak
nesneleri kapsam dışına ekle veya `persistent=True` kullan. `game.replace`
başarılı olduğunda giden kapsamlar da kapanır.

```python
game = Game(size=(320, 180), window_size=(960, 540), scale_mode="fit")
world_point = game.window_to_world(mouse_pixel)
if world_point is not None:
    tile = tile_map.world_to_map(world_point)
```

`size` oyun ve arayüzün çizim çözünürlüğüdür. `window_size` fiziksel pencere
boyutudur. `fit` en-boy oranını korur ve boş kenar bırakır. `integer` yeterli
alan varsa tam sayı katıyla büyütür, küçük pencerelerde orantılı küçültür.
`stretch` pencereyi doldurur. `window_to_screen` mantıksal ekran noktasını,
`window_to_world` kamera dönüşümü uygulanmış dünya noktasını verir. Boş kenarda
ikisi de `None` döndürür. Ters yönde `screen_to_window` ve `world_to_window`
kullanılır. Dünya dönüşümlerine isteğe bağlı `canvas` verilebilir.

TileMap görünür parçaların çizim verisini saklar. Animasyon karesi değiştiğinde
ilgili görünür parçalar yenilenir. Yalnızca ortam rengi kullanılan Canvas, ışık
biriktirme yüzeyine ihtiyaç duymaz.

## Motorun debug katmanı

```python
from doku2d import Game, Key

game = Game(debug=True)                 # F3 ile aç/kapat
game.debug.key = Key.F8                 # F3 artık oyuna ait
game.debug.show_collisions = False      # İsteğe bağlı görünüm seçenekleri
```

Debug varsayılan olarak kapalıdır. Açıldığında katman FPS, kare aralığı,
nesne sayısı ve çizilen TileMap parça sayısını gösterir. Fizik şekillerini,
kamera sınırlarını ve çizilen karo parçalarını da işaretler. `show_stats`,
`show_collisions`, `show_camera` ve `show_chunks` ayrı ayrı değiştirilebilir.

F3 ayrıca son çizilen karedeki fizik, oyun güncellemesi, çizim ve A* sürelerini
milisaniye olarak gösterir. Bunlar CPU süreleridir. A* fizik veya güncelleme
içinden çağrıldığında kendi satırında sayılır. Yanındaki sayı o karedeki yol
sorgusu sayısıdır. Koddan `game.debug.profile_ms` ve `game.debug.path_queries`
ile okunabilir. `game.debug.show_profile = False` süre toplamayı da kapatır.

Yerleşik kısayolu `game.debug.key = None` ile kapatıp kendi olay kodundan
`game.debug.toggle()` çağırabilirsin. Bu çağrı da debug modu kapalıyken katmanı
açmaz. Proje dosyasından etkinleştirmek için:

```toml
[debug]
enabled = true
key = "F8"  # Atlanırsa F3; false verilirse yerleşik kısayol yok.
```

## Oyuncu ayarlarını saklama

```python
from doku2d import Game, JoyButton, Key

game = Game(persist_preferences=True)
game.input.bind('interact', Key.E)                       # Oyun varsayılanı
game.input.set_bindings('interact', Key.F, JoyButton(2)) # Oyuncu seçimi
game.input.joy_deadzone = 0.25
game.audio['Music'].volume = 60
game.audio['SFX'].muted = True
```

`get_bindings(action)` arayüzde göstermek için etkin atamaları verir.
`set_bindings(action)` atamayı boş bırakır. Oyuncu seçimi sonraki açılışta,
oyun aynı eyleme `bind` ile varsayılan tuşunu verse de korunur. `JoyAxis` için
ayrı bir `deadzone` verirsen o bağlantı kendi değerini kullanır.

Tercihler normal kapanışta diğer `game.settings` değerleriyle birlikte yazılır.
Bir ayar menüsündeki Uygula düğmesinden hemen kaydetmek için
`game.settings.save()` çağırabilirsin. Özel ses gruplarının seviyeleri de sonraki
açılışta aynı adla `add_bus` çağırınca uygulanır.

`Game.from_project()` kullanıyorsan proje dosyasından da etkinleştirebilirsin:

```toml
[preferences]
persist = true
```
