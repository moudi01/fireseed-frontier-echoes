/* Minimal shared-ground renderer. Only server-discovered cells are received. */
function renderSpace(){
 const s=state.space,view=$('map'),binding=s.battle_binding;
 view.setAttribute('viewBox','0 0 560 440');view.setAttribute('tabindex','0');
 view.setAttribute('aria-label','连续区域地图。点击已发现道路行走；Q W E A S D逐格移动。');
 view.style.background='#17212b';
 const focusBattle=binding&&(state.phase==='BATTLE'||s.contact);
 const center=focusBattle?[binding.origin[0]+3,binding.origin[1]+4]:s.position;
 const radius=focusBattle?20:16,root=Math.sqrt(3);
 const to=(q,r)=>[280+root*((q-center[0])+(r-center[1])/2)*radius,220+1.5*(r-center[1])*radius];
 const hex=(x,y,scale=1)=>Array.from({length:6},(_,i)=>[x+radius*scale*Math.cos(Math.PI*i/3+Math.PI/6),y+radius*scale*Math.sin(Math.PI*i/3+Math.PI/6)].join(',')).join(' ');
 const colors={GROUND:'#e5e7eb',SHALLOW_WATER:'#add1df',DEEP_WATER:'#436c8b',LOW_OBSTACLE:'#877666',HIGH_OBSTACLE:'#35404b',FIXED_BRIDGE:'#d5b583',HIGH_GROUND:'#c7c39a'};
 for(const c of s.cells){
  const[x,y]=to(c.q,c.r);if(x < -30||x>590||y < -30||y>470)continue;
  const tile=svg('polygon',{points:hex(x,y),fill:colors[c.terrain_id]||'#35404b',stroke:'#586675','stroke-width':.5,opacity:c.visible?1:.36,'data-world-cell':`${c.q},${c.r}`});
  const title=document.createElementNS(NS,'title');title.textContent=`${c.q},${c.r} ${c.terrain_id}${c.visible?'':'（已探索）'}`;tile.append(title);
  if(c.walkable&&state.phase==='EXPLORE'){tile.style.cursor='pointer';tile.onclick=()=>act(`walkto ${c.q} ${c.r}`)}
 }
 if(s.last_walk.length>1)svg('polyline',{points:s.last_walk.map(p=>to(...p).join(',')).join(' '),fill:'none',stroke:'#245c91','stroke-width':2,'stroke-dasharray':'3 3','pointer-events':'none'});
 for(const o of s.objects){
  const[x,y]=to(...o.position);if(x<0||x>560||y<0||y>440)continue;
  if(o.lamp)svg('circle',{cx:x,cy:y,r:radius*2.2,fill:'#ffd36b',opacity:.2,'pointer-events':'none'});
  const mark=o.kind==='enemy'?(o.cleared?'✓':'!'):o.kind==='event'?'?':o.kind==='bell'?'钟':o.id;
  svg('circle',{cx:x,cy:y,r:12,fill:o.kind==='enemy'&&!o.cleared?'#8f2828':'#f5f0dc',stroke:'#263645','stroke-width':2});
  svg('text',{x,y:y+5,'text-anchor':'middle',fill:o.kind==='enemy'&&!o.cleared?'white':'#1c2833','font-size':13,'pointer-events':'none'},mark);
  svg('text',{x:x+17,y:y-10,fill:'#fff','font-size':12,stroke:'#17212b','stroke-width':3,'paint-order':'stroke'},o.name+(o.lamp?' · 灯':''));
 }
 if(binding&&(s.contact||state.phase==='BATTLE')){
  for(const c of s.battle_cells){
   const[x,y]=to(c.q+binding.origin[0],c.r+binding.origin[1]);const deploy=s.deploy_cells.some(p=>p[0]===c.q&&p[1]===c.r);
   const cell=svg('polygon',{points:hex(x,y,.94),fill:'transparent',stroke:deploy?'#1764a0':'#df9835','stroke-width':deploy?2:1.2,'data-local-cell':`${c.q},${c.r}`});
   const title=document.createElementNS(NS,'title');title.textContent=`战场格 ${c.q},${c.r}${deploy?' · 可部署':''}`;cell.append(title);
   if(deploy&&state.phase==='EXPLORE'){cell.style.cursor='pointer';cell.onclick=()=>act(`place ${target()} ${c.q} ${c.r}`)}
  }
  const actors=state.phase==='BATTLE'?state.battle.actors:[...s.preview.map(a=>({id:a.instance_id,side:'enemy',hp:a.stats.hp,pos:a.position,kind:a.enemy_id,stats:a.stats,facing:Number(a.facing?.replace('D','')||0)})),...state.party.filter(a=>a.deployed).map(a=>({id:a.instance_id,side:'player',hp:a.hp,pos:a.position,kind:a.unit_id,facing:a.facing}))];
  const world=p=>to(p[0]+binding.origin[0],p[1]+binding.origin[1]);
  for(const a of actors){
   if(a.hp>0&&a.pending)for(const p of a.pending.peril_outer_cells||[]){const[x,y]=world(p);const mark=svg('polygon',{points:hex(x,y,.85),fill:'none',stroke:'#a46212','stroke-width':2,'stroke-dasharray':'4 4'});const hint=document.createElementNS(NS,'title');hint.textContent='条件外圈：内圈有人未撤才引爆，内圈撤空则整招落空';mark.append(hint)}
   if(a.hp>0&&a.pending)for(const p of a.pending.cells){const[x,y]=world(p);svg('polygon',{points:hex(x,y,.85),fill:'none',stroke:'#f5a12b','stroke-width':3});svg('text',{x,y:y-8,fill:'#111','font-size':12},a.pending.due)}
   const[x,y]=world(a.pos);const dot=svg('circle',{cx:x,cy:y,r:state.phase==='BATTLE'?11:7,fill:a.hp<=0?'#747b82':a.side==='player'?'#185f96':'#ad3131',stroke:'white','stroke-width':1});
   const title=document.createElementNS(NS,'title');title.textContent=`${a.id} ${a.kind} HP ${a.hp}`;dot.append(title);
   if(state.phase==='BATTLE')svg('text',{x,y:y+4,'text-anchor':'middle',fill:'white','font-size':10},a.hp);
   const d=[[1,0],[0,1],[-1,1],[-1,0],[0,-1],[1,-1]][a.facing||0],end=world([a.pos[0]+d[0]*.4,a.pos[1]+d[1]*.4]);
   svg('line',{x1:x,y1:y,x2:end[0],y2:end[1],stroke:'#18202b','stroke-width':2});
   if(a.pending?.destination){const[dx,dy]=world(a.pending.destination);svg('text',{x:dx,y:dy+4,fill:'#642577','font-size':12},'落')}
  }
  if(state.phase==='BATTLE')for(const a of actors){
   if(a.hp<=0||!a.pending?.locks_target)continue;
   const victim=actors.find(v=>v.id===a.pending.target&&v.hp>0);if(!victim)continue;
   const[x,y]=world(victim.pos);
   const ring=svg('circle',{cx:x,cy:y,r:16,fill:'none',stroke:'#be2873','stroke-width':3,'pointer-events':'none'});
   const hint=document.createElementNS(NS,'title');hint.textContent=`${a.pending.name||a.pending.move_id}锁定本人 ${victim.id}，第${a.pending.due}拍无弹道直击；换格和遮挡仍追踪，可用护盾、减伤承接，或打断、延后`;ring.append(hint);
   svg('text',{x,y:y-21,'text-anchor':'middle',fill:'#fff','font-size':11,stroke:'#6d1643','stroke-width':3,'paint-order':'stroke','pointer-events':'none'},`锁人 ${a.pending.due}`);
  }
  if(state.phase==='BATTLE')for(const [row,blocked] of [[state.battle.edge_reservation,false],[state.battle.closed_edge,true]]){
   if(!row||blocked&&row.expires<state.battle.tick)continue;
   const[a,b]=row.edge.map(world),dx=b[0]-a[0],dy=b[1]-a[1],length=Math.hypot(dx,dy),mx=(a[0]+b[0])/2,my=(a[1]+b[1])/2;
   svg('line',{x1:mx-dy/length*10,y1:my+dx/length*10,x2:mx+dy/length*10,y2:my-dx/length*10,stroke:blocked?'#bd2424':'#b36a13','stroke-width':4,'stroke-dasharray':blocked?'none':'3 3'});
  }
 }
 if(state.phase!=='BATTLE'){const[x,y]=to(...s.position);svg('circle',{cx:x,cy:y,r:10,fill:'#1764a0',stroke:'#fff','stroke-width':3});svg('text',{x,y:y+4,'text-anchor':'middle',fill:'#fff','font-size':10},'队')}
 svg('rect',{x:0,y:0,width:560,height:28,fill:'#17212b'});
 svg('text',{x:12,y:19,fill:'white','font-size':13},`位置 ${s.position.join(', ')} · 已走 ${s.steps} 格 · ${state.phase==='BATTLE'?'原地战斗':'附近照明 / 暗处为已探索记忆'}`);
 if(state.phase==='EXPLORE'){
  const controls=el('div');controls.className='spatial-controls';$('context').append(controls);
  for(const[d,label]of [[4,'↖ Q'],[5,'↗ W'],[0,'→ E'],[3,'← A'],[2,'↙ S'],[1,'↘ D']])button(controls,label,'walk '+d);
  $('context').append(el('p','点击已发现道路会沿路行走，接敌即停。地图聚焦时可用 Q W E / A S D 移动；靠近后交互，不会自动选择事件。'));
  for(const o of s.objects.filter(o=>o.near&&o.kind!=='enemy'))button($('context'),'交互：'+o.name,o.command||'interact '+o.id);
  if(s.contact&&!state.cleared.includes(s.contact.site)){
   button($('actions'),'按当前编队开战','fight');button($('actions'),'退回接敌边界外','retreat');
   $('context').append(el('p','敌阵已公开：'+s.preview.map(a=>`${a.enemy_id} HP${a.stats.hp}`).join('；')+'。橙色格线为本处战场，蓝边为部署格；选中队员后点击蓝边格可布阵。'));
  }
 }
 view.onkeydown=e=>{const d={q:4,w:5,e:0,a:3,s:2,d:1}[e.key.toLowerCase()];if(d!==undefined&&state.phase==='EXPLORE'){e.preventDefault();act('walk '+d)}};
}
