from doku2d import Game, Scene, CharacterBody, Sprite


if __name__ == '__main__':
    game = Game()
    scene = Scene()
    character = CharacterBody()
    sprite = Sprite("character.png")
    character.add_child(sprite)
    scene.add_child(character)
    game.add_child(scene)
    game.run()
