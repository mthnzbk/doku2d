# Desteklenen API ve geçiş notları

Paket kökünün __all__ listesi yalnızca kullanılabilir API'yi içerir. Yardımcı
modüller import * ile dışarı sızmaz. Oyunun yaşam döngüsü Entity / Game üzerinden,
katman çizimi Canvas üzerinden yürür; SceneTree, parent ve root eklenmedi.

| Eski taslak | Çalışan karşılık |
| --- | --- |
| CanvasModulate | AmbientLight; eski ad aynı sınıfın uyumluluk adıdır. |
| Gece-gündüzü elle yönetme | DayNightCycle. |
| CanvasGroup fit_margin/clear_margin/use_mipmaps | Gerçek grup bileşimi, color ve opacity; etkisiz alanlar kaldırıldı. |
| Resource | Resources; eski ad uyumluluk için korunur. |
| Parallax adlı etkisiz Entity | Canvas(parallax=...) veya TileLayer.parallax. |
| CollisionShape2D / CollisionPolygon2D | Gövdenin shape alanında Box/Circle/Polygon/Segment. |
| RayCast2D taslağı | RayCast veya game.physics.raycast. |
| Shader adlı boş wrapper | Özel Entity.render içinde sfml.graphics.Shader. |
| Line, Path2D, PathFollow taslakları | Desteklenen dışa aktarımdan kaldırıldı; henüz çalışan motor API'si değiller. |
| Entity.material | İşlenmeyen alan kaldırıldı; render kodunda gerçek RenderStates kullan. |
| CollisionObject pickable/priority/disable_mode ve kullanılmayan mouse sinyalleri | Yalnızca doğrulanan layer/mask filtre kaynağı kaldı. |
| Marker.gizmo_extents | Marker adlandırılmış konum/dönüşüm noktasıdır; çizilmeyen gizmo ayarı kaldırıldı. |

```python
from doku2d import RayCast
ray = game.add(RayCast(position=(100, 100), target_position=(200, 0)))
ray.exclude = (player,)
hit = ray.force_update()
if hit:
    print(hit.collider, hit.point, hit.normal)
```

Ray'in target_position alanı yerel bir vektördür; kaydın ardından kare güncellemesinde
sorgulanır. enabled, collision_mask, include_areas ve exclude gerçek sorguyu etkiler.
is_colliding/get_collider/get_collision_point/get_collision_normal son sonucu verir.
Parent olmadığı için eski exclude_parent benzeri ayarlar yoktur.

Kaynak alan constructor'lar ilk argümanda kaynağı, ad için name= parametresini kullanır.
Konumsal kaynaklar position= ve açık özellikler üzerinden ayarlanır. Grafik kaynakları
Game'e eklenince ortak önbelleğe bağlanır; yollar proje kaynak köküne göre çözülür.
Özellikler typed/finite/range kontrolü yapar; vektör getter'ları kopya döndürür.
Bir vektörü değiştirmek için örneğin obj.position=(x,y) veya Tween'in position:x yolu
kullanılır. Tamamlanma/başlatma sinyallerinin argümanları ilgili özellik rehberinde
belirtilmiştir; Sprite kare animasyonu ile Timeline ad sinyalleri farklıdır.

Bu temizlik eski, işlevsiz prototip isimlerini kaldırır. Önceki projeler için
uyumluluk yalnızca çalışan Resource ve CanvasModulate adlarında korunur.
