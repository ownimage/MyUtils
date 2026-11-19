"""Application-specific button data and validated keyboard sequences."""
import copy
import json
import ntpath

def app_key(path):
    return ntpath.normcase(ntpath.normpath(path)) if path else ''

def default_button(index):
    letter = chr(97 + index)
    return dict(name=letter, icon='', secondary_icon='', sequence=letter)

def normalise_button(button):
    if not isinstance(button, dict):
        raise ValueError('Invalid button configuration.')
    second = button.get('secondary_icon', button.get('hover_icon', ''))
    if any(not isinstance(button.get(key), str) for key in ('name', 'icon', 'sequence')) or not isinstance(second, str):
        raise ValueError('Invalid button configuration.')
    return dict(name=button['name'], icon=button['icon'], secondary_icon=second, sequence=button['sequence'])

def parse_sequence(text):
    named = {'enter': 13, 'return': 13, 'tab': 9, 'space': 32, 'escape': 27,
             'esc': 27, 'backspace': 8, 'delete': 46, 'insert': 45, 'home': 36,
             'end': 35, 'pageup': 33, 'pagedown': 34, 'left': 37, 'up': 38,
             'right': 39, 'down': 40, 'plus': 187, 'comma': 188}
    modifiers = {'ctrl': 17, 'alt': 18, 'shift': 16, 'win': 91}
    result = []
    if not text.strip():
        return result
    for chord in text.split(','):
        parts = [part.strip().lower() for part in chord.split('+')]
        if not parts or not parts[-1]:
            raise ValueError('Use comma-separated keys, e.g. Ctrl+C, Ctrl+V. Use Plus for +.')
        mods = []
        for token in parts[:-1]:
            if token not in modifiers or modifiers[token] in mods:
                raise ValueError('Modifiers are Ctrl, Alt, Shift and Win; each appears once.')
            mods.append(modifiers[token])
        key = parts[-1]
        if len(key) == 1 and key.isascii() and key.isalnum():
            vk = ord(key.upper())
        elif key in named:
            vk = named[key]
        elif key.startswith('f') and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
            vk = 111 + int(key[1:])
        else:
            raise ValueError(f'Unsupported key: {key}. Use letters, digits, F1–F24 or named keys.')
        result.append((mods, vk))
    if len(result) > 32:
        raise ValueError('A sequence can contain at most 32 keys or shortcuts.')
    return result

class ButtonProfiles:
    def __init__(self, settings):
        self.settings = settings

    def read(self):
        self.settings.sync()
        raw = json.loads(self.settings.value('radial/profiles', '{}', type=str))
        if not isinstance(raw, dict):
            raise ValueError('Invalid application button profiles.')
        return raw

    def applications(self):
        return sorted(self.read())

    def buttons(self, application):
        raw = self.read().get(app_key(application), {})
        if not isinstance(raw, dict):
            raise ValueError('Invalid application button profile.')
        buttons = []
        for index in range(26):
            button = raw.get(str(index), default_button(index))
            button = normalise_button(button)
            parse_sequence(button['sequence'])
            buttons.append(copy.deepcopy(button))
        return buttons

    def save(self, application, buttons):
        if not application:
            raise ValueError('Choose an application first.')
        buttons = [normalise_button(button) for button in buttons]
        for button in buttons:
            parse_sequence(button['sequence'])
        profiles = self.read()
        profiles[app_key(application)] = {str(i): copy.deepcopy(button) for i, button in enumerate(buttons)}
        self.settings.setValue('radial/profiles', json.dumps(profiles))
        self.settings.sync()
        if self.settings.status() != self.settings.Status.NoError:
            raise OSError('Could not save application button settings.')
