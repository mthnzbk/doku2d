"""Local developer commands registered by the game."""
import shlex


class DebugConsole:
    def __init__(self, debugger):
        self.debugger = debugger
        self.game = debugger._game
        self._commands = {}
        self._controls = None
        self.register('help', lambda: '  '.join(sorted(self._commands)))

    @property
    def opened(self):
        return self._controls is not None

    def register(self, name, callback):
        if not isinstance(name, str) or not name or any(character.isspace() for character in name) or not callable(callback):
            raise ValueError('Console commands need a single name and a callable')
        self._commands[name] = callback
        return callback

    def execute(self, text):
        if not self.debugger.enabled:
            raise RuntimeError('The developer console requires debugging to be enabled')
        args = shlex.split(text)
        if not args:
            return None
        if args[0] not in self._commands:
            raise ValueError(f'Unknown command: {args[0]}')
        return self._commands[args[0]](*args[1:])

    def toggle(self):
        if self.opened:
            self.close()
        elif self.debugger.visible:
            self.open()

    def open(self):
        if self.opened or not self.debugger.visible:
            return
        from ..gui import ItemList, LineEdit

        width, height = self.game.size
        log, entry = ItemList(), LineEdit()
        log.position, log.size = (16, max(0,height-226)), (max(1,width-32), 169)
        entry.position, entry.size = (16, max(0,height-53)), (max(1,width-32), 36)
        entry.placeholder = 'Komut yaz ve Enter’a bas · F4 kapatır'
        entry.text_submitted.connect(self._submit)
        log.add_item('Doku2D · Komut listesi için help')
        log.row_height = 26
        for control in (log, entry):
            control.z_index = 100000
            control.process_mode = 'always'
            self.game.add(control, persistent=True)
        self._controls = log, entry
        self.game.call_deferred(self._focus, entry)

    def _focus(self, entry):
        if self.opened and self._controls[1] is entry and entry.game is self.game:
            entry.grab_focus()

    def _submit(self, text):
        log, entry = self._controls
        entry.text = ''
        try:
            result = self.execute(text)
            note = '' if result is None else f' → {result}'
        except Exception as error:
            note = f' → {error}'
        if self.opened and self._controls[0] is log:
            if len(log.items) >= 100:
                log.items = log.items[-99:]
            log.select(log.add_item(f'> {text}{note}'))

    def close(self):
        if self.opened:
            controls, self._controls = self._controls, None
            if not self.game.closed:
                for control in controls:
                    self.game.remove(control)
