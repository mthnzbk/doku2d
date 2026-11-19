# 8. Bölüm geçişi ve yaşam döngüsü

**Hedef:** Bölüm değişince eski kontrolleri ve bağlantıları birlikte kaldırmak.

1. `bolum.py` dosyasına iki bölümden oluşan küçük bir akış yaz:

   ```python
   from doku2d import Button, Game, Label

   game = Game(size=(540, 210))
   title = game.add(Label(text='Kalıcı üst menü'), persistent=True)
   title.position = (28, 18)
   scope = None

   def open_room(index):
       global scope
       if scope is not None:
           scope.close()
       scope = game.create_scope()
       caption = scope.add(Label(text=f'Bölüm {index}'))
       caption.position = (28, 64)
       next_room = scope.add(Button(text='Diğer bölüme geç'))
       next_room.position, next_room.size = (28, 116), (240, 40)
       scope.connect(next_room.pressed, lambda: open_room(3-index))

   open_room(1)
   game.run()
   ```

2. Düğmeye tekrar tekrar bas. Her seferinde bölüm etiketi ve düğme yeni
   kapsama eklenir. Eski bağlantılar `close()` ile kalkar.
3. Gerçek oyunda `scope.add(game.resources.load_map(...))` ile bölümün haritasını
   ekle. Sonradan başka bir yerden eklenen bölüm nesnesine `scope.add` veya
   `game.add(nesne, scope=scope)` kullan.

**Kontrol:** Üst menü görünür kalır ve bölüm değiştikçe kontroller birikmez.

[Sonraki: NPC ve debug](09-npc.md)
