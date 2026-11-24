"""Narrative and lighting metadata overlay; historical JSON remains immutable."""
from pathlib import Path
import json


def apply(events):
    text = json.loads(Path(__file__).with_name('civilian_text.json').read_text(encoding='utf-8'))
    for eid, patch in text.items():
        events[eid]['scene'] = patch['scene']
        for option in events[eid]['options']:
            if option['option_id']=='HUMANITY' and patch.get('protected_result'):
                option['result_text'] = patch['protected_result']
    for option in events['EV09']['options']:
        if option['option_id']=='HUMANITY': option['label']='留出载重，把水送到暮汀安置街'
    for option in events['EV19']['options']:
        for key in ('result_text','confirmation_text','opportunity_cost'):
            if key in option:option[key]=option[key].replace('药运往他乡','药被转卖给别的买主')
    # Metadata only: this greybox has no physical light renderer.
    staffed = {3,5,7,9,12,15,16,18,19,20,22,25,28,29,30,31,32,33,34,35,36,37,38,39,42,43,44,45,48,50,51,60}
    work = {18,19,20,22,25,30,33,36,39,42,45,48,51}
    for eid, event in events.items():
        number = int(eid[2:])
        hidden = number in (3,7)
        required = number in staffed and not hidden
        event['site_lighting'] = {
            'required': required, 'hidden_person_exception': hidden,
            'source': 'NONE_CONCEALED' if hidden else 'WORK_LAMP' if number in work else 'LOCAL_LANTERN' if required else 'PARTY_OR_EXISTING_SCENE',
            'scope': 'LOCAL_INTERACTION', 'erosion_immunity': False, 'rendered': False}
