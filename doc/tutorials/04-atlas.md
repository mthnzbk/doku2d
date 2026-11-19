# 4. Sprite atlası ve animasyon

**Hedef:** Aynı dokuya ait kareleri isimle seçip animasyon oynatmak.

1. `atlas_oyunu.py` dosyasında iki küçük görsel oluşturup paketle:

   ```python
   from sfml.graphics import Image
   from doku2d import AnimatedSprite, Color, Game, Sprite, SpriteAtlas

   atlas = SpriteAtlas.pack({
       'idle_0': Image.create(20, 20, Color.RED),
       'idle_1': Image.create(24, 20, Color.GREEN),
   })
   game = Game(size=(320, 180), debug=True)
   actor = game.add(AnimatedSprite())
   actor.position = (120, 90)
   actor.add_animation('idle', [atlas['idle_0'], atlas['idle_1']], fps=4)
   actor.play('idle')
   marker = game.add(Sprite(atlas['idle_1']))
   marker.position = (200, 90)
   game.run()
   ```

2. Oyun açıkken F3'e bas. İki sprite aynı Canvas ve dokuda art arda çizildiği
   için birlikte gönderilir.
3. Gerçek projede `SpriteAtlas.pack()` ile PNG'leri birleştirebilir veya
   `game.resources.load_atlas('res://art/actors.json')` ile hazır atlas yükleyebilirsin.

**Kontrol:** Soldaki renkler değişirken sağdaki sprite aynı kalır.

[Sonraki: Tiled ve kamera](05-tiled.md)
