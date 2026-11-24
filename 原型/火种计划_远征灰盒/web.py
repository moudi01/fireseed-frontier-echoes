"""Loopback-only, token-protected, single-writer HTTP adapter. No dependencies."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from copy import deepcopy
import json
import os
import secrets
import webbrowser
from engine import BASE, Game, atomic_json


def view(game,message=''):
    from app import HELP
    import region_space
    import narrative
    import depth_growth
    import rescue
    import escort
    import event_memory
    import refugee
    import water
    import medicine
    import cases
    import expedition_tiers
    import finale
    import plan_offers
    import event_conditions
    import rogue_events
    import enemy_intel
    import hidden_thread
    import boss_mimic,boss_threats
    import expedition_peril
    import book_catalog,book_rewards,skill_books
    import battle_enrage
    s=game.s
    party=deepcopy(s['party'])
    live={a['id']:a for a in s['battle']['actors']} if s['battle'] else {}
    for m in party:
        if m['instance_id'] in live:m['hp']=live[m['instance_id']]['hp']
    payload={'text':game.describe(),'message':message,'phase':s['phase'],'party':party,
             'books':{'catalog':[dict(id=bid,name=spec['name'],category=spec['category'],
                         stage=spec['stage'],price=spec['price'],summary=spec.get('summary',''),
                         auto_summary=spec.get('auto_summary',''),unlocked=book_rewards.unlocked(game,bid),
                         card=deepcopy(spec['card'])) for bid,spec in book_catalog.BOOKS.items()],
                      'stock':deepcopy(s['book_stock']),'rewards':book_rewards.public(game),
                      'members':[dict(id=m['instance_id'],learned=m.get('books_learned',[]),
                          equipped=m.get('books_equipped',[]),main=m.get('main_attack','AUTO'),
                          active=skill_books.active_ids(m),disabled=m.get('disabled_skills',[]),
                          skill_names={row['move_id']:row.get('name',row['move_id'])
                              for row in skill_books.cards(m,skill_books._core(m))},
                          reasons={bid:skill_books.reason(m,bid) for bid in book_catalog.BOOKS})
                          for m in s['party']+s['home_roster']]},
             'depth_growth': depth_growth.public(game),
             'expedition_tier':expedition_tiers.public(game),
             'journey_conditions':event_conditions.public(game),
             'fortune':rogue_events.public(game),
             'expedition_peril':expedition_peril.public_game(game),
             'battle_enrage':battle_enrage.public(s['battle']),
             'enemy_intel':enemy_intel.public(game),
             'boss_mechanics':{'mimic':boss_mimic.describe(s['battle']) if s['battle'] else '',
                               'threats':boss_threats.public(s['battle'])},
             'pouch':s['pouch'],'home_roster':s['home_roster'],'recipes':list(game.cat.recipes.values()),
             'rescue_batches':rescue.batches(s),'due_next':rescue.due_next(s),'next_day':s['day']+1,
             'capture_mode':s['capture_mode'],'ending':s['ending'],'summary':s['summary'],
             'ending_text':finale.ending_text(game),
             'can_flee':s['phase']=='BATTLE' and s['mission']!='FINALE',
             'escort':escort.preview(game),
             'event_memory':event_memory.describe(game),
             'refugee':refugee.public(game),
             'water':water.public(game),
             'medicine':medicine.public(game),
             'local_cases':cases.public(game),
             'site':s['site'],'region':s['region'],'battle':s['battle'],
             'save':str(game.save_path),'sequence':s['sequence'],'help':HELP,
             'routes':game.cat.config['routes'],'teams':game.cat.config['teams'],
             'save_choices':sorted(p.parent.name for p in (BASE/'local').glob('*/save.json')),
             'next':[],'event':None,'layout':None,'cleared':[]}
    if s['phase']=='EXPLORE':
        payload.update(layout=game.layout,cleared=game.current['cleared'],next=game.next_regions())
        if s['site'] in game.manifest_region['events']:
            event,binding,state=game.event_info()
            payload['event']={'card':event,'binding':rogue_events.public_binding(binding),'state':state,
                              'offers':{o['option_id']:game.offer(event,o) for o in event['options'] if o.get('reward_bundle_id')=='RB-PLAN'}}
            payload['event']['plan_labels']={pid:plan_offers.label(game,pid)
                                            for ids in payload['event']['offers'].values() for pid in ids}
            if binding.get('book_offer'):
                payload['books']['event_offer']=book_rewards.offer(game,binding['book_offer']['source_key'])
    if s['battle']:payload['board']=game.cat.boards[s['battle']['board_id']]
    payload['campaign']={'facts':list(s['campaign']['facts'])} if s.get('campaign') else None
    t=s.get('tutorial_trip')
    payload['tutorial']={'choices':list(t['choices']),'observed':bool(t['observation']),'gear_offers':t['gear_offers']} if s['mission']=='TUTORIAL' and t else None
    payload['narrative']=narrative.public(game)
    letters=hidden_thread.public(game)
    if letters['discovered']:payload['hidden_thread']=letters
    payload['space']=region_space.public(game)
    if payload['space']:payload['layout']=None
    return payload


def make_server(game,port=0):
    token=secrets.token_urlsafe(24);current=[game]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def response(self,status,body,content_type='application/json; charset=utf-8'):
            raw=body.encode('utf-8') if isinstance(body,str) else json.dumps(body,ensure_ascii=False).encode('utf-8')
            self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(raw)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(raw)
        def do_GET(self):
            if self.path=='/'+token+'/':self.response(200,(BASE/'index.html').read_text(encoding='utf-8'),'text/html; charset=utf-8')
            elif self.path=='/'+token+'/space_view.js':self.response(200,(BASE/'space_view.js').read_text(encoding='utf-8'),'application/javascript; charset=utf-8')
            elif self.path=='/'+token+'/narrative_view.js':self.response(200,(BASE/'narrative_view.js').read_text(encoding='utf-8'),'application/javascript; charset=utf-8')
            elif self.path=='/'+token+'/boards':
                from board_gallery import render
                self.response(200,render(current[0].cat.boards),'text/html; charset=utf-8')
            elif self.path=='/'+token+'/state':self.response(200,view(current[0]))
            else:self.response(404,{'error':'not found'})
        def do_POST(self):
            expected=f'http://127.0.0.1:{self.server.server_port}'
            if self.path!='/'+token+'/action' or self.headers.get('Origin',expected)!=expected:
                self.response(403,{'error':'forbidden'});return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=16000:raise ValueError('请求长度不合法')
                request=json.loads(self.rfile.read(length));operation=request.get('op','command');g=current[0]
                if request.get('sequence')!=g.s['sequence'] or request.get('save')!=str(g.save_path):
                    self.response(409,view(g,'状态已变化，已刷新；请确认当前状态后再操作。'));return
                if operation=='command':message=g.execute(request['command'])
                elif operation=='new_campaign':
                    from app import new_path
                    current[0]=Game.new_campaign(seed=int(request.get('seed',11)),save_path=new_path(),catalog=g.cat)
                    message='已新建自然周目，旧档保留。先领取委任。'
                elif operation=='new':
                    from app import new_path
                    current[0]=Game.new(route=request['route'],team=request['team'],pack=request['pack'],seed=int(request['seed']),birth=request['birth'],case_mode=request.get('case_mode','EV03'),difficulty=request.get('difficulty','D0'),save_path=new_path(),catalog=g.cat)
                    message='已新建独立试验，旧档保留。'
                elif operation=='load':
                    name=request['name']
                    if Path(name).name!=name or name in ['.','..']:raise ValueError('存档名不合法')
                    current[0]=Game.load(BASE/'local'/name/'save.json',catalog=g.cat);message='已恢复原档，未重新抽样。'
                elif operation=='export':
                    path=g.save_path.with_name('report.json');g.export(path);message='已导出：'+str(path)
                else:raise ValueError('未知操作')
                self.response(200,view(current[0],message))
            except (ValueError,IndexError,KeyError,TypeError,OSError) as error:self.response(400,view(current[0],'未执行：'+str(error)))
    server=HTTPServer(('127.0.0.1',port),Handler)
    return server,f'http://127.0.0.1:{server.server_port}/{token}/'


def serve(game,port=0,open_browser=True):
    server,url=make_server(game,port)
    atomic_json(BASE/'local'/'server.json',{'url':url,'pid':os.getpid(),'save':str(game.save_path)})
    print('灰盒地址：'+url,flush=True);print('关闭此终端即可停止服务。进度每次操作自动保存。',flush=True)
    if open_browser:webbrowser.open(url)
    try:server.serve_forever()
    finally:server.server_close()
