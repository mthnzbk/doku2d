"""Inspect and play a dialogue file outside its game."""
from dataclasses import replace
import json
from pathlib import Path

from sfml.window import Event, Keyboard

from ..core import Entity, Game, tr
from ..gui import Button, ItemList, Label, LineEdit, OptionButton, Tree
from .box import DialogueBox
from .analysis import analyze_dialogue
from .graph import DialogueGraph
from .tree import DialogueTree
from .widgets import DialogueHistory


class _FlagList(ItemList):
    def _key(self, event):
        if event.type == Event.KEY_PRESSED and event.code in (Keyboard.RETURN, Keyboard.SPACE):
            if self.selected_indices:
                self.item_clicked.emit(self.selected_indices[0], None, 0)
            return True
        return super()._key(event)


class DialoguePreview(Entity):
    def __init__(self, path=None, *, values=None):
        super().__init__()
        self.path = path
        self.tree = None
        self.state = {}
        self.flags = ()
        self.missing = ()
        self.missing_translations = ()
        self.checkpoint = None
        self._playable = None
        self._initial_values = dict(values or {})
        self._history = []
        self._warnings = ()
        self._warning_rows = {}
        self._watch_path = self._watch_stamp = None
        self._watch_elapsed = 0.0

    def on_ready(self):
        def place(control, x, y, width, height):
            control.position, control.size = (x, y), (width, height)
            return self.game.add(control)

        place(Label(text='Diyalog önizleme'), 24, 10, 580, 32).font_size = 24
        place(Label(text='Dil'), 643, 10, 35, 32)
        self.language = place(OptionButton(), 682, 10, 143, 32)
        localization = self.game.localization
        self.languages = tuple(sorted(set(localization.locales) | {self.game.locale}))
        for language in self.languages:
            self.language.add_item(language)
        self.language.selected = self.languages.index(self.game.locale)
        self.language.item_selected.connect(self.select_language)
        self.path_entry = place(LineEdit(), 24, 56, 819, 36)
        self.path_entry.placeholder = '.dialogue dosyasının yolu'
        self.path_entry.text_submitted.connect(self.open_file)
        place(Button(text='Dosyayı aç'), 855, 56, 121, 36).pressed.connect(self.open_file)

        for title, x, width in (('Bölümler', 24, 245), ('Koşullar', 285, 220),
                                ('Dosya uyarıları ve olaylar', 521, 455)):
            place(Label(text=title), x, 110, width, 24)
        self.sections = place(Tree(), 24, 139, 245, 156)
        self.sections.item_activated.connect(lambda item: self.play(item.data))
        self.flag_list = place(_FlagList(), 285, 139, 220, 156)
        self.flag_list.item_clicked.connect(self._click_flag)
        self.messages = place(ItemList(), 521, 139, 455, 156)
        self.messages.row_height = 26
        self.messages.font_size = 14
        self.messages.item_clicked.connect(self._open_warning)
        self.graph = place(DialogueGraph(), 24, 104, 952, 191)
        self.graph.visible = False
        self.graph.z_index = 20
        self.graph.section_selected.connect(self.play)
        place(Button(text='Bölümü oynat'), 24, 307, 245, 36).pressed.connect(self.play)
        self.save_button = place(Button(text='Konumu kaydet'), 285, 307, 168, 36)
        self.save_button.pressed.connect(self.save_checkpoint)
        self.save_button.disabled = True
        self.resume_button = place(Button(text='Kayıttan sürdür'), 465, 307, 168, 36)
        self.resume_button.pressed.connect(self.resume_checkpoint)
        self.resume_button.disabled = True
        place(Button(text='Denetle'), 648, 307, 99, 36).pressed.connect(self.inspect_flow)
        place(Button(text='Harita'), 758, 307, 99, 36).pressed.connect(self.toggle_graph)
        place(Button(text='Geçmiş'), 868, 307, 108, 36).pressed.connect(self.toggle_history)
        self.values_entry = place(LineEdit(), 24, 352, 795, 34)
        self.values_entry.placeholder = 'Metin değerleri (JSON)'
        self.values_entry.text_submitted.connect(self.apply_values)
        place(Button(text='Değerleri uygula'), 831, 352, 145, 34).pressed.connect(self.apply_values)
        self.status = place(Label(text='Önizlemek için bir diyalog dosyası aç.'), 24, 393, 952, 24)
        self.box = self.game.add(DialogueBox(width=952, height=235))
        self.box.continue_text = tr('preview.continue', default='Devam et')
        self.box.subdialogue_loader = self._load_subdialogue
        self.box.failed.connect(lambda error: self._message(str(error)))
        self.conversation_log = place(DialogueHistory(self.box), 24, 104, 952, 191)
        self.conversation_log.z_index = 21
        self.box.event_triggered.connect(lambda name: self._message(f'Olay  {name}'))
        self.box.line_changed.connect(self._line_changed)
        self.box.finished.connect(self._finished)
        if self.path is not None:
            self.path_entry.text = str(self.path)
            self.game.call_deferred(self.open_file)

    def _message(self, message):
        self._history.append(message)
        index = self.messages.add_item(message)
        self.messages.select(index)

    def select_language(self, index):
        self.game.locale = self.languages[index]
        self._refresh_alerts()
        self.box.focus_response()

    def _refresh_alerts(self):
        if self.tree is None:
            return
        localization = self.game.localization
        self.missing_translations = tuple(ref for ref in self.tree.translation_references
                                          if not localization.has_translation(ref.key))
        self.messages.items = []
        self._warning_rows.clear()
        for warning in self._warnings:
            index = self.messages.add_item(f'{Path(warning.source).name}:{warning.line}  {warning.message}')
            self._warning_rows[index] = warning
        for ref in self.missing:
            self.messages.add_item(f'{Path(ref.source).name}:{ref.line}   {ref.path}')
        for ref in self.missing_translations:
            self.messages.add_item(f'{Path(ref.source).name}:{ref.line} [{self.game.locale}]  {ref.key}')
        for message in self._history:
            self.messages.add_item(message)

    def _show_values(self):
        values = {key: value for key, value in self.state.items() if key not in self.flags}
        self.values_entry.text = json.dumps(values, ensure_ascii=False)

    def inspect_flow(self):
        if self.tree is not None:
            entry = self.sections.selected.data if self.sections.selected else self.tree.start
            self._warnings = analyze_dialogue(self.tree, entry=entry)
            self.graph.set_tree(self.tree, entry)
            self._refresh_alerts()
            self.status.text = f'{entry} başlangıcı · {len(self._warnings)} akış uyarısı'

    def _open_warning(self, index, point, button):
        warning = self._warning_rows.get(index)
        if button == 0 and warning is not None:
            if warning.state is not None:
                self.state.update(warning.state)
                for flag_index, flag in enumerate(self.flags):
                    self.flag_list.items[flag_index].text = self._flag_text(flag)
                self._show_values()
            self.play(warning.section)

    def toggle_graph(self):
        if self.tree is not None:
            self.conversation_log.close()
            self.graph.visible = not self.graph.visible
            if self.graph.visible:
                entry = self.sections.selected.data if self.sections.selected else self.tree.start
                self.graph.set_tree(self.tree, entry)

    def toggle_history(self):
        self.graph.visible = False
        if self.conversation_log.visible:
            self.conversation_log.close()
        else:
            self.conversation_log.open()

    def apply_values(self, text=None):
        if self.tree is None:
            return False
        try:
            values = json.loads(self.values_entry.text if text is None else text)
            if not isinstance(values, dict) or any(key in self.flags for key in values):
                raise ValueError
        except ValueError:
            self._message('Değerler bir JSON nesnesi olmalı. Koşulları listeden değiştir.')
            return False

        for key in tuple(self.state):
            if key not in self.flags:
                del self.state[key]
        self.state.update(values)
        self._show_values()
        self.box.focus_response()
        return True

    @staticmethod
    def _stamp(path):
        try:
            stat = path.stat()
            return stat.st_mtime_ns, stat.st_size
        except OSError:
            return None

    def update(self, dt):
        if self._watch_path is not None:
            self._watch_elapsed += dt
            if self._watch_elapsed >= .35:
                self._watch_elapsed = 0
                stamp = self._stamp(self._watch_path)
                if stamp != self._watch_stamp:
                    self._watch_stamp = stamp
                    self.open_file(self._watch_path, preserve=True)

    def open_file(self, path=None, *, preserve=False):
        path = str(self.path_entry.text if path is None else path).strip().strip('"')
        if not path:
            self.status.text = 'Diyalog dosyasının yolunu gir.'
            return False

        resources = self.game.resources
        try:
            resolved = resources.resolve(path)
            tree = DialogueTree.load(resolved, resources=resources)
            missing = tuple(ref for ref in tree.asset_references
                            if not resources.resolve(tree.asset_path(ref.path)).is_file())
        except (ValueError, OSError, RuntimeError) as error:
            self._message(str(error))
            self.status.text = 'Dosya açılamadı. Ayrıntı uyarılar listesinde.'
            return False

        selected = self.sections.selected.data if preserve and self.sections.selected else tree.start
        active = self.box.snapshot() if preserve else None
        state = self.state if preserve else {}
        self.box.close()
        self._watch_path, self._watch_stamp = resolved, self._stamp(resolved)
        self.tree, self.missing = tree, missing
        self._playable = self._without_missing_assets(tree, {ref.path for ref in missing})
        if not preserve:
            self.checkpoint = None
            self.resume_button.disabled = True
            self._history.clear()
        self.path_entry.text = str(resolved)
        self.flags = tuple(sorted({choice.condition[0] for section in tree.sections.values()
                                   for choice in (*section.choices, *section.branches)
                                   if choice.condition and len(choice.condition) == 2}))
        self.state = {**self._initial_values, **dict.fromkeys(self.flags, False), **state}
        self._show_values()
        self.sections.clear()
        selected = selected if selected in tree.sections else tree.start
        for name in tree.sections:
            item = self.sections.add_item(name, data=name)
            if name == selected:
                self.sections.select(item)
        self.flag_list.items = []
        for flag in self.flags:
            self.flag_list.add_item(self._flag_text(flag))
        self._warnings = analyze_dialogue(tree, entry=selected)
        self.graph.set_tree(tree, selected)
        self._refresh_alerts()
        self.status.text = f'{len(tree.sections)} bölüm, {len(self.flags)} koşul, {len(missing)} eksik dosya'
        if active is not None:
            try:
                self.box.restore(self._playable, active, state=self.state)
                self._line_changed(self.box.line)
            except (ValueError, OSError, RuntimeError):
                self.play(active['section'] if active['section'] in tree.sections else selected)
        return True

    @staticmethod
    def _without_missing_assets(tree, missing):
        if not missing:
            return tree
        sections = {name: replace(section, lines=tuple(replace(line, voice=None) if line.voice in missing else line
                                                       for line in section.lines))
                    for name, section in tree.sections.items()}
        portraits = {speaker: asset for speaker, asset in tree.portraits.items() if asset[1] not in missing}
        expressions = {key: asset for key, asset in tree.expressions.items() if asset[1] not in missing}
        return DialogueTree(sections, portraits, start=tree.start, directory=tree.directory, expressions=expressions,
                            asset_references=tree.asset_references, translation_references=tree.translation_references,
                            source=tree.source)

    def _load_subdialogue(self, path):
        resources = self.game.resources
        tree = DialogueTree.load(path, resources=resources)
        missing = tuple(ref for ref in tree.asset_references
                        if not resources.resolve(tree.asset_path(ref.path)).is_file())
        for ref in missing:
            self._message(f'{Path(ref.source).name}:{ref.line}   {ref.path}')
        return self._without_missing_assets(tree, {ref.path for ref in missing})

    def _flag_text(self, flag):
        return f'{"Açık" if self.state[flag] else "Kapalı"}   {flag}'

    def _click_flag(self, index, point, button):
        if button == 0:
            self._toggle_flag(index)

    def _toggle_flag(self, index):
        flag = self.flags[index]
        self.state[flag] = not self.state[flag]
        self.flag_list.items[index].text = self._flag_text(flag)

    def play(self, section=None):
        if self._playable is None:
            return
        if section is None:
            section = self.sections.selected.data if self.sections.selected else self.tree.start
        if self.conversation_log.visible:
            self.conversation_log.close()
        self.box.start(self._playable, section=section, state=self.state)

    def save_checkpoint(self):
        if self.box.active:
            self.checkpoint = self.box.snapshot(), self.state.copy()
            self.resume_button.disabled = False
            self._message('Kayıt  Konum ve koşullar saklandı.')

    def resume_checkpoint(self):
        if self.checkpoint is not None:
            checkpoint, state = self.checkpoint
            self.state.clear()
            self.state.update(state)
            self._show_values()
            for index, flag in enumerate(self.flags):
                self.flag_list.items[index].text = self._flag_text(flag)
            try:
                self.box.restore(self._playable, checkpoint, state=self.state)
                self._line_changed(self.box.line)
            except (ValueError, OSError, RuntimeError) as error:
                self._message(str(error))

    def _line_changed(self, line):
        self.save_button.disabled = False
        expression = f'   İfade: {line.expression}' if line.expression else ''
        pause = f'   Bekleme: {line.pause:g} sn' if line.pause else ''
        self.status.text = f'{line.speaker or "Anlatıcı"}{expression}{pause}'

    def _finished(self):
        self.save_button.disabled = True
        self.status.text = 'Diyalog tamamlandı.'


def make_preview(path=None, *, asset_root=None, locale='en', fallback_locale='en', catalogs=None, values=None):
    game = Game(title='Doku2D | Diyalog Önizleme', size=(1000, 680), asset_root=asset_root,
                locale=locale, fallback_locale=fallback_locale, catalogs=catalogs)
    preview = game.add(DialoguePreview(path, values=values))
    game.flush_deferred()
    return game, preview
