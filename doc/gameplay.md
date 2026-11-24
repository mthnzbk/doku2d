# Girdi, animasyon ve fizik

Çalışan örnek: `python -m examples.collect_game`.
WASD/oklar, gamepad sol çubuğu veya ekrandaki joystick hareket ettirir.
ESC/P duraklatır, R yeniden başlatır. Sekiz ışığı topla; sandıkları itebilirsin.
Metin alanına tıklayınca oyun girdisi kesilir; Enter veya boş alana tıklamak
oyuna dönmeni sağlar. `--frames 120` otomatik kapanan kontrol çalıştırmasıdır.

## En kısa karakter

```python
from doku2d import CharacterBody, Game, StaticBody

class Player(CharacterBody):
    def physics_update(self, dt):
        self.velocity = self.input.get_vector() * 220
        self.move_and_slide()

game = Game()
game.add(StaticBody(position=(400, 250), size=(30, 250), color=(60, 90, 110)))
game.run(Player(position=(100, 200), color=(100, 224, 199)))
```

Her nesne `game.add(...)` ile kaydolur. Özel Scene, root veya sahne ağacı yoktur.
`self.game` ve `self.input` kayıttan sonra kullanılabilir. Hız piksel/saniyedir;
`move_and_slide()` çağrısına `dt` çarpılmaz. Fizik bir sonraki sabit adımda ilerler.
`contacts`, `get_slide_collision(index)`, `is_on_floor()` ve `is_on_wall()`
son tamamlanan fizik adımının temaslarını verir.

## Girdi eşlemeleri

Varsayılan `move_left/right/up/down` eylemleri WASD, oklar ve gamepad eksenlerini
birleştirir. Çapraz hareket normalize edilir; analog kuvvet korunur.
`jump`: Space/gamepad 0, `interact`: E/gamepad 0,
`pause`: Escape/P/gamepad 7. Gamepad düğme numaraları cihaza göre değişebilir.

```python
from doku2d import Key, JoyButton, JoyAxis, MouseButton

game.input.bind("attack", Key.F, JoyButton(2), MouseButton(0))
game.input.bind("move_right", Key.D, Key.RIGHT, JoyAxis("X", deadzone=0.2))

# update veya physics_update içinde:
if self.input.is_action_just_pressed("attack"):
    self.attack()

held = self.input.is_action_pressed("attack")
released = self.input.is_action_just_released("attack")
strength = self.input.get_action_strength("attack")
horizontal = self.input.get_axis("move_left", "move_right")
direction = self.input.get_vector()  # veya dört özel eylem adı
```

`bind` o eylemin önceki eşlemesini değiştirir. `JoyButton(..., device=0)` ve
`JoyAxis(..., device=0)` yalnızca belirli cihazı dinler; varsayılan bütün cihazlardır.
İlk basış/bırakış bilgisi çizim karesinde bir kez, fizik adımında da bir kez görünür.
O karede fizik çalışmamışsa ilk sonraki fizik adımına saklanır.
Pencere odağı kaybolunca girdiler temizlenir.

Odak bir GUI kontrolündeyken oyun eylemleri baskılanır. GUI tarafından tüketilen
tuşlar bırakılana kadar oyuna geçmez. `global_action=True` eylemleri genel odak
baskılamasından muaftır; GUI'nin tükettiği tuşlara yine öncelik verilmez.
Metin yazarken kısayol istemiyorsan eylemi global yapma.

```python
from doku2d import TouchScreenButton, VirtualJoystick

button = TouchScreenButton()
button.action = "jump"
game.add(button)

stick = game.add(VirtualJoystick())  # doğrudan varsayılan move_* eylemlerine bağlı
stick.bind_actions("left", "right", "up", "down")  # isteğe bağlı özel adlar
```

Dokunmatik kontroller normal GUI boyut/konum ayarlarını kullanır. Elle sanal girdi
göndermek için `action_press("jump", source=nesne)` / `action_release(...)` vardır.
Kaynaklar bağımsızdır; birini bırakmak başka cihazın basılı girdisini kesmez.
Kontrol gizlenince, devre dışı bırakılınca veya kaldırılınca dokunma bırakılır.

## Sprite animasyonu

```python
from doku2d import AnimatedSprite

sprite = AnimatedSprite("hero.png", frame_size=(32, 32))
sprite.add_animation("idle", [0, 1], fps=4)
sprite.add_animation("walk", [2, 3, 4, 5], fps=10)
sprite.add_animation("hit", [6, 7], fps=12, loop=False)
sprite.play("idle")

# Bir fizik gövdesinin görseli olarak:
player.sprite = sprite
# Bağımsız görselse: game.add(sprite)
```

Kare numaraları sprite sheet üzerinde soldan sağa, yukarıdan aşağıya sayılır.
`sprite.frame` seçili animasyon içindeki sıra numarasıdır.
Aynı animasyonu tekrar `play("walk")` ile seçmek kareyi sıfırlamaz; bu yüzden
hareket kodunda her adımda çağrılabilir. `pause()` konumu korur, `stop()` ilk
kareye döner. `speed_scale`, `play(..., speed=-1, from_end=True)`, `flip_h`,
`flip_v`, `offset`, `scale` desteklenir.
`play("walk_east", preserve_phase=True)` iki döngülü klip arasında
geçerken döngüdeki ilerlemeyi korur.
`animation_changed`, `frame_changed`, `animation_looped`, `animation_finished`
parametresiz sinyallerdir. Döngüsüz animasyon bitiş sinyalini bir kez yayar.

Bir kareye ayak sesi, toz veya benzeri bir olay bağlayabilirsin:

```python
sprite.add_animation("run_south", [0, 1, 2, 3], fps=10,
                     markers={1: "footstep", 3: ("footstep", "dust")})
sprite.marker_reached.connect(on_marker)  # on_marker(marker, animation, frame)
```

İşaret numarası klip içindeki sıfır tabanlı kare sırasıdır. Oynatma bir
güncellemede birkaç kareyi geçse bile bütün işaretler geçiş sırasıyla yayılır.
Döngü konumunu koruyarak başka klibe geçmek, o konumdaki işareti tekrar yaymaz.

Alternatif tanım: `sprite.sprite_frames = {"walk": Animation((0, 1, 2), 10, True)}`.
`Animation` aynı paketten içe aktarılır; `sprite_frames` salt okunur görünüm döndürür.
Bir gövdeye verilen sprite ayrıca `game.add` ile kaydedilmez; konumu gövdeye göredir.
Gövde animasyonu ve çizimi otomatik ilerletir. Duraklatınca animasyon da durur.

### Üstten görünümlü karakterler

Yönlü klipleri ekledikten sonra mevcut gövdeye bağla:

```python
player.sprite = sprite
motion = sprite.follow_motion(player, directions=8)
```

Klip adları `idle_south`, `run_east` ve `run_north_east` biçimindedir.
`directions=4` ana yönleri, `directions=8` çaprazları da seçer. Bir yönün
klibi eksikse `idle` veya `run` gibi yönsüz klip kullanılabilir. Özel adlar
için `idle="stand"` ve `run="walk"` ver.

Karakter ilk olarak güneye bakar. Durunca `motion.facing` son hareket yönünü
korur. Koşarken yön değişince yeni klip aynı döngü konumundan oynar. Bu
seçim, klipleri otomatik aynalamaz. `navigate_to()` ile hareket eden NPC’ler
aynı şekilde bağlanır.

## Fizik gövdeleri ve alanlar

`game.physics` Pymunk 7 tabanlı dünyayı gerektiğinde oluşturur.
Varsayılan yerçekimi `(0, 0)`; platform örneği için `game.physics.gravity = (0, 900)`.

- `StaticBody`: sabit duvar/zemin.
- `RigidBody`: yerçekimi, kuvvet, darbe, dönme ve sürtünme alan cisim.
- `CharacterBody`: kullanıcı hızını yönettiği, dönmesi kilitli karakter;
  varsayılan `gravity_scale=0`. Statik yüzeylere yönelen hız bileşeni kaydırılır.
- `AnimatableBody`: koddan konumu/hızı yönetilen kinematik engel.
- `Area`: fiziksel olarak engellemeyen algılama alanı.

```python
from doku2d import Area, Circle, RigidBody

crate = game.add(RigidBody(position=(250, 100), size=(32, 32), mass=2))
crate.linear_damp = 2
crate.apply_impulse((80, -160))

trigger = game.add(Area(position=(400, 200), shape=Circle(24)))
trigger.body_entered.connect(lambda body: print("Girdi:", body.name))
trigger.body_exited.connect(lambda body: print("Çıktı:", body.name))
```

`size=(w,h)` kutu, `radius=r` daire kısayoludur; alternatif `shape=Box(...)` /
`Circle(...)`. Şekiller gövdenin merkezindedir. Daireler tekdüze ölçek ister.
Gövde `position`, `rotation` (derece), `scale`, `velocity`/`linear_velocity`,
`angular_velocity` (derece/saniye), `mass`, `gravity_scale`, `friction`,
`elasticity`, `linear_damp`, `angular_damp`, `lock_rotation`, `freeze`, `sleeping`
ayarlarını sağlar. `force`/`torque` sürekli, `apply_force` tek adımlık kuvvettir.
`apply_impulse` anlık darbedir. Görsel sprite yoksa `color` basit şekil çizer.

`collision_layer` / `collision_mask` 32 bitlik bit maskeleridir; ilk katman `1`,
ikinci `2`, ikisi birlikte `3`. Katı gövdelerde karşılıklı katman/maskeler eşleşir.
Area kendi maskesine göre bağımsız algılar; diğer gövdenin maskesinde Area katmanı
bulunması gerekmez. `monitoring=False` algılamayı, `monitorable=False` diğer
Area'ların bu alanı görmesini kapatır. `area_entered` / `area_exited` de vardır.
`get_overlapping_bodies()` / `get_overlapping_areas()` son fizik adımını döndürür.
Sinyaller fizik çözücüsünün dışına ertelenir; içlerinde nesne kaldırılabilir.

```python
hit = game.physics.raycast((100, 100), (500, 100), exclude=(player,))
if hit:
    print(hit.collider, hit.point, hit.normal)
```

`game.paused=True` fizik dünyasını durdurur; `process_mode="always"` menü kodu
çalışmaya devam eder. Çarpışmalar sabit `physics_fps` adımıyla çözülür.
Platform hareketi, eğimler, hareketli platformlar, Tiled çarpışmaları ve
animasyonlu autotile için [platform rehberine](platform.md) bakın.
