# GUI

Kontroller bağımsız Entity nesneleridir. `game.add(control)` onları varsayılan
ekran Canvas'ına kaydeder. Dünya içinde duran etiketler için `canvas=game.world`
verilebilir. Fare koordinatları kamera, dönüş ve ölçekten geri dönüştürülür.

```python
from doku2d import Game
from doku2d.gui import Button, LineEdit, Slider, ProgressBar, VBox

game = Game()
column = VBox()
column.position = (32, 32)
column.size = (320, 220)
button = column.add(Button(text="Başlat"))
entry = column.add(LineEdit())
entry.placeholder = "Oyuncu adı"
slider = column.add(Slider(value=60, step=1))
progress = column.add(ProgressBar(value=60))
slider.value_changed.connect(lambda value: setattr(progress, "value", value))
button.pressed.connect(lambda: print(entry.text))
game.add(column)
game.run()
```

## Ortak davranış

`position`, `size`, `min_size`, `max_size`, `rotation`, `scale`, `visible`,
`disabled`, `font`, `font_size`, `theme` ve `anchor` ayarlanabilir.
`Anchor.BOTTOM_RIGHT` gibi bir anchor ile `offset` birlikte kullanıldığında
kontrol mantıksal ekran boyutu değişince yeniden konumlanır.

Fare üzerine gelme, odak alma, boyut değişimi ve ham GUI input'u sinyallerle
izlenebilir. `grab_focus()` ve `release_focus()` odağı değiştirir. Tab ve
Shift+Tab kayıt sırasına göre gezinir. Butonlarda Enter/Space çalışır.
`mouse_filter` için `stop`, `pass`, `ignore` kullanılır. Durdurulan olaylar
oyun nesnelerine gitmez. Klavyeyi sürekli polling ile okuyan oyun kodu,
yazı alanı odaklıyken `game.ui.keyboard_captured` değerini kontrol edebilir.

Kontroller kendi sınırlarında kırpılır. `clip_contents=False` bu kırpmayı
kapatır. Popup'lar kontrol sınırlarının dışında, ekran üzerinde çizilir.

## Kontroller

- `Panel`, `Label`, `RichLabel`. RichLabel temel `[b]`, `[i]`,
  `[color=#RRGGBB]` ve `[url=değer]` etiketlerini işler. Bağlantılar
  `meta_clicked(değer)` sinyali yayar, otomatik tarayıcı açılmaz.
- `Button`, `CheckBox`, `CheckButton`, `TextureButton`. Toggle durumu
  `button_pressed`, olaylar `pressed`, `button_down`, `button_up`, `toggled`.
  TextureButton için normal/hover/pressed/disabled dokuları atanabilir.
- `LineEdit`, `TextEdit`. Unicode giriş, caret, Shift ile seçim, Ctrl+A,
  Ctrl+C/X/V, Ctrl+Z/Y, oklar ve Home/End desteklenir. `LineEdit`
  `text_submitted(text)` yayar. `secret`, `max_length`, `editable` seçenekleri
  vardır. TextEdit çok satırlıdır. İçerik taştığında yatay ve dikey kaydırma
  çubukları otomatik görünür. `h_scrollbar` ve `v_scrollbar` ile erişilir.
  Tekerlek dikey, Shift+tekerlek yatay kaydırır. Sağ tık menüsü
  `context_menu_enabled` ile, küçük emoji listesi `emoji_menu_enabled` ile
  açılır. `add_gutter(line_numbers=True)` satır numarası alanı ekler.
- `ProgressBar`, `TextureProgressBar`, `Slider`, `SpinBox`, `ScrollBar`
  ortak Range davranışını kullanır. Slider sürüklenir, oklarla ayarlanır.
  SpinBox'ta sayı yazıp Enter'a basılır veya +/- kullanılır. ScrollBar için
  `page` görünür sayfa büyüklüğünü, `vertical` yönü belirler.
- `ItemList` için `add_item()` veya `items=[Item(...)]`, `select_mode`,
  `selected_indices`, `select()` vardır. Ctrl ile çoklu seçim, çift tık ve
  Enter ile aktivasyon desteklenir.
- `TabBar` için `tabs`, `current_tab`, `add_tab()` kullanılır.
  Kapatma düğmesi `tab_close_pressed(index)` yayar. Uygulama bu sinyale
  bağlanıp hangi içeriğin gösterileceğini veya kaldırılacağını belirler.
- `OptionButton` açılır seçim listesi, `ColorPickerButton` RGBA kanallarını
  değiştiren açılır renk seçici sağlar. Renkler 8 bit/kanaldır.
- `NinePatchRect` dokuyu dokuz parçaya ayırır. `patch_margin` sırası
  sol, üst, sağ, alt. Küçük hedeflerde sınırlar orantılı daraltılır.
  `region_rect` doku içindeki alanı, `draw_center` merkez çizimini belirler.

TextureProgressBar yatay/dikey dolum ve doku kırpmayı destekler.
Radyal dolum ve HDR renk seçimi uygulanmamıştır. RichLabel tam bir belge
veya HTML motoru değildir. TextEdit temel düzenleme sağlar, işletim sisteminin
IME aday penceresini uygulama içinde yönetmez.

## Tree

```python
from doku2d import Tree

tree = game.add(Tree())
missions = tree.add_item("Görevler", expanded=False)
quest = tree.add_item("Mektubu teslim et", parent=missions, data="letter")
tree.item_activated.connect(lambda item: print(item.data))
tree.select(quest)
```

Sol ve sağ oklar dalları kapatıp açar. Yukarı ve aşağı görünür satırlarda
gezinir, Enter seçili öğeyi etkinleştirir. Fareyle dal işaretini tıklayabilir
ve tekerlekle kaydırabilirsin. `set_expanded(item, value)` ile dalı koddan
değiştir, `remove_item(item)` ile alt dalları birlikte kaldır.

## Sürükle-bırak

```python
from doku2d import DragData

inventory_slot.drag_source = lambda position: DragData(item, preview=item.name)
equipment_slot.drop_filter = lambda position, data: data.kind == "tool"
equipment_slot.dropped.connect(equip_item)  # equip_item(data, position)
```

`drag_source` başlangıçtaki yerel konumu alır. Boş yuvadan sürükleme
başlamasın istiyorsan `None` döndür. `DragData` önizlemesi metin,
`Texture` veya `AtlasRegion` olabilir. `drop_filter` hedefteki yerel
işaretçi konumunu ve taşınan veriyi alır.

Motor, sürükleme eşiğini, önizlemeyi, geçerli hedef vurgusunu ve iptali
yönetir. Kaynakta `drag_started(data)` ve `drag_finished(data, accepted)`
sinyalleri vardır. Geçerli hedefte bırakıldığında `dropped(data, position)`
yayılır. Alt sınıflar `get_drag_data`, `can_drop_data` ve `drop_data`
metotlarını da kullanabilir.

`Tree.item_at(position)` ile hedef satırı bulabilir,
`tree.move_item(item, parent=branch)` ile alt dalları birlikte taşıyabilirsin.
Eşyanın envanterden çıkarılması veya öğenin taşınması oyunun bırakma
işleyicisinde yapılır.

## Yerleşim

`HBox`, `VBox`, `Grid`, `Center` birer yerleşim kontrolüdür. `add(control,
expand=True)` fazla alanı paylaştırır. `spacing`, `set_margins()` ve
`Grid.columns` düzeni belirler. Kontroller Game içinde bağımsız kalır.
Bir kontrol aynı anda tek yerleşime ait olabilir. Yerleşimin kaydettiği
üyeler yerleşim kaldırıldığında da kaldırılır. Önceden Game'e kaydedilmiş
kontrollerin ömrü uygulamaya aittir. İç içe yerleşim desteklenir.

Yerleşim gizlendiğinde üyeler de çizim ve input dışında kalır.
Temayı `game.ui.theme` ile oyun genelinde seçebilirsin. Bir yerleşime verilen
tema üyelerine geçer. `control.theme` tek bir kontrole öncelikli tema verir.
`control.font_size = None` temanın yazı boyutuna döner.

```python
game.ui.theme = "res://theme.toml"
menu.theme = game.ui.theme.variant(radius=4)
```

```toml
[theme]
font_size = 18
font = "fonts/menu.ttf"
accent = [103, 221, 190]
radius = 10
```

TOML içindeki font yolu tema dosyasına göre çözülür. `res://` yolu varlık
klasöründen başlar. Font belirtilmezse motorun Noto Sans fontu kullanılır.
Ek odak çerçevesi `show_focus=True` ile açılır.

## Dokunmatik kontroller

`TouchScreenButton` aynı anda birden fazla parmağı izleyebilir. `action`
atandığında durum `game.ui.is_action_pressed(action)` ile okunur.
`VirtualJoystick.value` normalize yön vektörüdür. `moved(value)`,
`pressed`, `released`, `tapped`, `flicked` sinyalleri vardır.
`joystick_mode` için `fixed`, `dynamic`, `following` kullanılır.
Fare ile de denenebilir.

## Örnek

`python -m examples.gui_demo`

Üç sekmede kontroller, metin düzenleme, listeler, dokular, dokuz parçalı
çizim ve sanal joystick denenebilir. Otomatik kapanan kontrol için
`python -m examples.gui_demo --frames 120` kullanılır.


## RichLabel animasyonları

`bbcode_enabled=True` iken beş hazır efekt etiketle uygulanabilir.

```python
label = RichLabel(text="[wave amp=4 freq=2]Merhaba[/wave]")
label.bbcode_enabled = True
```

| Efekt | Örnek |
| --- | --- |
| Dalga | `[wave amp=4 freq=2]Metin[/wave]` |
| Dairesel hareket | `[tornado radius=3 freq=1]Metin[/tornado]` |
| Titreşim | `[shake rate=20 level=2]Metin[/shake]` |
| Gökkuşağı | `[rainbow speed=0.2 sat=0.65 val=1]Metin[/rainbow]` |
| Nabız | `[pulse freq=1]Metin[/pulse]` |

Etiketler iç içe kullanılabilir. Sayısal parametreler isteğe bağlıdır.
Doku2D'nin varsayılan hareket mesafeleri küçük arayüz yazıları için seçilmiştir.
`restart_effects()` animasyon saatini sıfırlar. Normal Entity duraklatma
kuralları geçerlidir. Efektlerin taşmaması için `effect_padding` boşluk bırakır.

`install_effect("custom", callback)` özel bir efekt kaydeder. Callback,
`CharacterEffect` ve parametre sözlüğü alır. Karakterin `offset`, `color`,
`scale`, `visible` alanlarını değiştirebilir. `index` metindeki karakter
sırası, `elapsed` saniye cinsinden animasyon zamanıdır. Bu API Python
karakterleri üzerinden çalışır; birleşik Unicode dizileri ve karmaşık
metin şekillendirme için tam bir glyph motoru sağlamaz.

GUI örneğinin **Text effects** sekmesi beş efekti ve birleşik kullanımını gösterir.
## Yerelleştirme

Varlık dizininde `locale/tr.json` ve `locale/en.json` gibi dosyalar oluştur.
Kataloglar düz bir anahtar-metin sözlüğüdür. Aşağıdaki örnek `tr.json` içeriğidir:

```json
{"menu.play": "Oyna", "menu.coins": "{count} altın"}
```

```python
from doku2d import Button, Label, tr

game.localization.load_catalog('tr', 'res://locale/tr.json')
game.localization.load_catalog('en', 'res://locale/en.json')
play = game.add(Button(text=tr('menu.play'), fit_text=True))
coins = game.add(Label(text=tr('menu.coins', count=3)))
game.locale = 'tr'
```

`tr(...)` ile işaretlenen düğme, etiket, liste öğesi, sekme ve metin kutusu
ipucu yeni dile geçer. Düz metinler ve oyuncunun yazdığı içerik olduğu gibi
kalır. Bir `Label` veya `Button` üzerinde `fit_text=True` metne göre genişliği
ayarlar. `HBox` içinde de yanındaki kontrolleri buna göre yerleştirir.

Eksik anahtar önce dilin genel sürümünde aranır (`tr-TR` → `tr`), ardından
yedek dil kullanılır. Anahtar hâlâ bulunamazsa `tr(..., default='Oyna')`
metni veya anahtarın kendisi gösterilir. `game.localization.locale_changed`
uygulamanın kendi dil değiştirme koduna bağlanabilir.

`Game.from_project()` için katalogları doğrudan proje dosyasında tanımlayabilirsin:

```toml
[localization]
locale = "tr"
fallback = "en"

[localization.catalogs]
tr = "locale/tr.json"
en = "locale/en.json"
```

Yollar varlık dizinine göredir ve normal derlemeye dahil edilir.
`persist_preferences=True` açıksa seçilen dil de ayarlara kaydedilir.
