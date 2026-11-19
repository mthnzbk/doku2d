# 9. NPC rotası, görünürlük ve F3

**Hedef:** NPC'nin engelin etrafından dolandığını ve ekran dışındayken rota sorgusunu durdurduğunu görmek.

1. `npc.py` dosyasına küçük bir TileMap ve bir NPC koy:

   ```python
   from sfml.graphics import Image, Texture
   from doku2d import CharacterBody, Color, Game, MapData, ScreenNotifier, TileMap, TileSet

   game = Game(size=(420, 240), debug=True)
   tileset = TileSet(Texture.from_image(Image.create(16, 16, Color.BLUE)))
   tileset.set_solid(0)
   world = TileMap(MapData(size=(22, 12)))
   world.add_tileset(tileset)
   wall = world.add_layer('Walls')
   for y in range(2, 8):
       wall.set_cell((10, y), 0)
   world.enable_collisions('Walls')
   game.add(world)
   npc = game.add(CharacterBody(position=world.map_to_world((3, 5)), radius=5,
                                color=(255, 180, 70)))
   follower = npc.navigate_to(world, world.map_to_world((18, 5)), speed=85)
   game.add(ScreenNotifier(npc, margin=32, auto_process=True))
   follower.arrived.connect(lambda: print('Hedefe ulaştı'))
   game.run()
   ```

2. F3'e bas ve `A*`, `Physics`, `Draw calls` değerlerine bak. İlk rota
   sorgusunda A* etkinliği görülür. NPC hedefte durur.
3. Pencerenin boyutunu değiştirmek mantıksal alanı değiştirmez. Görünürlük
   davranışını denemek için `Camera` ekleyip kamerayı NPC'den uzaklaştır.

**Kontrol:** Turuncu NPC duvarın etrafından dolaşır.

[Sonraki: efekt ve dağıtım](10-dagitim.md)
