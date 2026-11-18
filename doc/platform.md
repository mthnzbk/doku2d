# Platform fiziği, çarpışmalar ve animasyonlu autotile

Ortak örnek: `python -m examples.platform_demo`.

- A/D, oklar veya gamepad ile yürü; Space/gamepad 0 ile zıpla.
- P/ESC duraklatır, R başlangıca döner.
- Sol tıkla zemin, sağ tıkla animasyonlu su çiz; orta tıkla hücreyi sil.
- Sürükleyerek boyayabilirsin. GUI üzerinde başlayan tıklamalar haritayı boyamaz.
- Eğimden çık, hareketli platformu kullan ve sağdaki sarı hedefe ulaş.

Harita `examples/assets/platform/platform.tmj`, tileset `terrain.tsj` içindedir;
Tiled'da doğrudan açılabilir. Kenar eşlemeleri Tiled edge Wang setlerinden,
su animasyonları Tiled tile animation verisinden yüklenir.
`--frames 120` otomatik kapanan kontrol çalıştırmasıdır.

## Karakter

```python
from doku2d import CharacterBody, Game

class Player(CharacterBody):
    def __init__(self):
        super().__init__(motion_mode="grounded", size=(20, 30))

    def physics_update(self, dt):
        x = self.input.get_axis("move_left", "move_right")
        self.velocity = (x * 240, self.velocity.y)
        if self.input.is_action_just_pressed("jump"):
            self.jump(500)
        self.move_and_slide()

game = Game()
game.physics.gravity = (0, 900)
```

Varsayılan `motion_mode="floating"` mevcut üstten görünüşlü örnekleri korur.
`grounded` seçmek `gravity_scale=1`, `floating` seçmek `gravity_scale=0` yapar;
sonradan `gravity_scale` ayrıca değiştirilebilir. Yerçekimini motor uygular;
aynı yerçekimini her karede tekrar elle eklemene gerek yoktur.
Hız piksel/saniye, açı ayarları derece cinsindendir.

`move_and_slide()` motor hızını sabit fizik adımı için hazırlar. Hareket ve
çarpışma o adımın çözücüsünde tamamlanır; `dt` ile tekrar çarpılmaz.
Durum sorguları son tamamlanan fizik adımını verir. `jump(speed)` yerdeyken
bir kez kabul edilir, bool döndürür; havadayken tekrar zıplatmaz.
`teleport(position)` hız ve temasları temizleyerek konumu değiştirir.

- `is_on_floor()`, `is_on_wall()`, `is_on_ceiling()` birbirinden bağımsızdır;
  köşede hem zemin hem duvar teması olabilir.
- `get_floor_normal()` ve `get_floor_angle()` eğimi verir.
- `get_slide_collision_count()` / `get_slide_collision(i)` fizik temaslarını verir.
- `get_real_velocity()` platform taşınması dahil gerçek konum değişimidir.
  `velocity`, platformun otomatik taşıma hızından ayrı tutulur.

`up_direction` sıfır olamaz ve normalize edilir; varsayılan `(0,-1)`.
`max_angle=45` zemin sayılacak en büyük eğimdir. `stop_on_slope=True`
hareket istenmediğinde eğimde kaymayı durdurur; kapatılırsa yerçekimiyle kayar.
`constant_speed=True` eğimde istenen yatay hız büyüklüğünü eğim boyunca korur.
`block_on_wall=True` zemin sınırından dik olan yamaçlara yürüyerek tırmanmayı
engeller. `slide_on_ceiling=False` tavana yükselirken temas hızını keser;
varsayılan True yanal kaymaya izin verir.

`snap_length=4` yerdeki karakterin küçük aşağı basamakları takip ettiği uzaklıktır.
Zıplarken snap uygulanmaz. `apply_floor_snap()` elle uygular, bool döndürür.
`safe_margin=.08` zemin probu/tutunma toleransıdır; şekil boyutunu büyütmez.
Sıfır snap, aşağı basamakta kısa bir havalanmaya izin verir.

### Hareketli platform

```python
from doku2d import AnimatableBody

class Platform(AnimatableBody):
    def physics_update(self, dt):
        self.move_to(self.position + (80 * dt, 0))
```

Konum/dönme değişikliği sabit adımda hız olarak çözülür; karakter platformla
birlikte taşınır. Sürekli hareket için `velocity` / `angular_velocity` de verilebilir.
Dönüşte temas noktasının açısal hızı hesaba katılır.
`get_platform_velocity()` mevcut temasın dünya hızını verir.

`floor_layers` (varsayılan bütün katmanlar) ve `wall_layers` (varsayılan 0)
hangi çarpışma katmanlarının taşıma hızını aktaracağını belirler; zemin algılamasını
kapatmaz. `on_leave`: `"add_velocity"`, `"add_upward_velocity"`, `"none"`.
İlki ayrılırken platform hızını devralır; ikincisi aşağı yönlü kısmı atar;
sonuncusu ek momentum aktarmaz.

Fizik Pymunk tabanlıdır. Sabit adım içinde hıza/şekil boyutuna göre alt adımlar
kullanılır; bu klasik oyun hızlarında ince engelleri kaçırmayı azaltır.
Alt adım sayısı sınırlıdır; bu sınırsız hızlı cisimler için tam CCD garantisi değildir.
Gövde sınıflarındaki etkisiz eski slope/entegratör/damp-mode/Area override alanları
kaldırıldı veya yukarıdaki çalışan davranışlara bağlandı. Genel gövde ayarları
`mass`, `gravity_scale`, `friction`, `elasticity`, `linear_damp`, `angular_damp`,
`force`, `torque`, `lock_rotation`, `freeze`, `sleeping` olarak çalışır.
Yeni `Polygon` dışbükey fizik şeklidir; `Segment` çizgi çarpışması içindir.

## Tiled çarpışmaları

```python
from doku2d import TileMap

world = game.add(TileMap.from_tiled("level.tmx", collisions=True))
world.layers["Ground"].collision_enabled = False
```

Tileset'in Tile Collision Editor'ında çizilen dikdörtgen, polygon, polyline ve
ellipse şekilleri statik gövdelere dönüşür. İçbükey polygonlar parçalara ayrılır;
ellipse 24 köşeli bir çokgenle yaklaşılır. Hücre çevirme/döndürmeleri, tile offset,
grup/katman offset'leri ve haritanın dönüşümü çarpışmaya da uygulanır.
Nesne katmanındaki tile object'ler kendi ölçek/dönüşleriyle tileset şekillerini kullanır.
Görsel animasyon kareleri fizik şeklini her karede değiştirmez; seçilen asıl
döşemenin çarpışma verisi kullanılır.

`collisions=True` tile katmanlarındaki mevcut şekilleri etkinleştirir. Nesne
katmanları için Tiled custom property `collision_enabled=true` verilebilir veya
katman adı açıkça seçilebilir:

```python
world.enable_collisions(layers=["Ground", "Collision"])
world.disable_collisions()
```

Tile katmanındaki custom property `collision_mode="solid"` her dolu hücreyi
bütün bir ızgara hücresi olarak katı yapar. Tile custom property `solid=true`
yalnızca o tile id'yi tam hücre yapar. Yan yana tam hücreler tek yüzeyde birleştirilir.
`collision_enabled=false` katman/tile/nesne seviyesinde devre dışı bırakabilir;
katman objesinin `collision_enabled` property'si runtime açma/kapamadır.
Tiled'daki `collision` bool property'si katman seviyesinde kısa ad olarak da okunur.

`collision_layer`, `collision_mask`, `friction`, `elasticity` custom property'leri
katman → tile → nesne sırasıyla uygulanır. Bunlar native fizik maskeleri ve
katsayılarıdır; `collision_layer=2` ikinci katmanı ifade eder.
Nesne katmanındaki point/text verileri çarpışmaya dönüşmez. Katmanın gizlenmesi
fiziğini kapatmaz; gizli Collision katmanları bu şekilde kullanılabilir.
Fizik katmanları `parallax=(1,1)` olmalıdır. Tek yönlü platform davranışı bu sürüme dahil değildir.

Çarpışma şekli çizilmemiş sıradan görsel tile kendiliğinden katı olmaz.
Elle tanımlanan atlas için kısa yol:

```python
tiles.set_solid(range(16))       # ilk 16 tile tam hücre çarpışması
world = TileMap(tile_set=tiles, collisions=True)
ground = world.add_layer("Ground")
```

Hücre, autotile varyantı, katman ayarı veya harita dönüşümü değişince çarpışmalar
sonraki fizik adımında yenilenir. `world.colliders` oluşan gövdeleri okumak içindir;
yenilemelerde gövde örnekleri değişebilir. Harita kaldırılınca bunlar da temizlenir.

## Idle / run / jump / fall geçişleri

```python
sprite.add_animation("idle", [0, 1], fps=4)
sprite.add_animation("run", [2, 3, 4, 5], fps=10)
sprite.add_animation("jump", [6], fps=1)
sprite.add_animation("fall", [7], fps=1)
player.sprite = sprite
sprite.follow_motion(player, run_speed=240)
```

Motor, yere basma ve hız bilgisine göre animasyonu seçer. Yön değişince `flip_h`,
koşu hızı değişince oynatma hızı güncellenir; aynı durumda her karede ilk kareye dönmez.
Özel adlar verilebilir: `follow_motion(player, run="walk", jump="rise", fall="drop")`.
Floating karakter yalnızca idle/run ister; dikey hareketin büyüklüğü de hesaba katılır.
`run_speed` animasyonun normal hızda oynadığı hareket hızıdır.

`controller = sprite.motion`, `controller.state`, `controller.enabled` ve
`controller.changed.connect(callback)` kullanılabilir; sinyal state adını verir.
Saldırı gibi elle yönetilen bir animasyon için `sprite.motion.enabled=False`
yapılabilir. `sprite.follow_motion(None)` otomatik seçimi kaldırır.
Gövdeye verilmiş sprite ayrıca `game.add` ile kaydedilmez.

## Autotile

```python
from doku2d import TileSet, TileMap

tiles = TileSet("terrain.png", tile_size=(32, 32))
tiles.add_autotile("grass", range(16))
world = TileMap(tile_set=tiles)
ground = world.add_layer("Ground")
ground.paint_terrain([(0, 0), (1, 0), (2, 0)], "grass")
ground.set_terrain((1, 1), "grass")
ground.erase_cell((1, 0))
```

`range(16)` atlasın ilk 16 tile'ının aşağıdaki maskeler sırasıyla hazırlandığını
varsayar. Farklı atlas dizilimi için `{mask: tile_id}` sözlüğü verilir.
Her boyama/silmede hücre ve çevresindeki bağlantılar otomatik yenilenir.
Boş hücre `None`'dır; tile id `0` geçerli ilk döşemedir.

| Komşu | Bit |
| --- | --- |
| Kuzey | 1 |
| Doğu | 2 |
| Güney | 4 |
| Batı | 8 |
| Kuzeydoğu | 16 |
| Güneydoğu | 32 |
| Güneybatı | 64 |
| Kuzeybatı | 128 |

Varsayılan `mode="sides"` ilk dört biti kullanır; 16 bağlantı deseni vardır.
Örneğin doğu+batı bağlı tile maskesi `2+8=10`'dur.
`mode="blob"` köşeleri de kullanır. Köşe ancak ona bitişik iki kenar bağlıysa
sayılır; klasik 47 desenli blob autotile bu normalizasyonla tanımlanabilir.

```python
tiles.add_autotile("stone", {0: 20, 3: 21, 19: 22}, mode="blob", fallback=20)
```

Tanımlanmamış bir maskede `fallback` kullanılır; verilmemişse maske 0'ın tile'ı,
o da yoksa ilk tanımlanan tile kullanılır. Kurallar hazır yönlendirilmiş tile id'leri
seçer. Ayrı terrain adları birbirine bağlanmaz. Aynı tile id'lerini birden çok
terrain'e vermek otomatik çıkarımı belirsizleştirebilir; ayrı varyantlar kullan.
`tileset=...` ile başka tileset'in terrain'i seçilebilir.

Tiled edge Wang setleri `Set/Color` adlarıyla yüklenir. Tek renkli sette `Set`
kısa adı da vardır; örnekte `"Ground"` ve `"Water"` bunlardır. Bu, ikili
komşuluk eşlemesidir; bütün çok renkli corner/mixed Wang geçiş çözücüsü değildir.
Corner/mixed setler parser verisinde korunur; runtime blob kuralları elle verilebilir.
Başlangıçtaki Tiled hücreleri kuralın tile id'lerine uyuyorsa boyanan alanın
komşuları olarak tanınır. `layer.update_terrain("Water")` mevcut hücrelerin
tamamını o kurala bağlayıp yeniler. Kuralı değiştirince `update_terrain()` ile
önceden bağlanmış hücreler yeniden seçilebilir.

## Animasyonlu autotile

Autotile'ın seçtiği tile id'ye normal bir tile animasyonu tanımlanır:

```python
tiles.add_autotile("water", range(16))
for mask in range(16):
    tiles.add_animation(mask, [mask, mask + 16, mask + 32], fps=5)

water = world.add_layer("Water")
water.paint_terrain([(4, 2), (5, 2), (5, 3)], "water")
```

Bu atlas üç satırdan, her satırda aynı 16 bağlantı varyantından oluşur.
Önce komşuluğa göre tile id seçilir, sonra onun animasyon karesi çizilir.
`durations=[.1,.2,.1]` ile karelere ayrı saniye süreleri de verilebilir.
Tiled'ın animasyon tanımları aynı sisteme çevrilir.

Animasyon haritanın ortak zamanını kullanır: komşu eklemek, silmek veya yeni
hücre boyamak animasyonu başa döndürmez. Oyun durakladığında harita animasyonu
da durur. Animasyonlu autotile da normal tile gibi çarpışma metadata'sı taşıyabilir;
çarpışma bağlantı varyantı değişince yenilenir, görsel kare değişiminde yeniden kurulmaz.
