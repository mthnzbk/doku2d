"""Generate the API inventory from the current public exports and returned types."""
import argparse
import ast
from collections import defaultdict
from importlib import import_module
import inspect
from pathlib import Path
import re
import sys
from textwrap import dedent


ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT/'doc'/'api-reference.md'
sys.path.insert(0, str(ROOT))


CLASS_SUMMARIES = {
    'Binding': 'Animasyon hedefinin bir özelliğini okur ve yazar.',
    'CanvasEffect': 'Canvas üzerine uygulanan shader ve parametreleri taşır.',
    'LightingRenderer': 'Işıkları ve gölgeleri birleştirir.',
    'MeasuredTexture': 'Kare istatistiklerine çizim sayılarını ekleyen render dokusu.',
    'MeasuredWindow': 'Kare istatistiklerine çizim sayılarını ekleyen pencere.',
    'SpriteBatch': 'Uyumlu sprite köşelerini aynı çizim için toplar.',
    'TileCollisions': 'TileMap verisinden fizik gövdeleri üretir ve yeniler.',
    'TileMapChunk': 'Bir akış bölgesinin yerel haritasını ve ek nesnelerini taşır.',
    'TileMapStream': 'Yakın TileMap bölgelerini yükler ve uzak bölgeleri kaldırır.',
    'ViewCuller': 'Kamera dışında kalan çizilebilir nesneleri eler.',
    'Game': 'Oyun döngüsü, nesne kayıtları, pencere ve ortak motor servisleri.',
    'Object': 'Motorun adlandırılabilir ortak tabanı.',
    'Entity': 'Konum, Canvas, yaşam döngüsü ve işlem modu olan oyun nesnesi.',
    'Canvas': 'Çizim sırası, kamera/parallax, aydınlatma ve efekt ayarları.',
    'CanvasGroup': 'Birden çok görseli tek yüzeyde birleştirip renklendirir.',
    'EntityScope': 'Bir bölüme ait nesneleri, bağlantıları ve bekleyen işleri birlikte temizler.',
    'Resources': 'Projeye göre çözülen dosya yolları ve kaynak önbellekleri.',
    'Settings': 'Kullanıcı ayarları için JSON destekli sözlük.',
    'SaveStore': 'Adlandırılmış JSON kayıt yuvalarını okur ve atomik yazar.',
    'SaveError': 'Geçersiz kayıt içeriği hatası.',
    'Services': 'Oyun ömrü boyunca paylaşılan adlandırılmış nesneler.',
    'Input': 'Farklı giriş aygıtlarını isimli oyun eylemlerine eşler.',
    '_BindingCapture': 'Bir eylem için bekleyen tuş yakalama isteğini taşır.',
    'Signal': 'Bir olaya dinleyici bağlar ve olay oluşunca çağırır.',
    'Keyboard': 'SFML klavye tuşu sabitleri ve doğrudan tuş sorguları.',
    'Color': 'SFML RGBA rengi.',
    'Vector2': 'SFML iki bileşenli vektör.',
    'JoyAxis': 'Yön, ölü bölge ve isteğe bağlı aygıt taşıyan analog eksen bağı.',
    'JoyButton': 'Gamepad düğmesi bağı.',
    'MouseButton': 'Fare düğmesi bağı.',
    'ProjectConfig': 'doku2d.toml ayarları ve çözülmüş proje yolları.',
    'Localization': 'Oyun başına dil katalogları ve çeviri çözümleme.',
    'LocalizedText': 'Arayüzde dinamik çözülen çeviri anahtarı ve değerleri.',
    'Control': 'Odak, boyut, görünüm ve girdi davranışı olan GUI tabanı.',
    'UI': 'Kontrolleri yerleştirir ve odak, işaretçi ve popup olaylarını yönlendirir.',
    'Theme': 'Kontrol renkleri, font, köşe ve boşluk ayarları.',
    'Anchor': 'Kontrolü mantıksal ekranın bir noktasına bağlayan sabitler.',
    'HBox': 'Kontrolleri yatay sıralar.', 'VBox': 'Kontrolleri dikey sıralar.',
    'Box': 'Yatay veya dikey kutu yerleşimi.', 'Grid': 'Kontrolleri sütunlara böler.',
    'Center': 'Kontrolleri merkezler.', 'Layout': 'Kontrol yerleşimleri için ortak taban.',
    'Panel': 'Tema yüzeyi ve kenarlığı çizer.', 'Label': 'Statik metin çizer.',
    'RichLabel': 'Biçimli metin, bağlantı ve karakter efektlerini çizer.',
    'LineEdit': 'Tek satırlık düzenlenebilir metin ve parola kutusu.',
    'TextEdit': 'Çok satırlı metin, seçim, kaydırma ve satır numarası.',
    'BaseButton': 'Basış, odak, ikon ve seçili durum davranışı.',
    'Button': 'Metin ve isteğe bağlı ikon içeren standart düğme.',
    'CheckBox': 'İşaretli veya işaretsiz seçenek.', 'CheckButton': 'Açma kapama anahtarı.',
    'TextureButton': 'Duruma göre doku kullanan düğme.',
    'ItemList': 'Tekli veya çoklu seçim yapılabilen liste.',
    'OptionButton': 'Öğe seçmek için açılır menü.', 'TabBar': 'Sekme seçici ve sekme sinyalleri.',
    'ColorPickerButton': 'Renk seçici açan düğme.', 'Item': 'Listede veya açılır menüde gösterilen öğe verisi.',
    'NinePatchRect': 'Dokuyu köşeleri koruyarak dokuz parçayla ölçekler.',
    'Range': 'Alt ve üst sınırla sayısal değer tutan kontrol tabanı.',
    'Slider': 'Sürüklenerek sayısal değer seçilen kontrol.',
    'SpinBox': 'Yazılabilir ve adımlı sayısal alan.', 'ScrollBar': 'Kaydırma konumu ve sayfa miktarı.',
    'ProgressBar': 'Sayısal ilerlemeyi dolgu olarak gösterir.',
    'TextureProgressBar': 'İlerlemeyi dokulu dolgu olarak gösterir.',
    'TouchScreenButton': 'Dokunmatik basışları bir eyleme bağlar.',
    'VirtualJoystick': 'Dokunmatik yön vektörü ve hareket sinyalleri.',
    'CharacterEffect': 'RichLabel efekt çağrısında tek karakterin düzenlenebilir görünümü.',
    'Sprite': 'Doku, kare veya atlas bölgesi çizen nesne.',
    'AnimatedSprite': 'Sprite sheet ve atlas kareleri arasında oynatma.',
    'Animation': 'Kareler, FPS ve döngü bilgileri.',
    'MotionAnimation': 'Gövde hareketine göre sprite animasyonu seçer.',
    'AnimationPlayer': 'Adlandırılmış zaman çizelgelerini oynatır.',
    'Timeline': 'Özellik anahtarları ve çağrılar için zaman çizelgesi.',
    'Tween': 'Değerleri süre boyunca değiştirir veya bir çağrı zamanlar.',
    'PropertyTweener': 'Bir Tween özelliğinin geçiş ayarları.',
    'ShaderMaterial': 'Doku girdisi ve değiştirilebilir GLSL parametreleri.',
    'SpriteAtlas': 'Aynı dokuyu paylaşan isimli bölgeler.',
    'AtlasRegion': 'Bir atlas dokusu içindeki piksel dikdörtgeni.',
    'ScreenNotifier': 'Kamera görünürlüğü sinyalleri ve isteğe bağlı işlem durdurma.',
    'Camera': 'Dünya görünümü, takip, yakınlaştırma, sınırlar ve sarsıntı.',
    'Marker': 'Konum ve dönüşüm referansı.',
    'Light': 'Işık rengi, gücü, maske ve gölge ayarları.',
    'PointLight': 'Bir noktadan çevreye yayılan ışık.',
    'DirectionalLight': 'Belirli yönde yayılan ışık ve gölge.',
    'LightOccluder': 'Işık ışınlarını kesen şekil.',
    'AmbientLight': 'Canvas için geniş alan ortam rengi.',
    'DayNightCycle': 'Zamana göre ortam rengini değiştirir.',
    'Particles': 'CPU parçacık simülasyonu ve yayıcı ayarları.',
    'TileMap': 'Katmanları, koordinat dönüşümlerini ve hücre yol bulmayı yönetir.',
    'TileLayer': 'TileMap içinde çizilebilir ve düzenlenebilir katman.',
    'TileSet': 'Karo dokuları, özellikleri, animasyonları ve autotile kuralları.',
    'TileCell': 'Karo kimliği, tileset ve çevirme bilgisi.',
    'TiledParser': 'Orthogonal Tiled dosyalarını okur.',
    'MapData': 'Ayrıştırılmış Tiled harita verisi.',
    'MapObject': 'Tiled nesne geometrisi ve özel özellikleri.',
    'LayerData': 'Ayrıştırılmış Tiled katmanı.', 'TileSetData': 'Ayrıştırılmış Tiled karo seti.',
    'AutoTile': 'Komşu hücre maskelerine göre karo seçer.',
    'PhysicsWorld': 'Çarpışma dünyası, yerçekimi ve fizik sorguları.',
    'PhysicsBody': 'Şekil, hız, maske ve temas bilgisi olan fizik tabanı.',
    'CharacterBody': 'Kontrollü karakter hareketi, platform, zıplama ve NPC takibi.',
    'RigidBody': 'Kuvvet ve darbelerle hareket eden dinamik gövde.',
    'StaticBody': 'Fizik adımında kendiliğinden hareket etmeyen çarpışma gövdesi.',
    'AnimatableBody': 'Programlı hareketi diğer fizik gövdelerine aktarır.',
    'Area': 'Engellemeden giriş, çıkış ve örtüşme algılar.',
    'CollisionObject': 'Fizik katmanı ve maskesi ayarları.',
    'Collision': 'Bir fizik teması, ışın veya şekil sorgusunun sonucu.',
    'RayCast': 'Bir doğrultuda temas arayan oyun nesnesi.',
    'ShapeCast': 'Bir daire veya kutuyu süpürerek ilk fizik temasını izleyen nesne.',
    'Box shape': 'Dikdörtgen fizik şekli.',
    'Circle': 'Daire fizik şekli.', 'Polygon': 'Dışbükey çokgen fizik şekli.',
    'Segment': 'Kalınlığı olan kenar fizik şekli.',
    'PathFollower': 'NPC’yi bir TileMap rotası boyunca sürer.',
    'AudioPlayer': 'Ses veya akışkan müzik oynatır.',
    'PositionalAudio': 'Uzaklık ve stereo yönü hesaplanan oynatıcı.',
    'AudioListener': 'Konumsal sesin dinleme merkezi.',
    'AudioBus': 'Bir ses grubunun seviyesini ve mute durumunu tutar.',
    'AudioMixer': 'Oyunun ses gruplarını ve birleşik ses seviyelerini yönetir.',
    'DebugOverlay': 'Debug katmanı, kare ölçümleri ve çizim sayacı.',
}

MEMBER_SUMMARIES = {
    'position': 'Nesnenin konumu.', 'rotation': 'Derece cinsinden dönüş.', 'scale': 'Eksen başına ölçek.',
    'size': 'Genişlik ve yükseklik.', 'visible': 'Çizime katılma durumu.', 'enabled': 'Özelliğin etkinliği.',
    'material': 'Çizime uygulanacak ShaderMaterial.', 'canvas': 'Nesnenin çizildiği katman.',
    'z_index': 'Aynı katmandaki çizim önceliği.', 'process_mode': 'Nesnenin duraklatma ve güncelleme kuralı.',
    'texture': 'Kullanılan görsel kaynak.', 'frame': 'Geçerli animasyon karesi.',
    'text': 'Gösterilen veya düzenlenen metin.', 'placeholder': 'Boş girişte gösterilen ipucu.',
    'color': 'Çizim veya aydınlatma rengi.', 'tint': 'Çizim rengi çarpanı.', 'opacity': 'Çizim opaklığı.',
    'name': 'Nesnenin veya kaynağın adı.', 'target': 'Takip edilen nesne veya hedef nokta.',
    'loop': 'Bittiğinde baştan devam etme durumu.', 'playing': 'Oynatma durumu.',
    'offset': 'Başlangıç konumuna göre yerel kaydırma.', 'radius': 'Yarıçap.',
    'velocity': 'Gövdenin hızı.', 'collision_mask': 'Hangi fizik katmanlarının dikkate alınacağı.',
    'collision_layer': 'Nesnenin fizik kategori bitleri.', 'friction': 'Temas sürtünmesi.',
    'elasticity': 'Çarpışma sekmesi.', 'one_way': 'Platformda yalnızca üst yüzeyin destek olması.',
    'direction': 'Hareket veya yayılım yönü.', 'volume': '0–100 arası ses seviyesi.',
    'muted': 'Ses çıkışının susturulması.', 'bus': 'Oynatıcının ses grubu.',
    'value': 'Kontrolün geçerli değeri.', 'min_value': 'En küçük değer.', 'max_value': 'En büyük değer.',
    'step': 'Değerin değişim adımı.', 'disabled': 'Etkileşimin kapalı olması.',
    'font': 'Metin çiziminde kullanılan font.', 'theme': 'Kontrolün görünüm ayarları.',
    'font_size': 'Metin boyutu.', 'path': 'Kalan rota noktaları veya dosya yolu.',
    'locale': 'Etkin dil etiketi.', 'fallback_locale': 'Eksik çeviride kullanılan yedek dil.',
    'scope': 'Sahip olunan nesne kapsamı.', 'objects': 'Sistemin kayıtlı nesneleri.',
    'resources': 'Oyun kaynak önbelleği.', 'settings': 'Oyuncu ve oyun ayarları.',
    'saves': 'Adlandırılmış kayıt yuvalarına erişim.', 'ui': 'Arayüz denetleyicisi.',
    'debug': 'Debug katmanı ve ölçümler.', 'screen_entered': 'İzlenen bölge ekrana girdiğinde.',
    'screen_exited': 'İzlenen bölge ekrandan çıktığında.', 'on_screen': 'Son görünürlük hesabının sonucu.',
    'arrived': 'NPC hedefe ulaştığında.', 'path_failed': 'NPC için rota bulunamadığında.',
    'ready': 'Nesne ilk kez eklenip hazır olduğunda.', 'added': 'Nesne oyuna eklendiğinde.',
    'removed': 'Nesne oyundan kaldırıldığında.', 'finished': 'Oynatma veya işlem tamamlandığında.',
    'pressed': 'Düğme etkinleştirildiğinde.', 'value_changed': 'Değer değiştiğinde.',
    'text_changed': 'Düzenlenen metin değiştiğinde.', 'locale_changed': 'Etkin dil değiştiğinde.',
    'resized': 'Kontrol boyutu değiştiğinde.', 'draw_calls': 'Son karedeki motor çizim çağrısı sayısı.',
    'find_path': 'Başlangıçtan hedefe hücre rotası bulur.',
    'find_world_path': 'Rota üzerindeki dünya koordinatlarını döndürür.',
    'navigate_to': 'Karakter için otomatik rota takibi başlatır.',
    'world_to_map': 'Dünya konumunu TileMap hücresine dönüştürür.',
    'map_to_world': 'Hücre merkezini dünya koordinatında verir.',
    'world_to_screen': 'Dünya konumunu mantıksal ekrana çevirir.',
    'screen_to_world': 'Mantıksal ekran noktasını dünya konumuna çevirir.',
    'window_to_world': 'Fiziksel pencere noktasını dünya konumuna çevirir.',
    'raycast': 'Işın üzerindeki ilk uygun çarpışmayı sorgular.',
    'move_and_slide': 'Karakterin hızını temaslara göre kaydırarak uygular.',
    'drop_through': 'Tek yönlü platformun içinden düşmeyi başlatır.',
    'create_scope': 'Birlikte temizlenebilecek nesne kapsamı oluşturur.',
    'create_render_texture': 'Oyunun çizim sayacına katılan ara yüzey oluşturur.',
    'add': 'Bu sisteme bir öğe ekler.', 'remove': 'Bu sistemden bir öğe kaldırır.',
    'clear': 'Geçerli öğeleri veya durumu temizler.', 'connect': 'Sinyale dinleyici ekler.',
    'disconnect': 'Dinleyici bağlantısını kaldırır.', 'emit': 'Sinyali dinleyicilere gönderir.',
    'start': 'İşlemi başlatır.', 'play': 'Oynatmayı başlatır.', 'pause': 'İşlemi duraklatır.',
    'stop': 'Etkin işlemi durdurur.', 'resume': 'Duraklatılan işlemi sürdürür.',
    'save': 'Güncel durumu veya veriyi saklar.', 'load': 'Saklanan veriyi yükler.',
    'render': 'Nesneyi verilen hedefe çizer.', 'update': 'Bir oyun adımı işler.',
    'physics_update': 'Sabit fizik adımında çağrılır.', 'handle_event': 'Girdiyi işler ve tüketilme durumunu bildirir.',
    'arrange': 'Kontrol ve alt yerleşim boyutlarını hesaplar.',
}

PREFIXES = {'get': 'Döndürür', 'set': 'Ayarlar', 'is': 'Durumu sorgular', 'has': 'Varlığı sorgular',
            'load': 'Yükler', 'from': 'Veriden oluşturur', 'create': 'Oluşturur', 'add': 'Ekler',
            'remove': 'Kaldırır', 'apply': 'Uygular', 'reset': 'Sıfırlar', 'enable': 'Etkinleştirir',
            'disable': 'Kapatır', 'update': 'Günceller', 'on': 'Yaşam döngüsü kancası'}

MEMBER_SUMMARIES.update({
    'ambient': 'Katmanın ortam ışığından etkilenmesini belirler.',
    'order': 'Katmanların çizim sırasını belirler.',
    'parallax': 'Kamera hareketinin katmana uygulanan oranıdır.',
    'screen_space': 'Katmanı pencere içindeki mantıksal ekran koordinatlarında çizer.',
    'light_mask': 'Işık alan nesneleri bit maskesiyle eşleştirir.',
    'fps': 'Kare hızını saniyede kare olarak verir.',
    'fps_limit': 'Kare hızı üst sınırıdır.',
    'frame_ms': 'Kare süresini milisaniye cinsinden verir.',
    'path_queries': 'Karedeki yol arama sorgularının sayısıdır.',
    'tile_chunks': 'Karede çizilen karo kümelerinin sayısıdır.',
    'can_process': 'Nesnenin güncellenmeye uygun olup olmadığını sorgular.',
    'destroy': 'Nesneyi bağlı olduğu oyundan kaldırır.',
    'game': 'Nesnenin veya hizmetin bağlı olduğu Game örneğidir.',
    'input': 'Oyunun eylem eşlemelerine ve girdi durumuna erişim sağlar.',
    'transform': 'Konum, ölçek ve dönüşten oluşan çizim dönüşümüdür.',
    'app_id': 'Oyun verileri ve paketleme için kullanılan proje kimliğidir.',
    'audio': 'Ses veri yollarına ve oynatıcılara erişim sağlar.',
    'audio_listener': 'Konumsal ses hesabında kullanılacak dinleyicidir.',
    'call_deferred': 'Fonksiyonu güvenli güncelleme noktasına erteler.',
    'camera': 'Dünya görünümünü belirleyen etkin kameradır.',
    'clear_color': 'Yeni kare başında uygulanan arka plan rengidir.',
    'close': 'Kaynakları kapatır ve yaşam döngüsünü sonlandırır.',
    'closed': 'Örneğin kapatıldığını bildirir.',
    'draw_list': 'Kayıtlı nesneleri çizim sırasıyla verir.',
    'flush_deferred': 'Bekleyen ekleme, çıkarma ve ertelenmiş çağrıları işler.',
    'localization': 'Çeviri kataloglarına ve dil seçimine erişim sağlar.',
    'make_view': 'Canvas ve etkin kameraya uygun SFML görünümünü oluşturur.',
    'paused': 'Nesne veya oyunun geçici duraklama durumudur.',
    'physics': 'Yerçekimi ve fizik sorguları için fizik dünyasını verir.',
    'physics_fps': 'Saniyedeki sabit fizik adımı sayısıdır.',
    'physics_interpolation': 'Fizik adımları arasında görsel konum ve dönüşü yumuşatır.',
    'render_position': 'Çizimde kullanılan konumdur.',
    'render_rotation': 'Çizimde kullanılan açı, derece cinsindendir.',
    'render_transform': 'Çizimde kullanılan dönüşümdür.',
    'reset_physics_interpolation': 'Önceki fizik pozunu temizleyip gövdeyi güncel pozunda çizer.',
    'project_root': 'Proje ayarlarının bulunduğu temel dizindir.',
    'quit': 'Oyun döngüsünden çıkış ister.',
    'run': 'Oyun döngüsünü başlatır. max_frames kısa doğrulamalar için kare sayısını sınırlar.',
    'running': 'Döngünün çalışıp çalışmadığını gösterir.',
    'scale_mode': 'Mantıksal oyun alanının pencereye nasıl ölçekleneceğini seçer.',
    'screen_to_window': 'Mantıksal ekran koordinatını pencere pikseline çevirir.',
    'world_to_window': 'Dünya noktasını kamera ve Canvas üzerinden pencere pikseline çevirir.',
    'services': 'Oyuna kaydedilmiş servisleri verir.',
    'title': 'Pencere veya sekmede gösterilen başlıktır.',
    'window': 'Etkin SFML penceresini verir.',
    'window_size': 'Pencerenin piksel cinsinden boyutudur.',
    'window_icon': 'Pencere açıldığında yüklenen simge dosyasının yoludur.',
    'build_icon': 'Windows derlemesinin ICO simge dosyasının yoludur.',
    'world': 'Oyunun varsayılan dünya Canvas’ıdır.',
    'action_press': 'Eyleme programatik basış ve güç değeri gönderir.',
    'action_release': 'Programatik basışı ilgili kaynak için kaldırır.',
    'actions': 'Kayıtlı girdi eylemlerini verir.',
    'bind': 'Tuş, fare veya kontrolcü girdisini bir eyleme bağlar.',
    'capture_binding': 'Sıradaki tuş, gamepad düğmesi veya eşik üstü eksen hareketini eyleme atar.',
    'cancel_binding_capture': 'Bekleyen tuş yakalamayı iptal eder.',
    'binding_capture_action': 'Girdi bekleyen eylemin adını verir.',
    'joy_deadzone': 'Kontrolcü çubuğundaki küçük girdilerin yok sayıldığı eşiktir.',
    'release_source': 'Bir kaynağın ürettiği tüm etkin basışları kaldırır.',
    'translate': 'Etkin katalogdaki anahtarı çözer ve metindeki değişkenleri yerleştirir.',
    'cache_info': 'Türlerine göre önbelleğe alınmış kaynak sayılarını verir.',
    'preload': 'Kaynakları ilk kullanımdan önce önbelleğe alır.',
    'unload': 'Belirtilen kaynak için önbellek girdisini kaldırır.',
    'defer': 'İlgili kapsam canlı kaldığı sürece ertelenmiş çağrıyı yürütür.',
    'members': 'Kapsamın veya grubun bağlı nesnelerini verir.',
    'map_to_local': 'Karo hücresini TileMap’in yerel koordinatına çevirir.',
    'local_to_map': 'TileMap’in yerel koordinatından karo hücresini bulur.',
    'erase_cell': 'Katmandaki belirtilen karo hücresini temizler.',
    'cells': 'Katmanın hücre konumlarını ve karo atamalarını taşır.',
    'chunk': 'Karo verilerinin işlendiği hücre grubudur.',
    'tile_size': 'Bir karonun piksel boyutudur.',
    'tile_id': 'Karonun tileset içindeki numarasıdır.',
    'firstgid': 'Tileset’in Tiled haritasındaki ilk genel karo kimliğidir.',
    'tilesets': 'Haritaya ekli karo kaynaklarını verir.',
    'autotiles': 'Komşuluk kurallarıyla seçilen otomatik karo tanımlarıdır.',
    'paint_terrain': 'Hücreye arazi atar ve komşu karo seçimlerini günceller.',
    'navigation': 'Haritanın rota bulma verilerine erişim sağlar.',
    'follow': 'Kameraya izlenecek nesneyi ve takip ayarını verir.',
    'bounds': 'Hareket, çizim veya sorgunun dikdörtgen sınırlarıdır.',
    'shake': 'Geçici kamera sarsıntısı başlatır.',
    'stop_shake': 'Sürmekte olan kamera sarsıntısını bitirir.',
    'zoom': 'Kameranın yakınlaştırma oranıdır.',
    'floor_probe': 'Karakterin altındaki zemini arayan fizik sorgusudur.',
    'floor_layers': 'Zemin temasında dikkate alınacak fizik katmanlarıdır.',
    'wall_layers': 'Duvar temasında dikkate alınacak fizik katmanlarıdır.',
    'gravity_scale': 'Dünya yerçekiminin gövdeye uygulanan çarpanıdır.',
    'jump': 'Karaktere yukarı doğru sıçrama hızı verir.',
    'teleport': 'Gövdeyi normal hareket adımını kullanmadan konumlandırır.',
    'safe_margin': 'Karakterin temas sorgularındaki mesafe payıdır.',
    'motion_mode': 'Karakterin zeminli veya serbest hareket modelidir.',
    'up_direction': 'Zemin ve tavan ayrımı için kullanılan yukarı vektörüdür.',
    'monitoring': 'Alan algılamasının çalışıp çalışmadığını belirler.',
    'monitorable': 'Alanın diğer algılayıcılar tarafından görülmesini belirler.',
    'angular_velocity': 'Birim zamanda gerçekleşen açısal değişimdir.',
    'linear_velocity': 'Gövdenin doğrusal hız vektörüdür.',
    'occluder': 'Işığı keserek gölge oluşturacak çizim geometrisidir.',
    'energy': 'Işığın parlaklık çarpanıdır.',
    'mask': 'Katılım veya çizim filtresini belirleyen bit maskesidir.',
    'alive_count': 'O anda etkin olan parçacık sayısıdır.',
    'color_ramp': 'Parçacığın ömrü boyunca örneklenen renk geçişidir.',
    'emitting': 'Yayıcının yeni parçacık üretip üretmediğini belirler.',
    'seed': 'Yinelenebilir rastgelelik için başlangıç değeridir.',
    'lifetime': 'Parçacığın yaşama süresidir.',
    'bbcode_enabled': 'Zengin metinde BBCode etiketlerini yorumlar.',
    'clip_text': 'Metni kontrolün görünür alanıyla sınırlar.',
    'editable': 'Metnin kullanıcı tarafından değiştirilebilirliğini belirler.',
    'secret': 'Girdi karakterlerini gizler.',
    'secret_character': 'Gizli girdide her karakter yerine gösterilen işarettir.',
    'h_scrollbar': 'Yatay kaydırma çubuğuna erişim verir.',
    'v_scrollbar': 'Dikey kaydırma çubuğuna erişim verir.',
    'grab_focus': 'Klavye odağını bu kontrole alır.',
    'release_focus': 'Kontrolün klavye odağını bırakır.',
    'select_all': 'Tüm metni veya seçilebilir öğeleri seçer.',
    'selected_text': 'Girdi alanındaki seçili metni verir.',
    'selected_indices': 'Seçili liste öğelerinin indekslerini verir.',
    'toggle_mode': 'Düğmenin basılı durumunu tıklamalar arasında korur.',
    'button_pressed': 'Düğmenin basılı durumunu bildirir.',
    'current_tab': 'Etkin sekmenin indeksidir.',
    'context_menu_enabled': 'Sağ tık menüsünü açar veya kapatır.',
    'max_polyphony': 'Oynatıcının aynı anda çalabileceği ses sayısı üst sınırıdır.',
    'volume_db': 'Desibel cinsinden ses düzeyidir.',
    'stream_paused': 'Ses akışının duraklatma durumudur.',
    'attenuation': 'Konumsal sesin mesafeyle azalmasını belirler.',
    'list_slots': 'Kayıtlı oyun yuvalarının adlarını verir.',
})


def signature(value):
    try:
        return str(inspect.signature(value))
    except (TypeError, ValueError):
        doc = inspect.getdoc(value) or ''
        first = doc.splitlines()[0] if doc else ''
        return first[first.index('('):].split(' -> ')[0] if '(' in first and ')' in first else '(…)'


def clean(value):
    return str(value).replace('`', "'").replace('|', r'\|').replace('\n', ' ')


def first_doc(value):
    doc = inspect.getdoc(value) or ''
    line = doc.splitlines()[0] if doc else ''
    if not line or line.startswith(('Initialize self.', 'Return self.', 'Mapping', 'Helper for')) or '(' in line:
        return ''
    return line


def detail(name, value, kind):
    if name in MEMBER_SUMMARIES:
        return MEMBER_SUMMARIES[name]
    doc = first_doc(value.fget if isinstance(value, property) else value)
    if doc:
        return doc
    if kind == 'Sinyal':
        return f'`{name}` olayı gerçekleştiğinde gönderilir.'
    head, _, rest = name.partition('_')
    if kind == 'Metot' and head in PREFIXES:
        return f'{PREFIXES[head]}: `{rest or name}`.'
    return f'`{name}` {"ayarı" if kind == "Özellik" else "işlemi"}.'


def stored_attributes(cls):
    if not cls.__module__.startswith('doku2d.'):
        return set()
    source = ast.parse(dedent(inspect.getsource(cls)))
    result = set()
    for node in ast.walk(source):
        if (isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store)
                and isinstance(node.value, ast.Name) and node.value.id == 'self'
                and not node.attr.startswith('_')):
            result.add(node.attr)
    return result


def reference():
    import doku2d
    from doku2d.cli import build_atlas, build_project, create_project, run_project
    from doku2d.core.console import DebugConsole
    from doku2d.core.debug import DebugOverlay
    from doku2d.gui.effects import CharacterEffect
    from doku2d.gui.runtime import UI
    from doku2d.physics.physical import PhysicsBody
    from doku2d.rendering.tiledparser import LayerData, TileSetData

    exports = defaultdict(list)
    for name in doku2d.__all__:
        value = getattr(doku2d, name)
        if inspect.isclass(value):
            exports[value].append(name)
    for value in (DebugOverlay, DebugConsole, CharacterEffect, UI, PhysicsBody, LayerData, TileSetData):
        if value not in exports:
            exports[value].append(value.__name__)

    internal = {}
    for source in sorted((ROOT/'doku2d').rglob('*.py')):
        if 'template' in source.relative_to(ROOT).parts or source.name == '__main__.py':
            continue
        classes = [node.name for node in ast.parse(source.read_text(encoding='utf-8-sig')).body
                   if isinstance(node, ast.ClassDef)]
        if not classes:
            continue
        parts = source.relative_to(ROOT).with_suffix('').parts
        module = import_module('.'.join(parts[:-1] if parts[-1] == '__init__' else parts))
        for name in classes:
            value = getattr(module, name)
            if value not in exports:
                internal[value] = [name]

    def section(value):
        if value in internal:
            return 'internal'
        return value.__module__.split('.')[1] if value.__module__.startswith('doku2d.') else 'sfml'

    by_section = defaultdict(list)
    for value, names in (exports | internal).items():
        names.sort(key=lambda n: (n != value.__name__, n))
        by_section[section(value)].append((names, value))
    groups = {'core': 'Oyun, kaynaklar, girdi ve ayarlar', 'config': 'Proje ayarları',
              'rendering': 'Çizim, TileMap ve kamera', 'animation': 'Animasyon',
              'physics': 'Fizik ve NPC', 'audio': 'Ses', 'gui': 'Arayüz', 'dialogue': 'Diyalog',
              'sfml': 'SFML türleri',
              'internal': 'Motorun iç sınıfları'}
    rows = ['# Doku2D API başvurusu', '', '<!-- Generated by tools/generate_api_reference.py -->', '',
            f'{len(exports)} genel sınıf veya dönüş türü ve {len(internal)} iç sınıf listelenir.',
            'Alt sınıflar üst sınıfların üyelerini miras alır. Motorun iç sınıfları uygulama ayrıntısıdır.',
            'Kurucular ve alt çizgiyle başlamayan üyeler gösterilir.', '']
    for group, title in groups.items():
        if group not in by_section:
            continue
        rows += [f'## {title}', '']
        for names, cls in sorted(by_section[group], key=lambda item: (item[1].__module__, item[0][0])):
            name = names[0]
            source = inspect.getsourcefile(cls) if group != 'sfml' else None
            where = ''
            if source:
                line = inspect.getsourcelines(cls)[1]
                where = f' [Kaynak](../{Path(source).resolve().relative_to(ROOT).as_posix()}#L{line})'
            summary_key = 'Box shape' if name == 'Box' and group == 'physics' else cls.__name__
            desc = CLASS_SUMMARIES.get(summary_key) or first_doc(cls) or f'{name} motor türü.'
            heading = f'{name} ({"fizik" if group == "physics" else "yerleşim"})' if name == 'Box' else name
            rows += [f'### {heading}', '', desc + where, '', f'Kurucu: `{name}{clean(signature(cls))}`.', '']
            bases = [base.__name__ for base in cls.__bases__ if base is not object]
            if bases:
                rows += ['Üst tür: ' + ', '.join(f'`{base}`' for base in bases) + '.', '']
            if len(names) > 1:
                rows += ['Eş ad: ' + ', '.join(f'`{alias}`' for alias in names[1:]) + '.', '']
            members, constants = [], []
            definitions = dict(cls.__dict__)
            annotations = set(definitions.get('__annotations__', {})) | stored_attributes(cls)
            for base in cls.__mro__[1:]:
                if base.__module__.startswith('doku2d.') and base not in exports:
                    for member, value in base.__dict__.items():
                        definitions.setdefault(member, value)
                    annotations.update(base.__dict__.get('__annotations__', {}))
                    annotations.update(stored_attributes(base))
            for member in sorted(set(definitions) | annotations):
                if member.startswith('_'):
                    continue
                value = definitions.get(member)
                if isinstance(value, doku2d.Signal):
                    kind, display = 'Sinyal', member
                elif isinstance(value, property) or inspect.isgetsetdescriptor(value) or member in annotations:
                    kind, display = 'Özellik', member
                    if isinstance(value, property) and value.fset is None:
                        kind += ' (salt okunur)'
                elif callable(value) or isinstance(value, (classmethod, staticmethod)):
                    kind, display = 'Metot', member + signature(getattr(cls, member))
                elif value is not None:
                    constants.append(member)
                    continue
                else:
                    continue
                members.append((display, kind, detail(member, value, kind.split(' (')[0])))
            if members:
                rows += ['| Üye | Tür | Kısa bilgi |', '|---|---|---|']
                rows += [f'| `{clean(display)}` | {kind} | {clean(desc)} |' for display, kind, desc in members]
                rows.append('')
            if constants:
                rows += ['Sabitler ve öntanımlar: ' + ', '.join(f'`{value}`' for value in constants) + '.', '']
    rows += ['## Modül işlevleri', '']
    for func in (doku2d.tr, doku2d.analyze_dialogue, create_project, run_project, build_project, build_atlas):
        rows += [f'- `{func.__module__}.{func.__name__}{signature(func)}`. ' +
                 (first_doc(func) or {'create_project': 'Boş dizinde başlangıç projesi oluşturur.',
                                      'run_project': 'Projenin giriş dosyasını çalıştırır.'}.get(func.__name__, '')), '']
    return '\n'.join(rows).rstrip() + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    rendered = reference()
    if args.check:
        if not DESTINATION.is_file() or rendered != DESTINATION.read_text(encoding='utf-8'):
            raise SystemExit('API reference is stale. Run tools/generate_api_reference.py.')
    else:
        DESTINATION.write_text(rendered, encoding='utf-8')


if __name__ == '__main__':
    main()
