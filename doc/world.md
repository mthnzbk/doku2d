# TileMap, Tiled, kamera ve ses

Birlikte çalışan örnek: `python -m examples.world_demo`.
WASD/oklar veya gamepad ile yürü; Space kamerayı sarsar, P/ESC duraklatır.
Alttaki kontroller ön planı, sesi ve yakınlaştırmayı değiştirir.
Işıklara yaklaşıp uzaklaşınca ses düzeyi, sağından/solundan geçince stereo dengesi değişir.
Örnek dosyalar `examples/assets/world/` içindedir. `forest.tmj` Tiled'da açılıp düzenlenebilir.
`--frames 120` otomatik kapanan kontrol çalıştırması sağlar.

## Tiled haritasını yükleme

```python
from doku2d import Game, TileMap

game = Game()
world = game.add(TileMap.from_tiled("assets/level.tmx"))
world.layers["Ground"].visible = True
world.layers["Canopy"].z_index = 20

game.run()
```

Katmanlar adlarıyla erişilir. Gruplar `World/Ground` gibi yollarla düzleştirilir;
Tiled'daki görünürlük, opacity, tint, offset ve parallax birleşimleri korunur.
Döşeme, resim ve nesne katmanları desteklenir. Resim katmanları tekrar edebilir;
nesne katmanlarında tile object görselleri çizilir, diğer nesneler oyun verisi olarak kalır.

`TileMap` katmanlarını oyuna otomatik kaydeder ve kaldırırken temizler. Katmanları
ayrıca `game.add` ile ekleme. Bunlar düz oyun kayıtlarıdır; yeni bir sahne ağacı yoktur.
`tilemap` konum/dönme/ölçeği katman çizimlerine uygulanır. Katmanların kendi
`position`, `rotation`, `scale`, `visible`, `opacity`, `tint`, `parallax`, `canvas`
ve `z_index` ayarları da vardır. `z_index`, haritanın `z_index` değerine eklenir.

Zemin `z_index=0`, karakter `z_index=10`, ön plan `z_index=20` olursa karakter
zeminin üstünde, ağaç yapraklarının altında çizilir. `Canvas` sırası da her zamanki
çizim sıralamasına katılır. `layer.parallax=(.5,.5)` daha yavaş hareket eden katmandır.

### Parser ayrı kullanılabilir

```python
from doku2d import TiledParser, TileMap

data = TiledParser.parse("assets/level.tmj")  # yalnızca dosya/veri işlemleri
world = TileMap(data)                        # dokular bu aşamada yüklenir
```

Parser pencere açmaz ve GPU dokusu oluşturmaz. Sonuç `MapData` nesnesidir:
`tile_size`, `size`, `layers`, `tilesets`, `properties`, `infinite`,
`render_order`, `parallax_origin`, `background_color`.
`TileCell`, global GID yerine tileset sıra numarasını ve yerel tile id'yi tutar;
çevirme bayrakları ayrı alanlardadır.

Desteklenenler:

- Orthogonal haritalar: TMX ve JSON (`.tmj`, `.json`).
- Gömülü veya harici TSX/TSJ tileset'ler; bir haritada birden fazla tileset.
- Atlas ve ayrı resimlerden oluşan tileset'ler; margin, spacing ve tile offset.
- Dizi, TMX XML tile listesi, CSV ve Base64; sıkıştırmasız, zlib ve gzip verisi.
- Sabit boyutlu ve infinite/chunk haritalar; negatif hücre koordinatları.
- Yatay, dikey ve diagonal çevirme; dört orthogonal çizim sırası.
- Gruplar, animasyonlu döşemeler, layer tint/opacity/parallax ve tekrar eden resimler.
- Nesne kimliği, adı, sınıfı/türü, konumu, boyutu, dönüşü, noktaları ve custom property'leri.
- Dosya property'leri ile görsel yollarının ilgili TMX/TSX/JSON dosyasına göre çözülmesi.

Isometric/staggered/hexagonal haritalar, zstd ve harici object template'leri henüz
desteklenmez; parser açık hata verir. Tile object hizalaması bottom-left olmalıdır.
Edge Wang setleri autotile kurallarına çevrilir. Otomatik Tiled çarpışmaları ve
animasyonlu autotile için [platform rehberine](platform.md) bakın.
Metin/polygon gibi nesneler metadata'dır; otomatik GUI veya şekil çizimine dönüşmez.

### Nesneler ve custom property'ler

```python
spawn = next(obj for obj in world.objects if obj.name == "PlayerSpawn")
player.position = world.transform.transform_point(spawn.position)
speed = spawn.properties.get("speed", 220)
```

`world.objects` tüm nesne katmanlarını birleştirir. `MapObject` üzerinde `id`,
`name`, `type`, `position`, `size`, `rotation`, `shape`, `points`, `tile`,
`properties`, `layer`, `visible`, `text` bulunur. Konumlar haritanın yerel piksel
koordinatlarıdır; grup/katman offset'leri zaten eklenmiştir. Property türü `object`
olan değerler nesne kimliği olarak korunur. Dünya içindeki `visible`, nesnenin
kendi görünürlüğüdür; katmanın görünürlüğü ayrıca uygulanır.

## Elle harita oluşturma ve hücre düzenleme

```python
from doku2d import TileMap, TileSet

world = TileMap(tile_set=TileSet("tiles.png", tile_size=(32, 32)))
ground = world.add_layer("Ground", z_index=0)
ground.fill((0, 0, 30, 20), 0)
ground.set_cell((4, 6), 3)
ground.set_cell((5, 6), 3, flip_h=True)
ground.erase_cell((7, 6))
game.add(world)
```

Yerel tile id `0` ilk döşemedir; boş hücre `None`'dır. `set_cell(..., None)` veya
`set_cell(..., -1)` de hücreyi siler. `tileset=1` ya da `tileset="Forest"` ile
başka tileset seçilebilir. `world.add_tileset(...)` eklenen tileset'in sıra numarasını döndürür.
`get_cell((x,y))` bir `TileCell` veya `None` döndürür; `layer.cells` salt okunur
hücre görünümüdür. `clear`, `fill`, `remove_layer` ve `changed` sinyalleri vardır.
`tile_size` harita ızgarasıdır; tileset görsel boyutu farklı olabilir.

`world.map_to_local((x,y))` hücrenin merkezini, `local_to_map(point)` hücre
koordinatını döndürür. `map_to_world` / `world_to_map` haritanın dönüşümünü de
uygular. `bounds` yerel piksel sınırları, `world_bounds` dönüşmüş sınır kutusudur;
kamerada `camera.bounds = world.world_bounds` kullanılabilir.

Çizim geometrisi `chunk=(16,16)` hücrelik parçalarda önbelleklenir. Yalnızca
görünen parçalar hazırlanır/çizilir; hücre değişince ilgili parça yenilenir.
Animasyon kareleri değişince geometrisi yenilenir. Infinite haritalarda bu
parçalar Tiled'ın kaydettiği chunk boyutundan bağımsızdır.

## Kamera

```python
from doku2d import Camera

camera = game.add(Camera())
camera.follow(player, smoothing=8, dead_zone=(160, 100))
camera.bounds = world.world_bounds
camera.zoom = (1.25, 1.25)

camera.shake(10, .3)
```

Takip nesnesi normal bir `Entity` veya konum döndüren callable olabilir.
Takip, nesnelerin güncellemesinden sonra çözülür; kayıt sırası gecikme oluşturmaz.
`dead_zone` dünya pikseli cinsinden genişlik/yüksekliktir; sıfır kesintisiz takip eder.
`position_smoothing` ve `smoothing_speed` yumuşatmayı, `rotation_smoothing`
açı yumuşatmasını yönetir. `follow(..., smoothing=0)` doğrudan takip eder.
`reset_smoothing()` hedefe anında gider; ışınlanma sonrası kullanılabilir.
`offset` takip merkezine eklenir. `target=None` ile kamera elle hareket ettirilir.

`bounds=(x,y,width,height)` veya `limit=(left,top,right,bottom)` kullanılabilir.
Yakınlaştırma ve dönmeyle görünen alan sınır içinde tutulur. Harita ekrandan
küçükse o eksende ortalanır. `limit_enable=False` sınırları kapatır.
`screen_center` son görünüm merkezidir; `position` sarsıntıdan etkilenmez.
Sarsıntı süre sonunda sıfırlanır; `stop_shake()` erken keser. Sınırlarda sarsıntı
kırpılarak harita dışına taşması engellenir. Ekran uzayındaki Canvas etkilenmez.

## Ses

```python
from doku2d import AudioPlayer, PositionalAudio, AudioListener

music = game.add(AudioPlayer("music.ogg", stream=True, loop=True,
                            autoplay=True, volume=40))
click = game.add(AudioPlayer("click.wav", max_polyphony=4))
click.play()

listener = game.add(AudioListener(target=player))
water = game.add(PositionalAudio("water.wav", position=(500, 300),
                                 max_distance=700, autoplay=True, loop=True))
```

`AudioPlayer` konumdan bağımsız ses; `PositionalAudio` iki boyutlu konuma göre
ses düzeyi ve stereo dengesi hesaplar. `AudioListener` dinleme merkezidir;
`target` verilirse takip eder, `offset` eklenebilir. İlk dinleyici otomatik seçilir;
`make_current()` ile değiştirilebilir. Dinleyici yoksa etkin kamera, kamera da
yoksa ekranın merkezi kullanılır. Dinleyicinin dönüşü sağ/sol eksenini döndürür.

`volume`: 0–100, `volume_db`: en çok 0 dB, `pitch_scale`: pozitif oynatma hızı/perde,
`loop`, `autoplay`, `max_polyphony` özellikleri vardır. Ses girdisi dosya yolu
veya SFML `SoundBuffer` olabilir. Normal sesler `game.resources.get_sound` ile
önbelleklenir. `stream=True`, dosyayı SFML Music üzerinden akıtarak çalar;
uzun müziklerde tamamını belleğe almak gerekmez.

`play(from_position=0)`, `stop()`, `pause()`, `resume()`, `seek(seconds)` ve
`get_playback_position()` kullanılabilir. `stream_paused` elle duraklatmadır;
`playing` duraklatılmış ama bitmemiş sesleri de kapsar. Doğal olarak son ses
bittiğinde parametresiz `finished` yayılır; `stop()` bu sinyali yaymaz. Polyphony
sınırı aşılırsa en eski ses durdurulur. Nesne kaldırılınca sesleri de durur.

Oyun durakladığında sesler mevcut konumunda duraklar ve devam eder;
`process_mode="always"` olan sesler duraklama sırasında da çalar.
Elle duraklatılmış ses, oyun devam ettirildi diye yeniden başlamaz.

Konumsal seste `max_distance` dışında ses sıfırdır. Ses eğrisi
`volume * max(0, 1-distance/max_distance) ** attenuation` biçimindedir.
`panning_distance` tam sağ/sol dengeye ulaşılacak yatay uzaklık,
`panning_strength` etki çarpanıdır; `0` merkezden çalar.
`effective_volume` ve `pan` hesaplanan değerleri okumak içindir.
Hesaplama oyun örneğine özeldir; SFML'ın global listener konumu değiştirilmez.
Ses çıkışı işletim sisteminin seçili aygıtını kullanır; hesaplanan pan/gain
ayarlanan hoparlör düzenine göre duyulur.

## Format kaynakları

[Tiled JSON](https://doc.mapeditor.org/en/stable/reference/json-map-format/),
[TMX](https://doc.mapeditor.org/en/stable/reference/tmx-map-format/) ve
[GID/çevirme bayrakları](https://doc.mapeditor.org/en/stable/reference/global-tile-ids/).

Proje kaynak kökü ve paylaşılan önbellek için `game.resources.load_map(path)` veya
`TileMap.from_tiled(path, resources=game.resources)` kullanılabilir.
