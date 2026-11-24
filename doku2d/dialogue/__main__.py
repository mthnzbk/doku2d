import argparse

from .preview import make_preview


def main(argv=None):
    parser = argparse.ArgumentParser(description='Önizlemek istediğin Doku2D diyalog dosyasını aç.')
    parser.add_argument('path', nargs='?', help='.dialogue dosyasının yolu')
    parser.add_argument('--assets', help='res:// yolları için varlık dizini')
    parser.add_argument('--locale', default='en', help='Başlangıç dili')
    parser.add_argument('--fallback', default='en', help='Yedek dil')
    parser.add_argument('--catalog', action='append', default=[], metavar='DİL=DOSYA', help='Çeviri kataloğu')
    args = parser.parse_args(argv)
    catalogs = {}
    for mapping in args.catalog:
        locale, _, path = mapping.partition('=')
        if not locale.strip() or not path.strip():
            parser.error('--catalog için DİL=DOSYA biçimini kullan')
        catalogs[locale] = path
    game, _ = make_preview(args.path, asset_root=args.assets, locale=args.locale,
                           fallback_locale=args.fallback, catalogs=catalogs)
    game.run()


if __name__ == '__main__':
    main()
