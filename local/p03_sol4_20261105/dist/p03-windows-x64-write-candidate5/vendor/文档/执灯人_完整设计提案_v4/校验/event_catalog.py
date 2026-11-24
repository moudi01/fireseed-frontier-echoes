"""Compose documentation catalogs for ordinary MULTI runs; not a runtime loader."""
from pathlib import Path
import hashlib
import json

H = Path(__file__).resolve().parent


def load_catalog():
    raw = (H / '远征事件池.json').read_bytes()
    base = json.loads(raw)
    config = json.loads((H / '多区域远征配置.json').read_text(encoding='utf-8'))
    events = list(base['events'])
    seen = {e['event_id'] for e in events}
    if len(seen) != len(events):
        raise ValueError('duplicate baseline event ID')
    bundles = []
    for name in config['events'].get('extension_files', []):
        if Path(name).name != name:
            raise ValueError('extension must be an explicit sibling file')
        ext = json.loads((H / name).read_text(encoding='utf-8'))
        if ext['base_event_sha256'] != hashlib.sha256(raw).hexdigest():
            raise ValueError('extension baseline hash mismatch')
        for event in ext['events']:
            if event['event_id'] in seen:
                raise ValueError('duplicate event ID: ' + event['event_id'])
            seen.add(event['event_id'])
            events.append(event)
        bundles.extend(ext['reward_bundles'])
    original_bundles = json.loads((H / '战利品.json').read_text(encoding='utf-8'))['reward_bundles']
    ids = [b['bundle_id'] for b in original_bundles + bundles]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate reward bundle ID')
    if any(o.get('reward_bundle_id') and o['reward_bundle_id'] not in ids for e in events for o in e['options']):
        raise ValueError('unknown event reward bundle')
    return events, original_bundles + bundles
