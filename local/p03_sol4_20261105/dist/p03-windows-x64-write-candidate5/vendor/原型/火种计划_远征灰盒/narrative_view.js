/* Read-only text presentation; world actions are separate explicit controls. */
let narrativeSceneKey=null;
function renderNarrative(){
 const panel=$('narrativePanel'),n=state.narrative;panel.replaceChildren();
 if(!state.campaign||!n)return;
 panel.append(el('h3','剧情与引导'),el('p',n.hint));
 const scene=n.active,key=state.save+':'+(scene?.id||'');
 if(scene){
  if(key!==narrativeSceneKey)playing=false;
  const line=scene.lines[scene.cursor];
  panel.append(el('h4',scene.title+` · ${scene.cursor+1}/${scene.lines.length}`));
  panel.append(el('p',line.speaker+'：'+line.text));
  button(panel,scene.cursor+1===scene.lines.length?'读完':'下一句','dialogue next');
  button(panel,'跳过本段','dialogue skip');
 }
 narrativeSceneKey=key;
 button(panel,n.enabled?'关闭自动讲解':'开启自动讲解','dialogue auto '+(n.enabled?'off':'on'));
 const details=el('details');details.append(el('summary','已发生的故事 · '+n.history.length+'段'));
 const status={READING:'阅读中',READ:'已读',SKIPPED:'已跳过',ARCHIVED:'已收入记录',MUTED:'讲解关闭时记录'};
 for(const row of [...n.history].reverse())button(details,`第${row.day}日 · ${row.title}（${status[row.status]}）`,'dialogue replay '+row.id);
 panel.append(details);
 // Keep task decisions outside the text pager; all use existing transactions.
 const world=el('div');world.setAttribute('class','row');panel.append(world);
 const facts=state.campaign.facts;
 if(state.phase==='TOWN'){
  if(facts.includes('ST-102')&&!facts.includes('ST-103'))button(world,'与许苇核对调查','quest review CONFIRM');
  else if(facts.includes('ST-103')&&!facts.includes('ST-104'))button(world,'交存侦路报告','quest archive CONFIRM');
 }
 // Tutorial state is exposed independently of dialogue visibility and read status.
 const t=state.tutorial;
 if(t&&state.phase==='EXPLORE'){
  if(state.site==='D'&&!t.observed)button(world,'记录巡行现场','tutorial observe');
  if(state.site==='B_MATERIAL'&&!t.choices.includes('materials')){
   button(world,'领取材料','tutorial materials');button(world,'放弃材料','tutorial materials PASS');
  }
  if(state.site==='B_SUPPORT'&&!t.choices.includes('support')){
   const b=el('button','为操作目标领取护持');b.onclick=()=>act('tutorial support '+target());world.append(b);
   button(world,'放弃护持','tutorial support PASS');
  }
  if(state.site==='A'&&state.cleared.includes('A')&&!t.choices.includes('plan')){
   for(const id of ['PL01','PL02','PL05'])button(world,'领取方案 '+id,'tutorial plan '+id);
   button(world,'放弃方案','tutorial plan PASS');
  }
  if(state.site==='G'&&state.cleared.includes('G')&&!t.choices.includes('cache')){
   for(const id of t.gear_offers)button(world,'领取箱中装备 '+id,'tutorial cache '+id);
   button(world,'放弃箱中装备','tutorial cache PASS');
  }
 }
}
