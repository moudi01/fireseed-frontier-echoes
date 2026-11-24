"""Read-only overview rendered from the same cells used by combat."""
from html import escape
import math


def render(boards):
    colors={'GROUND':'#fff','HIGH_OBSTACLE':'#62676c','LOW_OBSTACLE':'#ab9d87',
            'SHALLOW_WATER':'#b9d9e9','DEEP_WATER':'#649abb','HIGH_GROUND':'#dfdcaa','FIXED_BRIDGE':'#debe8f'}
    cards=[]
    for b in boards.values():
        positions=[(math.sqrt(3)*(c['q']+c['r']/2),1.5*c['r']) for c in b['cells']]
        left=min(p[0] for p in positions)-math.sqrt(3)/2;right=max(p[0] for p in positions)+math.sqrt(3)/2
        top=min(p[1] for p in positions)-1;bottom=max(p[1] for p in positions)+1
        size=min(280/(right-left),230/(bottom-top))
        player=set(map(tuple,b['player_deploy_cells']));enemy=set(map(tuple,b['enemy_deploy_cells']))
        tiles=[]
        for c,(x,y) in zip(b['cells'],positions):
            x=160+(x-(left+right)/2)*size;y=135+(y-(top+bottom)/2)*size
            points=' '.join(f'{x+size*math.cos(i*math.pi/3+math.pi/6):.4f},{y+size*math.sin(i*math.pi/3+math.pi/6):.4f}' for i in range(6))
            fill=colors[c['terrain_id']];pos=(c['q'],c['r'])
            tiles.append(f'<polygon points="{points}" fill="{fill}" stroke="#9da3a8" stroke-width=".7"><title>{pos} {c["terrain_id"]}</title></polygon>')
            if pos in player or pos in enemy:
                mark,color=('我','#276ab3') if pos in player else ('敌','#b83e39')
                tiles.append(f'<text x="{x:.3f}" y="{y+3:.3f}" text-anchor="middle" fill="{color}" font-size="9">{mark}</text>')
        cards.append(f'<article><h2>{escape(b["name"])}</h2><p>{b["shape_name"]} · {b["cell_count"]}格</p><svg viewBox="0 0 320 270" aria-label="{escape(b["name"])}">{"".join(tiles)}</svg></article>')
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>多形状战场 · 棋盘总览</title><style>
body{font:15px system-ui,sans-serif;background:#f4f4f4;color:#222;margin:20px}h1{font-size:24px;margin:0 0 8px}h2{font-size:17px;margin:12px 12px 4px}p{margin:4px 12px 8px}header p{margin:8px 0 16px}main{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}article{background:white;border:1px solid #d1d5d8}article p{color:#555}svg{display:block;width:100%;height:220px}@media(max-width:850px){main{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style><header><h1>按场地选择棋盘</h1><p><span style="color:#276ab3">我：己方部署格</span>　<span style="color:#b83e39">敌：敌方部署格</span>（文字标记，不改变地形色）<br><span style="background:#b9d9e9">浅蓝：浅水，可走但较慢</span>　<span style="background:#649abb">深蓝：深水</span>　<span style="background:#ab9d87">灰褐：低障碍</span>　<span style="background:#62676c;color:white">深灰：高障碍</span>（后三者不可走）　<span style="background:#debe8f">棕黄：桥面</span>　<span style="background:#dfdcaa">浅黄：高地</span></p></header><main>'''+''.join(cards)+'</main></html>'
