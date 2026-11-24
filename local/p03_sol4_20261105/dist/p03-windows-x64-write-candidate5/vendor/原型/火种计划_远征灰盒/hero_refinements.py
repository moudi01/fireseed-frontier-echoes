"""Finite refinements to the existing H05/H06 kits, without new actions."""


def before_hit(b,a,v,action,amount,tick,log,spend_shields,*,surface=None):
    """H05 strips a real shield before this same basic hit spends its damage."""
    import combat as c
    import heroes
    import skill_books
    if (amount<=0 or action.get('move_id')!='BASIC' or action.get('derived')
            or not heroes.enabled(a,'H05') or not skill_books.capabilities(a)['near']):return
    # The caller supplies the final surface after any guard redirection. A
    # boss part spends its owner's shields but uses the part's contact cell.
    contact=surface if surface is not None else v
    if c.distance(a['pos'],contact['pos'])!=1:return
    removed=4-spend_shields(v,b['shared_shields'],4)
    if removed:
        log('hero_shield_strip',actor=a['id'],target=v['id'],action_id=action['id'],
            removed=removed,phase='before_main_hit')


def end_tick(actions,b,cat,board,tick,log):
    """Refund H06's first genuine moving-target miss, sharing interruption's cap."""
    import heroes
    ids={a['id']:a for a in b['actors']}
    for a,action in actions:
        if (action.get('move_id')!='H06-A' or not heroes.enabled(a,'H06')
                or a['hero_uses'].get('H06-P') or a['move_uses'].get('H06-A',0)<1):continue
        origin=action.get('tracked_target_origin');target=ids.get(action.get('target'))
        release_position=action.get('release_target_position')
        if not origin or release_position is None or not target or target['hp']<=0:continue
        # Later same-tick pushes must not create or erase the reason this
        # already-released spell missed. Survival is still checked at settlement.
        position=tuple(release_position);locked={tuple(p) for p in action['cells']}
        if position==tuple(origin) or position in locked:continue
        if any(e['type']=='hit' and e.get('actor')==a['id'] and e.get('action_id')==action['id']
               for e in b['events']):continue
        a['hero_uses']['H06-P']=1;a['move_uses']['H06-A']-=1
        log('hero_cast_refund',actor=a['id'],cast_id=action['id'],move='H06-A',
            ready=a['move_ready']['H06-A'],reason='TARGET_MOVED_OUT_OF_LOCKED_CELLS',
            tracked_target_origin=list(origin),release_target_position=list(release_position),
            target_position=target['pos'][:])
