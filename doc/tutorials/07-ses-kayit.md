# 7. Ses, tercihler ve kayıt yuvası

**Hedef:** Bir ses seviyesini ve oyuncu ilerlemesini ayrı ayrı saklamak.

1. `ses_kayit.py` dosyasına şu kodu koy. Kayıtlar bu örnekte yerel bir
   klasöre yazılır:

   ```python
   from doku2d import Game, JoyButton, Key

   game = Game(save_dir='.ders-kayitlari', persist_preferences=True)
   try:
       game.audio['Music'].volume = 55
       game.input.set_bindings('jump', Key.SPACE, JoyButton(0))
       game.input.joy_deadzone = .25
       game.saves.save('checkpoint', {'version': 1, 'score': 12, 'position': [80, 120]})
       print(game.saves.load('checkpoint'))
   finally:
       game.close()
   ```

2. Çalıştır ve `.ders-kayitlari/settings.json` ile `checkpoint.json`
   dosyalarını aç. Oyuncu tercihleri ve oyun ilerlemesi ayrı tutulur.
3. Oyun klasörüne bir `assets/music.ogg` eklediğinde, oyun kurulumunda
   `Game(asset_root='assets')` ve `game.add(AudioPlayer('res://music.ogg',
   stream=True, loop=True, autoplay=True, bus='Music'))` kullan. `AudioPlayer`
   sınıfını `doku2d` paketinden içe aktar.

**Kontrol:** `Music` seviyesini değiştirince çalan müzik yeni seviyeyi kullanır.

[Sonraki: bölüm geçişi](08-bolumler.md)
