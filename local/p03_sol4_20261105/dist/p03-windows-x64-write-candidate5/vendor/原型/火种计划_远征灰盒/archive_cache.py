"""Share immutable, validated settlement and learning records inside a session."""
from copy import deepcopy
import hashlib
import json


def _read_only(*args, **kwargs):
    raise TypeError('Committed archive records are immutable')


class _FrozenDict(dict):
    __setitem__ = __delitem__ = __ior__ = _read_only
    clear = pop = popitem = setdefault = update = _read_only

    def __deepcopy__(self, memo):
        copied = {}
        memo[id(self)] = copied
        for key, value in self.items():
            copied[deepcopy(key, memo)] = deepcopy(value, memo)
        return copied


class _FrozenList(list):
    __setitem__ = __delitem__ = __iadd__ = __imul__ = _read_only
    append = clear = extend = insert = pop = remove = reverse = sort = _read_only

    def __deepcopy__(self, memo):
        copied = []
        memo[id(self)] = copied
        copied.extend(deepcopy(child, memo) for child in self)
        return copied


def _freeze(value, memo):
    if type(value) not in (dict, list, tuple):
        return value
    identity = id(value)
    if identity in memo:
        return memo[identity]
    if type(value) is dict:
        result = _FrozenDict()
        memo[identity] = result
        for key, child in value.items():
            dict.__setitem__(result, key, _freeze(child, memo))
    elif type(value) is list:
        result = _FrozenList()
        memo[identity] = result
        list.extend(result, (_freeze(child, memo) for child in value))
    else:
        result = tuple(_freeze(child, memo) for child in value)
        memo[identity] = result
    return result


def _json(value, depth, sort_keys, pretty):
    options = {'ensure_ascii': False, 'allow_nan': False, 'sort_keys': sort_keys}
    if pretty:
        raw = json.dumps(value, indent=2, **options).encode('utf-8')
        return raw.replace(b'\n', b'\n' + b'  ' * depth) if depth else raw
    return json.dumps(value, separators=(',', ':'), **options).encode('utf-8')


class ArchivedRecord(_FrozenDict):
    __slots__ = ('_encodings', '_decoded_json')

    def __init__(self, value, *, decoded_json=False):
        if type(value) is not dict:
            raise TypeError('Expected a validated archive object')
        frozen = _freeze(value, {})
        dict.__init__(self, frozen)
        self._encodings = {}
        self._decoded_json = decoded_json

    def encoded(self, depth, sort_keys, pretty):
        key = (depth if pretty else 0, sort_keys, pretty)
        reading = self._encodings.get(key)
        if reading is None:
            reading = _json(self, depth, sort_keys, pretty)
            self._encodings[key] = reading
        return reading


def seal_validated(state, *, decoded_json=False):
    """Seal only the two collections whose producers detach finished records."""
    for archive in (state['completed_history'], state['learning']['battles']):
        for index, record in enumerate(archive):
            if type(record) is not ArchivedRecord:
                archive[index] = ArchivedRecord(record, decoded_json=decoded_json)


def seal_loaded_journal(state):
    """The JSON reader creates detached history. New rows may still alias live state."""
    for index, record in enumerate(state['journal']):
        state['journal'][index] = ArchivedRecord(record, decoded_json=True)


def warm_archives(state, *, for_checkpoint=False):
    """Prepare committed archive bytes before the first interactive command."""
    for archive, depth in ((state['completed_history'], 2), (state['learning']['battles'], 3)):
        for record in archive:
            record.encoded(depth, False, False)
            if for_checkpoint:
                record.encoded(depth, True, False)
                record.encoded(depth, False, True)
    for record in state['journal']:
        if type(record) is ArchivedRecord:
            record.encoded(2, False, False)
            if for_checkpoint:
                record.encoded(2, True, False)
                record.encoded(2, False, True)


def _structured(value, path):
    if path in (('completed_history',), ('learning', 'battles'), ('journal',)):
        return isinstance(value, list) and any(type(record) is ArchivedRecord for record in value)
    if path == ('learning',):
        return isinstance(value, dict) and _structured(value.get('battles', []), ('learning', 'battles'))
    if not path and isinstance(value, dict):
        return (_structured(value.get('completed_history', []), ('completed_history',))
                or _structured(value.get('learning', {}), ('learning',))
                or _structured(value.get('journal', []), ('journal',))
                or (value.get('format') == 'TINDER-FINALE-RETRY-1'
                    and _structured(value.get('state'), ())))
    return False


def fragments(value, sort_keys=False, pretty=False, path=(), depth=0):
    if type(value) is ArchivedRecord:
        yield value.encoded(depth, sort_keys, pretty)
        return
    if not _structured(value, path):
        yield _json(value, depth, sort_keys, pretty)
        return

    mapping = isinstance(value, dict)
    yield b'{' if mapping else b'['
    pad = b'\n' + b'  ' * (depth + 1) if pretty else b''
    entries = (sorted(value.items()) if sort_keys else value.items()) if mapping else enumerate(value)
    for index, (key, child) in enumerate(entries):
        if index:
            yield b','
        yield pad
        if mapping:
            yield _json(key, 0, False, False)
            yield b': ' if pretty else b':'
        child_path = (*path, key)
        if not path and key == 'state' and value.get('format') == 'TINDER-FINALE-RETRY-1':
            child_path = ()
        yield from fragments(child, sort_keys, pretty, child_path, depth + 1)
    if pretty:
        yield b'\n' + b'  ' * depth
    yield b'}' if mapping else b']'


def checkpoint_copy(value, path=()):
    """Copy exactly the state the sidecar reader would decode."""
    if type(value) is ArchivedRecord:
        if value._decoded_json:
            return value
        decoded = json.loads(value.encoded(0, False, False))
        return ArchivedRecord(decoded, decoded_json=True)
    if not _structured(value, path):
        return json.loads(_json(value, 0, False, False))
    if isinstance(value, dict):
        return {key: checkpoint_copy(child, (*path, key)) for key, child in value.items()}
    return [checkpoint_copy(child, path) for child in value]


def encode(state):
    return b''.join(fragments(state))


def digest(state, *, sort_keys=False, pretty=False):
    result = hashlib.sha256()
    for part in fragments(state, sort_keys, pretty):
        result.update(part)
    return result.hexdigest()
