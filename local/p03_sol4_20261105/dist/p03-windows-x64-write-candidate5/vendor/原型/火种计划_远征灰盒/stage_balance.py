"""Public early/middle ordinary contracts, independent of the visiting roster.

The route's authored chapter selects the contract. Later permissions do not
raise an old route again. The existing departure freeze and single application
of progression_pressure own enemy numbers; this module never edits actors,
skills, rewards, player panels, gear or frozen content files.
"""
from copy import deepcopy

VERSION = 'STAGE-CONTRACT-0.68'
CONTRACTS = {
    1: dict(contract_stage='EARLY', stage_name='前期委任', stage_floor=1,
            hp_percent=100, attack_percent=120),
    2: dict(contract_stage='MIDDLE', stage_name='中期委任', stage_floor=3,
            hp_percent=100, attack_percent=120),
}


def early_middle_policy(route, facts=None):
    """Return the frozen-pressure schema for chapter1/2, otherwise None.

    ``facts`` is accepted for the shared public-policy signature; it does not
    feed difficulty. A chapter2 party revisiting chapter1 gets chapter1 foes.
    Only ordinary journeys call the surrounding route policy.
    """
    row = CONTRACTS.get(route['chapter'])
    if row is None:
        return None
    return dict(version=VERSION, route_id=route['route_id'], chapter=route['chapter'],
                **deepcopy(row), milestone=None, policy_source='authored_route_chapter',
                scale_by_party=False, frozen_at='departure')


def install(catalog):
    catalog.rules['stage_balance'] = dict(version=VERSION,
        contracts=deepcopy(CONTRACTS), source='authored_route_chapter',
        player_costs_unchanged=True, scale_by_party=False,
        hp_and_defense_extra_scaling=False)

