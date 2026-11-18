# Doku2D kullanım modeli

Doku2D, bağımsız nesneleri doğrudan `Game` içine kaydeder.
`Entity` ortak oyun nesnesidir. Karakter, kamera ve kontrolcü aynı düz
koleksiyonda yaşar. Bir sınıfın bölüm veya menü oluşturması için özel
bir taban sınıftan türemesi gerekmez.

```python
from doku2d import Canvas, Entity, Game

class Player(Entity):
    def update(self, dt):
        self.position += (100 * dt, 0)

    def render(self, target, states):
        pass  # states.transform bu nesnenin konum, dönüş ve ölçeğidir

game = Game()
player = game.add(Player())
interface = Canvas("Interface", order=10, screen_space=True)
# game.add(MyLabel(), canvas=interface)
game.run()
```

`game.run(Player(), AnotherObject())` da nesneleri ekleyerek başlatabilir.
Kaynak olarak nesne örneği, sınıf veya parametresiz factory kullanılabilir.
Nesneler birbirini normal Python referanslarıyla tutar. Örneğin takip
kamerası kurucusunda `player` alır ve `update()` içinde onun konumunu okur.
Otomatik ebeveyn dönüşümü veya yol üzerinden nesne arama bulunmaz.

## Canvas

`Canvas` bir çizim ayarıdır. Nesne toplamaz ve yaşam döngüsü yönetmez.
Aynı Canvas herhangi sayıda nesnede paylaşılabilir.

```python
background = Canvas("Mountains", order=-1, parallax=(0.2, 0.2))
world = game.world
interface = Canvas("Interface", order=1, screen_space=True)

game.add(Mountains(), canvas=background)
game.add(Player(), canvas=world)
game.add(StatusBar(), canvas=interface)
```

`canvas.order` çizim sırasını, `screen_space` ekran koordinatlarında
çizimi, `parallax` kamera hareketi çarpanını belirler. Atanmayan Canvas
`game.world` olarak değerlendirilir. Aynı sıradaki nesneler `z_index`
ile sıralanır. Eşit değerlerde kayıt sırası korunur. Kamera ekran
merkezinde olduğunda dünya koordinatları ile ekran koordinatları aynıdır.

## Yaşam döngüsü

- `on_added()` her kayıtta çalışır. `self.game` bu sırada hazırdır.
- `on_ready()` örneğin ilk başarılı kaydında bir kez çalışır.
- `on_removed()` nesne çıkarılırken çalışır. `self.game` hâlâ kullanılabilir.
- `added`, `ready`, `removed` aynı aşamalara ait sinyallerdir.

`game.remove(obj)` veya `obj.destroy()` nesneyi koleksiyondan çıkarır.
Python referansları nesneyi hayatta tutabilir. Callback sırasında ekleme,
çıkarma ve içerik değiştirme güvenli döngü sınırlarına ertelenir.
Nesnenin `position`, `rotation` (derece), `scale`, `visible`, `z_index`
ve `canvas` property'leri vardır.

`game.paused = True` normal güncellemeyi ve input'u duraklatır.
`process_mode` seçenekleri `pausable`, `always`, `when_paused`, `disabled`.
Çizim devam eder. `physics_update(dt)` sabit zaman adımıyla çağrılır.

## İçeriği değiştirme ve kalıcı servisler

`game.replace(Menu())` geçici nesneleri kaldırıp yenilerini ekler.
`persistent=True` ile kaydedilen nesneler korunur.
Özel bir Scene veya bölüm tabanı gerekli değildir.

```python
from dataclasses import dataclass
from doku2d import Game

@dataclass
class Session:
    score: int = 0

game = Game(services={"session": Session})
game.services["session"].score += 10
```

Servisler oyun örneğine özeldir. Normal Python nesnesi veya `Entity`
olabilir. Entity servisleri otomatik olarak kalıcı kaydedilir ve
güncelleme alabilir. Normal nesneler yalnızca adla saklanır.
`game.services.add("name", instance_or_factory)` ve
`game.services.remove("name")` kullanılabilir.
`"package.module:ClassName"` biçimindeki kod referansları da desteklenir.
Kayıt sırası başlatma sırasıdır.

## Sinyaller ve sayısal kontroller

Sınıf üzerindeki `Signal()` her örneğe ayrı bağlantı listesi sağlar.
`connect(callback, one_shot=True)`, `disconnect(callback)`,
`is_connected(callback)` ve `emit(*args)` desteklenir.
Python bound metotları zayıf referansla tutulur.

`Range(Control)`, `ProgressBar`, `Slider`, `SpinBox` ve `ScrollBar` için
ortak `min_value`, `max_value`, `value`, `step`, `rounded`, `ratio`
davranışını sağlar. `step=0` sürekli değerdir. `value_changed(value)`
gerçek değer değişiminde, `changed()` aralık ayarları değiştiğinde yayılır.

## Örnek

`python -m examples.example1` hareketli kamera, parallax ve sabit ekran
Canvas'ını gösterir. WASD/ok tuşlarıyla hareket, P ile duraklatma,
R ile konum sıfırlama, Escape ile çıkış yapılır.
`--frames 120` otomatik kapanan kontrol çalıştırması sağlar.

Örnekteki metinler ve şekiller doğrudan SFML ile çizilir. Font için
Windows Segoe UI kullanılır. Motor çekirdeği bu fonta bağımlı değildir.
GUI kontrolleri ve etkileşimli örnek için [GUI rehberine](gui.md) bakın.
Girdi, sprite animasyonu, fizik ve oynanabilir toplama örneği için
[oynanış rehberine](gameplay.md) bakın. TileMap, Tiled, kamera ve ses için [dünya rehberine](world.md) bakın.
Tween, AnimationPlayer, parçacıklar ve ışık/gölge için [efekt rehberine](effects.md) bakın.

CanvasGroup, gece-gündüz, ortak kaynaklar ve kayıt için [runtime rehberine](runtime.md),
oluşturma/çalıştırma/paketleme için [proje rehberine](project.md) bakın.
