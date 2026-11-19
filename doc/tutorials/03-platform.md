# 3. Platform karakteri ve tek yönlü zemin

**Hedef:** Altından geçilen bir platforma zıplamak ve aşağı inmek.

1. `platform.py` dosyasına şu kodu koy:

   ```python
   from doku2d import CharacterBody, Game, StaticBody

   class Player(CharacterBody):
       def physics_update(self, dt):
           self.velocity = (self.input.get_axis('move_left', 'move_right') * 170,
                            self.velocity.y)
           if self.input.is_action_just_pressed('jump'):
               if not (self.input.is_action_pressed('move_down') and self.drop_through()):
                   self.jump(400)
           self.move_and_slide()

   game = Game(size=(480, 280))
   game.physics.gravity = (0, 800)
   game.add(StaticBody(position=(240, 260), size=(460, 16), color=(90, 120, 150)))
   game.add(StaticBody(position=(225, 180), size=(180, 8),
                       one_way=True, color=(120, 210, 175)))
   game.add(Player(position=(225, 225), size=(18, 24), motion_mode='grounded',
                   color=(255, 200, 105)))
   game.run()
   ```

2. Space ile zıpla. Karakter platformu geçip üstüne insin.
3. Platformdayken aşağı ve Space'e bas. `drop_through` yalnızca tek yönlü
   yüzeyde etkinleşir. Normal zemin altta durdurur.

**Kontrol:** Hız atamasında düşey hızı koruduğun için yerçekimi etkisini sürdürür.

[Sonraki: atlas animasyonu](04-atlas.md)
