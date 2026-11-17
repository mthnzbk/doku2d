
class Resource:
    """Doku (Texture), Font ve diğer asset'leri önbelleğe alarak yönetir."""
    _textures = {}
    _fonts = {}

    """oyun paketlendiğinde kod zipten hafızaya yükleyerek kullanacak. Geliştirici uğraşmadan."""

    @classmethod
    def get_texture(cls, path: str): pass

    @classmethod
    def get_font(cls, path: str): pass

    @classmethod
    def clear(cls): pass
