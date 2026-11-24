# Diyalog

`doku2d.dialogue` paketi metin dosyasından konuşma dalları okur. `DialogueBox`
mevcut GUI temasını kullanır ve metni harf harf gösterir.

## İlk konuşma

```python
from doku2d import DialogueBox, Game

game = Game(asset_root="examples/assets")
dialogue = game.add(DialogueBox(characters_per_second=45))
dialogue.continue_text = "Devam"
dialogue.start("res://harbor.dialogue")
game.run()
```

Enter veya boşluk yazıyı tamamlar, sonraki basış konuşmayı ilerletir.
Seçenekler satır tamamlandığında altta görünür. Yukarı ve aşağı oklarla
seçilebilir, Enter veya fareyle onaylanabilir. Escape konuşmayı kapatır.
Uzun bir satırı Page Up ve Page Down ile kaydırabilirsin.
`characters_per_second=0` metni hemen gösterir.

## `.dialogue` dosyası

```text
@portrait "Liman kâtibi" left "portraits/keeper.png"
@portrait "Lale" right "res://portraits/lale.png"

~ start
Liman kâtibi: Mektubu götürür müsün?
Lale: Kime teslim edeceğim?
Liman kâtibi: Ayla'ya. Değirmenin kapısında bekliyor.
- Evet => accepted
- Hayır => END

~ accepted
Lale: Patikayı izleyip götürürüm.
| Mektubu çantama koydum.
=> END
```

- `~ isim` yeni bir bölüm açar. `start` varsa varsayılan giriş odur, aksi
  hâlde ilk bölüm kullanılır. `start(tree, section="accepted")` doğrudan bir
  bölümden açar.
- `Konuşmacı: Metin` bir satır ekler. `|` ile başlayan satır aynı konuşma
  balonunda yeni bir satıra geçer. İsimsiz anlatım için düz metin yaz.
- `- Seçim => hedef` satırları bölümün sonuna eklenir. Seçenek yoksa
  `=> hedef` ile otomatik dal belirt. `END` konuşmayı kapatır.
- `@portrait` satırlarını bölümlerden önce yaz. Portre konuşmacıya göre üstte
  solda veya sağda gösterilir. Göreli dosya yolu diyalog dosyasının dizinine,
  `res://` yolu oyun kaynak dizinine göre çözülür.
- `#` ile başlayan satırlar yorumdur. Bölüm isimleri harf veya alt çizgiyle
  başlamalıdır. Hatalı hedefler dosya yüklenirken satır numarasıyla gösterilir.

## Oyuna bağlama

`DialogueTree.load(..., resources=game.resources)` bir ağacı önceden yükler.
Aynı ağacı daha sonra `dialogue.start(tree)` ile açabilirsin.

| Sinyal | Argüman |
| --- | --- |
| `line_changed` | `DialogueLine` |
| `choice_selected` | `DialogueChoice`, seçimin metni ve hedefi |
| `event_triggered` | Olay adı |
| `finished` | Argüman yok |

`dialogue.confirm()`, `dialogue.skip()`, `dialogue.choose(index)` ve
`dialogue.close()` ile kontrolleri kendi oyununun girdilerine bağlayabilirsin.
Arayüzün görünür olması oyunu duraklatmaz. Oyun kendi akışında
`game.paused = True` kullanıyorsa diyalog arayüzü işlemeye devam eder.

## Koşullar ve olaylar

```text
~ start
Ayla: Mektubu getirdin mi?
- Teslim et => delivered [if has_letter]
- Sonra gelirim => END

~ delivered
Ayla: Teşekkür ederim.
@event letter_delivered
=> reward [if reward_ready]
=> END

~ reward
Ayla: Bu ödül senin.
```

```python
state = {"has_letter": True}

def handle_event(name):
    if name == "letter_delivered":
        state["has_letter"] = False
        state["reward_ready"] = True

dialogue.event_triggered.connect(handle_event)
dialogue.start(tree, state=state)
```

`[if flag]` ve `[if not flag]` seçenekleri veya atlamaları koşula bağlar.
Belirtilmemiş bir bayrak yanlış kabul edilir. Birden fazla atlama varsa ilk
eşleşen kullanılır. Eşleşme yoksa bölüm kapanır. `@event` önceki satır
onaylandığında tetiklenir. Bölüm başına konduğunda, ilk satırdan önce çalışır.

## Konuşmayı kaydetmek

```python
game.saves.save("chapter", {"dialogue": dialogue.snapshot(), "flags": flags})

saved = game.saves.load("chapter")
flags = saved["flags"]
if saved["dialogue"] is not None:
    dialogue.restore("res://harbor.dialogue", saved["dialogue"], state=flags)
```

`snapshot()` bir JSON nesnesi döndürür. Konuşma kapalıysa sonuç `None`
olur. Kayıt, bölümü, satırı, yazının görünen kısmını, duraklamayı,
seçili cevabı ve ses konumunu içerir. Uygulanmış olaylar tekrar yayılmaz.
Bir seçim veya olay sırasında kayıt alındıysa sonraki oyun güncellemesi
yarım kalan adımı tamamlar. Dosyadaki bölüm adları ve satır sırası kaydın
dayanağı olduğu için kayıtları aynı diyalog ağacıyla aç. Oyun bayraklarını
ve ödül gibi sonuçları diyalog kaydıyla aynı slota yaz.

## Replik ifadesi, duraklama ve ses

```text
@portrait Ayla left "portraits/ayla.png"
@portrait Ayla left "portraits/ayla_relieved.png" relieved

~ start
Ayla: Sonunda geldin.
@expression relieved
@pause 0.4
@voice "voice/ayla_arrival.ogg"
Ayla: Kapıyı kapatır mısın?
```

`@expression`, `@pause` ve `@voice` hemen önceki repliğe uygulanır.
Duraklama, yazı ve ses başlamadan önce saniye cinsinden bekler.
Bir replikten diğerine geçildiğinde önceki ses kesilir. Ses varsayılan
olarak `SFX` kanalını kullanır. Ayrı bir kanal için `dialogue.voice_bus` ayarla.
`dialogue.voice_enabled = False` yeni replikleri sessiz açar.

## Çeviri ve oyun değerleri

```text
~ start
Ayla: [tr harbor.greeting] Hoş geldin, {player_name}.
- [tr harbor.give] {letter_count} mektup teslim et => END [if has_letter]
- Sonra görüşürüz => END
```

`[tr anahtar]` etiketini replik veya cevap metninin başına yaz.
Katalogda anahtar bulunamazsa etiketten sonraki metin kullanılır.
Katalogları `game.localization.load_catalog(...)` ile veya proje
ayarları üzerinden yükle. `game.locale` açık diyalogda da değiştirilebilir.

```python
box.start("res://harbor.dialogue", state={
    "player_name": "Lale", "letter_count": 2, "has_letter": True,
})
```

`{player_name}` gibi basit adlar `state` içinden okunur. Aynı yer tutucuları
katalog çevirilerinde kullanabilirsin. Eksik bir değer metinde olduğu gibi
görünür. Gerçek süslü parantez için `{{` ve `}}` yaz. Replik ve cevapların
ham metinleri `box.line.text` ve `box.choices` üzerinden erişilebilir.
Çözümlenmiş metin için `box.display_text` ve `box.choice_text(choice)` kullan.

## Diyaloğu önizlemek

```powershell
python -m doku2d.dialogue examples/assets/preview.dialogue --assets examples/assets --locale tr --fallback tr --catalog tr=locale/dialogue-tr.json --catalog en=locale/dialogue-en.json
```

Dosyayı açtıktan sonra listeden bir bölüm seçip **Bölümü oynat** düğmesine bas.
Koşulları tıklayarak açıp kapatabilirsin. Bayraklar, gösterilen cevapları
ve sonraki atlamaları değiştirir. Uyarılar listesi eksik portre ve seslerin
dosyadaki satırını gösterir. Bu varlıklara başvuran replikleri de oynatabilirsin.
**Konumu kaydet** ve **Kayıttan sürdür**, önizleme oturumu içinde çalışır.

Örnek galerisine `python -m examples.gallery` ile girip **Diyalog önizleme**
ekranından aynı dosyayı deneyebilirsin. **Dil** menüsü replik ve cevapları
anında değiştirir. Seçili dilde eksik çeviriler uyarılar listesinde dosya,
satır ve anahtarla gösterilir. **Değerleri uygula** düğmesi, JSON alanındaki
ad ve sayı değişikliklerini açık diyaloğa aktarır.

**Denetle**, seçili başlangıç bölümünden ulaşılamayan bölümleri ve
cevap koşullarının hepsinin yanlış olabildiği bölümleri gösterir.
Denetim dosyadaki koşulları inceler. Python'daki olay işleyicilerinin
durumu nasıl değiştireceğini varsaymaz. Uyarıya tıklayınca bölüm
örnek koşullarla açılır. **Harita**, dosyanın bölümlerini ve olası
geçişlerini gösterir. Dosyayı kaydedince önizleme kendini yeniler.

## Süre, kilit, giriş ve ortak konuşma

```text
~ gate
Bekçi: Dur…[pause=0.3] [shake]Kapı kapanıyor![/shake]
@timeout 12 closed
- Kodu gir => code [if has_letter] [locked "Önce mektubu getir"]
- Geri çekil => closed

~ code
Bekçi: İki basamaklı kodu yaz.
@input gate_code number "Kapı kodu" 10 99
=> shared [if gate_code == 42]
=> closed

~ shared
Bekçi: Fenerdeki görevli sana yolu tarif edecek.
@call "shared-keeper.dialogue" greeting END

~ closed
Bekçi: Bugünlük kapattık.
=> END
```

- `[locked "..."]` koşul yanlışken cevabı görünür bırakır ve kilit nedenini gösterir.
- `@timeout saniye bölüm`, son replik tamamlanınca sayar. Süre ve alt konuşmadan dönüş konumu kayda girer.
- `@input` için `text` sınırları karakter sayısını, `number` sınırları sayı aralığını belirtir. Giriş sonucu değiştirilebilir `state` sözlüğüne yazılır. Koşullarda `==` ve `!=` ile JSON değerlerini karşılaştırabilirsin.
- `@call` içindeki son ad dönüş bölümüdür. Yol, çağıran dosyaya göre çözülür. `END` bulunduğun alt konuşmayı bitirir.
- `[pause=0.3]` daktiloyu replik içinde bekletir. `[shake]`, `[wave]` ve diğer hazır RichLabel efektleri replikte kullanılabilir.
- `box.history` onaylanmış replikleri ve seçilmiş cevapları verir. `DialogueHistory(box)` hazır geçmiş kontrolüdür.
- `SpeechBubble(npc, tr("npc.greeting", default="Selam!"))` kısa bir repliği dünya nesnesine bağlar. `say(...)` ile yeni replik başlatılabilir.
