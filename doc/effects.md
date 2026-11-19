# Tween, AnimationPlayer, parçacıklar ve ışık

Ortak örnek: `python -m examples.effects_demo`.
WASD/oklar veya gamepad ile odada yürü; Space kıvılcım oluşturur, P/ESC duraklatır.
Kontrollerden gölgeleri, yağmuru ve aydınlatmayı açıp kapatabilirsin. Çizelge hızı
ayrı ayarlanır. Işık Tween ile, sandık AnimationPlayer ile hareket eder.

## Tween

```python
tween = self.create_tween()
tween.tween_property(self, "position", (500, 200), 1, ease="out_cubic")
tween.parallel().tween_property(self, "scale", (1.5, 1.5), 1)
tween.tween_interval(.2)
tween.tween_callback(self.arrived)
```

`Entity.create_tween()` nesnenin oyununa kaydeder ve ona bağlar.
`game.create_tween()` bağımsız tween oluşturur. Nesne kaldırılınca bağlı tween
kesilir; normal tamamlanmada tween otomatik kaldırılır. Yeniden kullanmak için
kaldırılmadan önce `tween.auto_remove=False` ayarla.
Otomatik kaldırılmış veya öldürülmüş tween yerine yeni bir tween oluştur.

Adımlar varsayılan sıralıdır. `parallel()` sonraki adımı mevcut adımla birlikte
başlatır. `set_parallel(True)` varsayılanı paralel yapar; `chain()` yeni bir grup açar.
Paralel grup en uzun adımı tamamlanınca biter.

```python
tween = game.create_tween().set_loops()  # sonsuz; set_loops(3) toplam üç tur
tween.tween_property(lamp, "energy", 1.8, .8, ease="in_out_sine")
tween.tween_property(lamp, "energy", .7, .8, ease="in_out_sine")
```

`tween_property` bir `PropertyTweener` döndürür:
`set_delay(seconds)`, `set_ease(name)`, `from_(value)`, `from_current()` ve
`as_relative()` ile ayarlanabilir. Başlangıç değeri adım gerçekten başlayınca
okunur; döngüler aynı yakalanmış başlangıç değerlerini kullanır, kendiliğinden
birikmez. `as_relative()` hedefi başlangıç değerine ekler.

Sayı, Vector2, eşit uzunluklu sayısal tuple/list ve Color geçişleri desteklenir.
`"position:x"` / `"position.x"` gibi alt özellikler de yazılabilir; kopya döndüren
Vector2 property'leri kök nesneye geri atanır. Bool gibi diğer değerler adım
sonunda değiştirilir. Easing overshoot yaparsa sayısal setter'ın sınırları da geçerlidir.

Easing adları: `linear`, `in_sine`, `out_sine`, `in_out_sine`; aynı in/out/in_out
önekleriyle `quad`, `cubic`, `quart`, `quint`, `expo`, `back`, `bounce`, `elastic`.
Özel callable da verilebilir. `tween.set_ease(...)` sonraki adımların varsayılanıdır.

`pause()`, `play()`, `stop()`, `restart()`, `kill()` ve `speed_scale` vardır.
`stop()` başa döner ama hedef özelliklerini anında geri yazmaz; `play()` yeniden
ilerletir. `kill()` iptal eder ve kaldırır; `finished` yaymaz.
`finished()`, `step_finished(index)` ve `loop_finished(completed_loops)` sinyalleri
vardır. Sonsuz döngü sıfır süreli olamaz.
Tween kare güncellemesinde ilerler; varsayılan olarak oyunla duraklar. Bağlı tween,
sahibinin `process_mode` ve işlenebilirlik durumunu kullanır; bağımsız tween'in
`process_mode="always"` olması duraklatılmış menü geçişleri için kullanılabilir.

## AnimationPlayer ve Timeline

Sprite'ın kare animasyonları `AnimatedSprite` üzerindedir. Birden fazla nesnenin
özelliğini ortak zaman çizelgesinde yönetmek için `Timeline` kullanılır:

```python
from doku2d import AnimationPlayer, Timeline

clip = Timeline(3, loop=True)
clip.property(crate, "position", [(0, (100, 200)), (1.5, (400, 200)), (3, (100, 200))],
              ease="in_out_sine")
clip.property(crate, "rotation", [(0, 0), (3, 360)])
clip.call(1.5, sparks.burst)
clip.signal(2, my_signal, "cue")

player = game.add(AnimationPlayer())
player.add_animation("crate", clip)
player.play("crate")
```

Hedefler doğrudan Python nesnesidir; sahne yolu veya root gerekmez.
`Timeline(length=None)` son anahtardan süreyi hesaplar. Anahtar zamanları saniye,
benzersiz ve negatif olmayan değerlerdir. `interpolation="step"`, görünürlük gibi
kesikli özellikler için kullanılabilir. İlk anahtardan önce ilk değer, son anahtardan
sonra son değer tutulur. Boş, döngüsüz bir çizelge sıfır sürede tamamlanabilir.

`play(name)` baştan başlatır; `play_backwards(name)` sondan ters oynatır.
`pause()` / `resume()` mevcut konumu korur; `stop(reset=True)` ilk kareyi uygular.
`seek(seconds)` özellikleri günceller ama çağrı/sinyal anahtarlarını tetiklemez.
İstenirse `seek(..., events=True)` geçilen olayları yayar; `update=False` yalnızca
oynatma konumunu değiştirir. `speed_scale` hız çarpanıdır, negatif de olabilir.

`playback_position` saniye cinsinden oynatma konumudur; `position` normal Entity
konumudur. `animation`, `playing`, `animations` okunabilir. Sinyaller:
`animation_started(name)`, `animation_finished(name)`, `animation_looped(name)`.
Döngülü klipte finished yerine looped yayılır. Bir karede birden fazla anahtar veya
döngü geçilirse olaylar atlanmaz. Varsayılan olarak oyunla duraklar.
Aynı özelliği aynı anda hem Tween hem Timeline ile yönetmekten kaçın.

## Particles

```python
from doku2d import Particles

smoke = game.add(Particles.smoke(position=(200, 400)))
sparks = game.add(Particles.sparks(position=(200, 400)))
sparks.burst()
rain = game.add(Particles.rain(position=(500, 0), amount=180))
```

Hazır ayarlar normal bir `Particles` döndürür; özellikleri sonradan değişebilir.
`Particles.sparks` bir defalık, başlangıçta kapalıdır; `burst()` veya `restart()` ile
başlatılır. Duman ve yağmur sürekli başlar. Constructor seçenekleri preset'in
varsayılan amount/lifetime/emitting değerlerini değiştirebilir.

```python
p = game.add(Particles(amount=80, lifetime=1.2, one_shot=True, emitting=False))
p.direction = (0, -1)
p.spread = 110
p.initial_velocity = (90, 220)
p.gravity = (0, 300)
p.scale_range = (1, 4)
p.color = (255, 210, 120)
p.end_color = (230, 70, 20, 0)
p.explosiveness = 1
p.restart()
```

| Özellik | Anlamı |
| --- | --- |
| `amount` | En fazla canlı parçacık sayısı (1–10000). |
| `amount_ratio` | 0–1 yoğunluk çarpanı. |
| `lifetime`, `randomness` | Saniye cinsinden ömür ve 0–1 arası ömür değişkenliği. |
| `one_shot`, `emitting` | Bir çevrim veya sürekli yayılım; yeni üretimi açıp kapama. |
| `explosiveness` | 0 eşit aralıklı, 1 anında toplu yayılım. |
| `direction`, `spread` | Yön ve toplam açı genişliği (derece). |
| `initial_velocity` | Piksel/saniye alt/üst hız aralığı. |
| `gravity`, `damping` | İvme ve üstel sönüm. |
| `scale_range`, `end_scale` | Başlangıç yarıçapı (piksel) ve ömür sonu boyut çarpanı. |
| `rotation_range`, `angular_velocity` | Derece ve derece/saniye aralıkları. |
| `color`, `end_color` | Ömür boyunca renk/alpha geçişi. |
| `texture`, `blend_mode` | İsteğe bağlı Texture/dosya ve alpha/add harmanlama. |
| `speed_scale`, `seed` | Simülasyon hızı ve rastgelelik tohumu. |

Dokulu parçacıkların en-boy oranı korunur; boyut, uzun kenarın yarısını belirtir.

`color_ramp=[(0, Color(...)), (.5, Color(...)), (1, Color(...))]` ara renkler sağlar.
`emission_shape`: `point`, `box`, `circle`; `emission_size` kutu boyutları,
`emission_radius` dolu daire yarıçapıdır. Yerel yayılım şekli nesnenin dönüşümüyle
başlar. `local_coords=False` varsayılandır: doğmuş parçacıklar kaynak hareket edince
onunla sürüklenmez. True olduğunda kaynakla birlikte dönüşürler; gravity de yereldir.
Canlı parçacık varken koordinat modu değiştirmek için önce `clear()` kullan.

`emitting=False` yeni üretimi keser, mevcut parçacıklar yaşamaya devam eder.
`clear()` mevcut parçacıkları temizler. `restart(clear=True)` çevrimi sıfırlar;
`burst(count=None)` kapasite kadar parçacığı anında ekler.
Son parçacık bittiğinde ve üretim durduğunda `finished()` bir kez yayılır.
`finished.connect(p.destroy)` tek kullanımlık efektin kaldırılmasını sağlayabilir.
`alive_count` canlı sayıdır. Sistem CPU tabanlıdır ve varsayılan olarak oyunla duraklar.

## Işıklandırma ve ortam rengi

```python
from doku2d import CanvasModulate, PointLight, DirectionalLight, LightOccluder

game.add(CanvasModulate(color=(45, 55, 75)))
lamp = game.add(PointLight(position=(250, 200), radius=260,
                           color=(255, 200, 135), energy=1.4, shadow=True))
game.add(DirectionalLight(direction=(.6, 1), energy=.15, shadow=True))
game.add(LightOccluder.from_body(wall))
```

Işık, ortam rengi ve engeller aynı Canvas içinde etkileşir. Varsayılan world Canvas
üzerindeki ışık HUD'ın ayrı Canvas'ını değiştirmez. `canvas.ambient=(r,g,b)` ortam
rengini doğrudan ayarlar; CanvasModulate bunu ayrıca çarpar. Alpha, Canvas'ın
saydamlığını da etkiler. `canvas.lighting=False` o Canvas'ın ışık/ortam geçişini kapatır.
Işık bulunmayan, beyaz ortamlı Canvas normal doğrudan çizim yolunu kullanır.
Aynı order'daki Canvas'lar kayıt sırasıyla ayrı yüzey olarak çizilir; kendi içlerinde
nesneler z_index ile sıralanır. HUD'ın order'ını dünyadan yüksek tut.

`PointLight`: `radius`, `falloff`, `color`, `energy`, `enabled`, `shadow`, `offset`,
`texture_scale`, `texture`. Varsayılan doku dairesel, yumuşak bir ışık düşüşüdür;
özel doku da verilebilir. Konum, dönüş ve ölçek ışığa uygulanır. `target=player`
verilirse dönüşümü hedefe göre hesaplanır; ek position/offset yereldir.
`DirectionalLight`: `direction`, `shadow_length` (`max_distance` aynı ayarın kısa
uyumluluk adıdır); konumdan bağımsızdır. Rotation yönünü döndürür.

```python
blocker = game.add(LightOccluder(
    points=[(-30, -40), (30, -40), (30, 40), (-30, 40)],
    position=(400, 250)))
```

`LightOccluder.points` yerel noktaları, `closed=False` açık çizgiyi tanımlar.
`target=wall` ile hedefin dönüşümünü izler. `from_body` Box, Circle, Polygon veya
Segment geometrisini alır; şekil sonradan değiştirilirse occluder'ı da güncelle.
`enabled=False` gölgeyi kapatır. Hedefi oyundan kaldırılmış engel/ışık çizime katılmaz.
Işığın kaynağı kapalı bir engelin içindeyse o noktasal ışık engellenir.

`canvas.light_mask`, `light.light_mask`, `occluder.light_mask` 32-bit maskelerdir.
Işık yalnızca eşleşen Canvas ve engelleri kullanır. Fizik maskelerinden bağımsızdır;
çarpışma gövdesi kendiliğinden ışık engellemez, occluder eklemek gerekir.

Bu sürüm keskin çokgen gölgeleri üretir: noktasal ışıkta görünürlük ışınları,
yönlü ışıkta uzatılmış gölge çokgenleri kullanılır. Normal map, SDF, yumuşak gölge,
HDR/bloom bu API'nin parçası değildir. Renkler standart 8-bit ışık yüzeyinde birleşir.
Aydınlatma SFML/OpenGL shader desteği gerektirir; yüzeyler pencere boyutuna göre
yenilenir ve yeniden kullanılır.

CanvasModulate uyumluluk adı korunur; AmbientLight, DayNightCycle ve gerçek CanvasGroup
kullanımı için [runtime rehberine](runtime.md) bakın.
## Kendi shader'ını kullanma

`assets/shaders/tint.frag`:

```glsl
uniform sampler2D u_texture;
uniform vec4 tint;

void main() {
    vec4 pixel = texture2D(u_texture, gl_TexCoord[0].xy);
    gl_FragColor = pixel * gl_Color * tint;
}
```

```python
from doku2d import Color, ShaderMaterial

material = ShaderMaterial('res://shaders/tint.frag')
sprite.material = material
material.set_shader_parameter('tint', Color(255, 140, 100))
```

Bir materyali `Sprite`, `AnimatedSprite`, `TileMap`, `CanvasGroup` veya başka
bir çizilebilir nesnenin `material` alanına verebilirsin. Özel çizim kodunda
`render(target, states)` ile gelen `states` değerini SFML çizim çağrısına aktar.
`material = None` normal çizime döner. Aynı materyali paylaşan nesneler aynı
parametreleri görür. Bağımsız parametreler için ayrı materyal oluştur.

`game.world.material = material` efekti aydınlatmadan sonra tüm dünya
katmanına uygular. Ayrı HUD katmanı normal kalır. `CanvasGroup.material`
grup tint ve saydamlığı birleştirildikten sonra çalışır. Bu iki kullanım ek
çizim yüzeyi gerektirir. UI açılır menüleri katman sonrası çizilir ve kendi
kontrollerinin materyalini kullanır.

Shader kodu SFML/OpenGL uyumlu GLSL kullanır. `u_texture` mevcut çizim
dokusuna otomatik bağlanır. Başka bir sampler adı için `texture_uniform`
verebilir, dokusuz shader için `texture_uniform=None` kullanabilirsin.
`vertex='res://shaders/move.vert'` isteğe bağlıdır. Dosya yerine GLSL metni
vermek için `ShaderMaterial.from_source(...)` kullan.
