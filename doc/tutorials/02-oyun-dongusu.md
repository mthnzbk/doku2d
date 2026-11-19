# 2. Game, Entity ve mantıksal ekran

**Hedef:** Pencere büyüse de oranı bozulmayan ilk oyun nesnesini çizmek.

1. Aşağıdaki kodu `ilk_oyun.py` dosyasına koy:

   ```python
   from sfml.graphics import RectangleShape
   from doku2d import Color, Entity, Game

   class Box(Entity):
       def on_ready(self):
           self.shape = RectangleShape((24, 24))
           self.shape.fill_color = Color.GREEN

       def update(self, dt):
           self.position += self.input.get_vector() * 120 * dt

       def render(self, target, states):
           target.draw(self.shape, states)

   game = Game(size=(320, 180), window_size=(960, 540), scale_mode='fit')
   box = game.add(Box())
   box.position = (148, 78)
   game.run()
   ```

2. `python ilk_oyun.py` ile çalıştır. `on_ready` ilk kuruluşu, `update(dt)`
   karedeki hareketi, `render` çizimi yapar. `dt` saniyedir.
3. Pencereyi dikey yap. Mantıksal alan 320×180 kalır. Oyun girdisindeki fare
   konumunu mantıksal koordinata çevirmek için `game.window_to_screen(pixel)`
   kullan. Boş kenarlarda `None` döner.

**Kontrol:** Kutunun şekli korunur ve oklarla hareket eder.

[Sonraki: platform karakteri](03-platform.md)
