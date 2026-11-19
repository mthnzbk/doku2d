# 10. Shader ile dünya efekti ve dağıtım

**Hedef:** Shader varlığını içeren bağımsız bir oyun paketi almak.

1. `egitim/assets/tint.frag` dosyasını oluştur:

   ```glsl
   uniform sampler2D u_texture;
   uniform vec4 tint;

   void main() {
       gl_FragColor = texture2D(u_texture, gl_TexCoord[0].xy) * tint;
   }
   ```

2. Başlangıç projesinin `main()` işlevinde, `Game.from_project(PROJECT)` ile
   `game.run(...)` arasına şu satırları ekle. Dünyanın rengi değişir, HUD kendi
   Canvas'ında kalır:

   ```python
   from doku2d import Color, ShaderMaterial

   material = ShaderMaterial('res://tint.frag')
   material.set_shader_parameter('tint', Color(170, 225, 255))
   game.world.material = material
   ```

3. Motorun kurulu olduğu ortamda Nuitka'yı ve [platform araçlarını](../build.md)
   hazırla. Oyun klasöründen çalıştır:

   ```sh
   doku2d run --frames 3
   doku2d build
   ```

4. Komutun yazdığı ikili dosyayı başka bir çalışma dizininden aç. Dağıtımda
   `dist/<app_id>.dist` klasörünün tamamını gönder.

**Kontrol:** Paketlenmiş oyun shader'ı ve Tiled haritasını kendi varlıklarından okur.

[Ders listesi](README.md) · [API başvurusu](../api-reference.md)
