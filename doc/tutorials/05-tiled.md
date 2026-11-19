# 5. Tiled haritası ve kamera

**Hedef:** Başlangıç şablonundaki haritayı ayrı bir giriş dosyasında yüklemek.

1. Birinci dersteki `egitim` projesinde `harita.py` dosyası aç. `assets/level.tmj`
   ve haritanın doku dosyaları yerinde kalsın.
2. Haritayı `res://` yolu üzerinden yükle:

   ```python
   from pathlib import Path
   from doku2d import Camera, CharacterBody, Game

   class Player(CharacterBody):
       def physics_update(self, dt):
           self.velocity = self.input.get_vector() * 130
           self.move_and_slide()

   game = Game.from_project(Path(__file__).with_name('doku2d.toml'))
   world = game.add(game.resources.load_map('res://level.tmj', collisions=True))
   player = game.add(Player(position=(120, 180), radius=8, color=(120, 230, 210)))
   camera = game.add(Camera())
   camera.follow(player, smoothing=8)
   camera.bounds = world.world_bounds
   camera.zoom = (1.25, 1.25)
   game.run()
   ```

3. `python harita.py` ile çalıştır. Koddan `world.world_to_map(player.position)`
   ile karakterin hücresini, `world.map_to_world((4, 5))` ile hücre merkezini al.

**Kontrol:** Kamera karakteri takip eder. Katı karolar hareketi engeller.

[Sonraki: menü ve yerelleştirme](06-ui.md)
