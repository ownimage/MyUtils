"""Application-specific button data and validated keyboard sequences."""
import copy
import json
import ntpath

BEHAVIOURS = {'normal': '.', 'hold': '-', 'repeat': '...'}

def app_key(path):
    return ntpath.normcase(ntpath.normpath(path)) if path else ''

def default_button(index):
    letter = chr(97 + index)
    return dict(name=letter, icon='', secondary_icon='', sequence=letter.upper(), behaviour='normal')

def normalise_sequence(text):
    """Uppercase single letter keys, preserving spacing and incomplete edits."""
    chords = []
    for chord in text.split(','):
        parts = chord.split('+')
        key = parts[-1].strip()
        if len(key) == 1 and key.isascii() and key.isalpha():
            parts[-1] = parts[-1].replace(key, key.upper())
        chords.append('+'.join(parts))
    return ','.join(chords)


def normalise_button(button):
    if not isinstance(button, dict):
        raise ValueError('Invalid button configuration.')
    second = button.get('secondary_icon', button.get('hover_icon', ''))
    if any(not isinstance(button.get(key), str) for key in ('name', 'icon', 'sequence')) or not isinstance(second, str):
        raise ValueError('Invalid button configuration.')
    behaviour = button.get('behaviour', 'normal')
    if not isinstance(behaviour, str) or behaviour not in BEHAVIOURS:
        raise ValueError('Behaviour must be Normal, Hold or Repeat.')
    sequence = normalise_sequence(button['sequence'])
    chords = parse_sequence(sequence)
    if behaviour == 'hold' and len(chords) > 1:
        raise ValueError('Hold requires one key or shortcut, not a sequence.')
    return dict(name=button['name'], icon=button['icon'], secondary_icon=second,
                sequence=sequence, behaviour=behaviour)

def character_key(character):
    """Resolve a printable character through the current Windows keyboard layout."""
    import ctypes
    if len(character) != 1 or not character.isprintable() or ord(character) > 0xffff:
        raise ValueError('Choose one printable character supported by the keyboard layout.')
    scan = ctypes.windll.user32.VkKeyScanW
    scan.argtypes = [ctypes.c_wchar]
    scan.restype = ctypes.c_short
    value = scan(character)
    if value == -1 or (value >> 8) & ~7:
        raise ValueError(f'Character {character!r} is unavailable on the current keyboard layout.')
    mods = [vk for bit, vk in ((1, 16), (2, 17), (4, 18)) if (value >> 8) & bit]
    return mods, value & 255


def parse_sequence(text):
    named = {'enter': 13, 'return': 13, 'tab': 9, 'space': 32, 'escape': 27,
             'esc': 27, 'backspace': 8, 'delete': 46, 'insert': 45, 'home': 36,
             'end': 35, 'pageup': 33, 'pagedown': 34, 'left': 37, 'up': 38,
             'right': 39, 'down': 40}
    modifiers = {'ctrl': 17, 'alt': 18, 'shift': 16, 'win': 91}
    result = []
    if not text.strip():
        return result
    for chord in text.split(','):
        raw_parts = [part.strip() for part in chord.split('+')]
        parts = [part.lower() for part in raw_parts]
        if not parts or not parts[-1]:
            raise ValueError('Use comma-separated keys, e.g. Ctrl+C, Ctrl+V. Use Plus for +.')
        mods = []
        modifier_only = all(token in modifiers for token in parts)
        for token in (parts if modifier_only else parts[:-1]):
            if token not in modifiers or modifiers[token] in mods:
                raise ValueError('Modifiers are Ctrl, Alt, Shift and Win; each appears once.')
            mods.append(modifiers[token])
        key = parts[-1]
        if modifier_only:
            vk = None
        elif len(key) == 1 and key.isascii() and key.isalnum():
            vk = ord(key.upper())
        elif len(raw_parts[-1]) == 1 or key in ('plus', 'comma'):
            character = {'plus': '+', 'comma': ','}.get(key, raw_parts[-1])
            required, vk = character_key(character)
            mods.extend(mod for mod in required if mod not in mods)
        elif key in named:
            vk = named[key]
        elif key.startswith('f') and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
            vk = 111 + int(key[1:])
        else:
            raise ValueError(f'Unsupported key: {key}. Use a printable character, F1–F24 or a named key.')
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
