# Sürüm notları

## 1.0.0rc2

- Diyalog dosyaları, koşullu ve süreli seçimler, oyuncu girişi, ortak alt
  konuşmalar, kayıt ve konuşma geçmişi. Yerelleştirme, portreler, ses,
  metin efektleri ve karaktere bağlı konuşma balonları.
- Diyalog önizlemesi, tıklanabilir dal haritası, otomatik yenileme ve
  dosya satırını gösteren akış, varlık ve çeviri uyarıları.
- Tree, arayüz genelinde sürükle-bırak, girdi bağlamları, tuş atama ve
  gamepad ipuçları. Otomatik ses kısma ve F3 üzerinden geliştirici konsolu.
- Arka planda varlık yükleme ve bölüm geçişleri. Canvas Y sıralaması,
  hareket interpolasyonu, yönlü animasyon ve animasyon işaretleri.
- Parçalı TileMap yükleme, parçalar arası NPC navigasyonu, şekil
  taramaları, zıplama yardım ayarları ve yeni örnek galeri ekranları.
- `Scripts/doku2d` başlatıcısı ve PNG klasörlerinden sprite atlası
  üreten `doku2d atlas` komutu.
- Shader desteği olmayan Windows grafik ortamlarında başlangıç oyunu
  açılıyor. Ortam rengi ve CanvasGroup saydamlığı temel çizimle çalışıyor.

## 1.0.0rc1

- Oyun döngüsü, `Entity`, katmanlı `Canvas`, bölüm kapsamları, sinyaller,
  girdi eşleme, kayıt/yükleme ve ayar API'leri.
- Tiled içe aktarma, katmanlı TileMap, animasyonlu autotile, grid üzerinden
  yol bulma ve `NavigationAgent` ile NPC yol takibi.
- Pymunk tabanlı fizik, karakter hareketi, tek yönlü platformlar, alanlar
  ve ışın sorguları.
- Sprite ve atlas animasyonu, sprite batching, görünürlük elemesi ve ekran
  giriş/çıkış bildirimleri. Gölge, parçacık, shader materyali, CanvasGroup
  ve gece-gündüz için ortam rengi.
- Boyutlandırılabilir UI, tema ve yerelleştirme, metin ve liste kontrolleri,
  kamera, konumsal ses ve geliştiricinin değiştirebildiği F3 paneli.
- `doku2d create`, `run` ve Nuitka tabanlı `build`. Şablon oyunda kayıt
  yüklenirken yeniden eklenen nesneler artık bölümleriyle birlikte temizleniyor.
- On adımlı eğitim, sınıf başvurusu ve temiz kurulumdan bağımsız uygulamaya
  kadar otomatik sürüm doğrulaması.

Belgelendirilmiş Windows ve Linux kapsamı, macOS durumu ve bağımlılıklar
[platform rehberinde](doc/build.md). 1.0 sonrası genel API kapsamı
[uyumluluk notlarında](doc/api.md).
