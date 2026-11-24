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
        super().__init__(motion_mode="grounded", size=(20, 30),
                         coyote_time=0.10, jump_buffer=0.12)

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
Durum sorguları son tamamlanan fizik adımını verir. `jump(speed)` zıplamayı
hemen başlatırsa `True` döner. İstek havada tamponlanırsa dönüş değeri
`False` olur ve süre dolmadan zemin teması gerçekleşirse motor zıplamayı uygular.

`coyote_time`, platform kenarından çıktıktan sonra zıplamanın kabul edildiği
süredir. `jump_buffer`, havada basılan zıplama tuşunun yere inene kadar kaç
saniye hatırlanacağını belirler. İkisi de varsayılan olarak `0` değerindedir.
`teleport(position)` hız, temas ve bekleyen zıplamayı temizler.
`drop_through()` başarıyla çalıştığında kenar hakkını ve bekleyen isteği iptal eder.

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

## Fizik interpolasyonu

`Game(physics_interpolation=True)` seçeneği, sabit fizik adımları arasında
çizilen konum ve dönüşü yumuşatır. `Game.from_project()` kullanan projelerde
aynı ayarı `doku2d.toml` üzerinden açabilirsin.

```toml
[window]
physics_fps = 60
physics_interpolation = true
```

Özellik varsayılan olarak kapalıdır. Açıldığında çizim, son iki fizik adımı
arasında ilerler ve bu yüzden fiziğin en fazla bir adım gerisindedir.
`position`, `rotation`, `transform` ve fizik sorguları tamamlanan son adımın
değerlerini verir. Özel çizimde `render_position`, `render_rotation` ve
`render_transform` üzerinden ara konumu okuyabilirsin.

Kamera bir fizik gövdesini takip ettiğinde onun çizilen konumunu izler.
Gövdeye bağlı ışıklar ve gölgeler de aynı ara dönüşümü kullanır. Hareketli
platformu interpolasyona dahil etmek için `move_to()` çağrısını
`physics_update()` içinde yap.

`CharacterBody.teleport()` geçişi sıfırlar. Fizik adımı dışında doğrudan
verilen konum ve dönüş de ekrana hemen yansır. Fizik adımı içindeki özel bir
ışınlanmadan sonra `body.reset_physics_interpolation()` çağırabilirsin.
Kameranın kendi takip yumuşatmasını da sıfırlamak için
`camera.reset_smoothing()` kullan.

## ShapeCast

`game.physics.shapecast()` bir daireyi veya kutuyu başlangıç noktasından bitiş
noktasına doğru süpürür. Örneğin duvarın önünde duran karakterin atılabileceği
mesafeyi ölçmek için gövde boyutuna yakın bir kutu kullanabilirsin.

```python
from doku2d import Circle, ShapeCast
from doku2d.physics import Box

start = player.position
hit = game.physics.shapecast(Box((20, 28)), start, start + (96, 0),
                            mask=1, exclude=(player,))
if hit:
    print(hit.collider, hit.point, hit.normal, hit.distance)

probe = game.add(ShapeCast(Circle(8), target=player, target_position=(64, 0)))
```

Sonuç ilk teması verir. `fraction` yolun 0–1 arasındaki oranıdır ve `distance`
şekil merkezinin temasa kadar gittiği mesafedir. Başlangıçta örtüşme varsa her
ikisi de `0` olur. Başlangıç ile bitişi aynı verirsen yalnızca örtüşmeyi
sorgularsın. Sorgu dünya koordinatları kullanır ve kutuyu `rotation` ile derece
cinsinden yönlendirebilirsin. Bir süpürme boyunca yön sabit kalır.

`ShapeCast` nesnesi her güncellemede sonucu yeniler. `target` verilirse nesnenin
yerel konumu ve yönü takip edilir, hedefin kendi gövdesi sorgudan çıkarılır.
Şekil boyutları dünya birimidir. Aynı karede güncel sonucu almak için
`probe.force_update()` çağırabilirsin.

`mask`, taranacak çarpışma katmanlarını seçer. Alanları dahil etmek için
doğrudan sorguda `areas=True`, nesnede `include_areas=True` kullan.
Tek yönlü platformlar sorguda yüzey olarak görünür. Geçiş kuralını karakterin
fizik hareketi uygular.

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
Fizik katmanları `parallax=(1,1)` olmalıdır.

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
## Tek yönlü platformlar

```python
from doku2d import StaticBody

game.add(StaticBody(position=(320, 160), size=(144, 12), one_way=True))
```

`one_way=True` üst yüzeyi destek olarak kullanır. Karakter aşağıdan veya
yandan geçebilir. Hareketli yüzey için aynı seçeneği `AnimatableBody` üzerinde
kullanabilirsin.

Bir `grounded` karakterin fizik güncellemesinde aşağı ve zıpla girdilerini
`drop_through()` ile bağlayabilirsin:

```python
if self.input.is_action_just_pressed('jump'):
    if not (self.input.is_action_pressed('move_down') and self.drop_through()):
        self.jump()
```

`drop_through()` yalnızca karakter tek yönlü bir yüzeyde duruyorsa `True`
döner. Varsayılan olarak 0,2 fizik saniyesi boyunca tek yönlü yüzeyleri
yoksayar. `duration` ile süreyi değiştirebilirsin. Normal zeminler bu sırada
da çarpışmaya devam eder.

Tiled’da bir nesne katmanına, çarpışma nesnesine veya karoya boolean
`one_way=true` ekle. Tek bir nesneyi işaretliyorsan nesne katmanında
`collision=true` kullan. Katmanın tamamı tek yönlüyse katmana `one_way=true`
vermen yeterlidir. Aynı katmandaki bir nesnenin `one_way=false` değeri katman
ayarını geçersiz kılar. Çarpışma geometrisi olmayan işaretli karoların üst
kenarı platform yüzeyi olur.
