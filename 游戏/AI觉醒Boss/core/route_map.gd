extends Control
## Read-only geography derived from locked campaign state. Entering a location is UI only.
signal entered
var model={}
var markers=[]
var font: Font
var origin=Vector2.ZERO
var zoom=1.0
const POS=[Vector2(130,535),Vector2(265,400),Vector2(385,470),Vector2(500,320),Vector2(645,395),Vector2(735,235),Vector2(860,310)]

static func describe(state: Dictionary) -> Dictionary:
	var p=state.pending;var route=str(p.get("route",""));var phase=str(state.phase)
	var nodes=[];var current="";var title="";var notes=[];var choices=[];var branches={};var visited=[];var return_from=""
	if route=="tutorial_trail":
		title="林道侦查";var j=p.journey
		nodes=[["base","前线据点"],["first","林口遭遇"],["caravan","商队残骸"],["camp","林间营地"],["formation","精英前哨"],["elite","守路精英"],["return","归途 · 运输"]]
		current="return" if phase=="settlement" else str(j.node)
		if not j.caravan_choice.is_empty():notes.append("商队："+{"collect":"收取物资","mark":"留下路标 +1日","pass":"沿路继续"}.get(j.caravan_choice,""))
		if not j.camp_choice.is_empty():notes.append("营地："+("消耗食物休整" if j.camp_choice=="rest" else "跳过休整"))
		choices=["base"]
		if not j.first_result.is_empty():choices.append("first")
		if not j.caravan_choice.is_empty():choices.append("caravan")
		if not j.camp_choice.is_empty():choices.append("camp")
		if not j.baseline.is_empty():choices.append("formation")
		if phase=="settlement":
			if j.node=="return":visited.append("caravan" if j.caravan_choice.is_empty() else ("camp" if j.camp_choice.is_empty() else "formation"))
			elif j.node=="elite":
				if state.battle_result.get("result")=="player_win":choices.append("elite")
				else:visited.append("elite")
			else:visited.append("first")
	elif route=="rescue_path":
		title="失联地点 · 营救专线";var r=p.rescue_path
		nodes=[["base","前线据点"],["approach","旧路入口"],["camp","林后营地"],["gate","营门整备"],["battle","营地守卫"],["return","归途 · 人员接回"]]
		current="return" if phase=="settlement" else str(r.node);choices=["base"]
		for decision in r.choices:
			choices.append(decision.node)
			branches[decision.node]=decision.choice
			notes.append({"direct":"沿路搜寻 · 不加日","detour":"绕到林后 · +1日","breach":"立即突入 · 不加日","wait":"等待换岗 · +1日"}.get(decision.choice,decision.choice))
		if r.node=="battle":choices.append("gate")
		if phase=="settlement" and not r.withdrawn:
			if state.battle_result.get("result")=="player_win":choices.append("battle")
			else:visited.append("battle")
		if r.withdrawn:
			visited.append(["approach","camp","gate"][mini(2,r.choices.size())]);notes.append("已撤离：已到达与已处理分别标记")
	elif route=="boundary":
		title="深核边界";var b=p.boundary
		nodes=[["base","前线据点"],["guards","路口守卫"],["approach","王座台阶"],["wall","道路阻断" if b.stage in ["wall","observed"] or b.completed else "前方道路"],["return","归途 · 运输"]]
		current="return" if phase=="settlement" else ("wall" if b.stage=="observed" else str(b.stage));choices=["base"]
		if b.stage!="guards":choices.append("guards")
		if b.stage in ["wall","observed"] or b.completed:choices.append("approach")
		if b.completed:choices.append("wall")
		if phase=="settlement" and not b.completed:visited.append("approach" if b.stage=="returned" else "guards")
		if b.observed:notes.append("已观察前方；可以返回")
	else:
		title={"commission":"短程委托","outskirts":"边境出征","outpost":"重甲前哨","tutorial":"林口训练","rescue":"旧营救行动"}.get(route,"远征")
		nodes=[["base","前线据点"],["battle",title+" · 目标"],["return","归途 · 运输"]]
		current="return" if phase=="settlement" else "battle";choices=["base"]
		if phase=="settlement":
			if state.battle_result.get("result")=="player_win":choices.append("battle")
			else:visited.append("battle")
	var result=[]
	if phase=="settlement":
		# Returning uses the actual last reached location, never a link through skipped nodes.
		for n in nodes:
			if n[0] in choices or n[0] in visited:return_from=n[0]
	for i in range(nodes.size()):
		var n=nodes[i];var pos=POS[i] if nodes.size()==7 else Vector2(140+float(i)*700.0/float(nodes.size()-1),420-90*sin(float(i)*1.65))
		if n[0]=="return":pos=Vector2(155,225)
		result.append({"id":n[0],"title":n[1],"pos":pos,"status":"current" if n[0]==current else ("done" if n[0] in choices else ("visited" if n[0] in visited else "future"))})
	return {"key":"%d:%s:%s:%s:%s"%[int(state.expedition),route,phase,current,str(p.get("boundary",{}).get("stage",""))],"title":title,"nodes":result,"current":current,"notes":notes,"branches":branches,"return_from":return_from,"route":route,"day":int(state.day),"is_return":phase=="settlement","failed":phase=="settlement" and state.battle_result.get("result") in ["enemy_win","draw"]}

func _ready():
	font=SystemFont.new();font.font_names=PackedStringArray(["Microsoft YaHei UI","Microsoft YaHei","Noto Sans CJK SC"])
	resized.connect(layout)
func configure(state: Dictionary):
	model=describe(state)
	for child in markers:remove_child(child);child.queue_free()
	markers=[]
	for n in model.nodes:
		var b=Button.new();b.text=("▶ " if n.status=="current" else ("✓ " if n.status=="done" else ("○ " if n.status=="visited" else "◇ ")))+n.title
		b.theme=preload("res://core/interface_theme.gd").create();b.add_theme_font_override("font",font)
		var style=StyleBoxFlat.new();style.bg_color=Color("b79b62") if n.status=="current" else (Color("596b62") if n.status=="done" else Color("d8ccb0"))
		style.border_color=Color("35483f") if n.status=="current" else Color("ac9c7c");style.set_border_width_all(2 if n.status=="current" else 1);style.set_corner_radius_all(5)
		var hover=style.duplicate();hover.bg_color=hover.bg_color.lightened(.08)
		for slot in ["normal","disabled"]:b.add_theme_stylebox_override(slot,style)
		for slot in ["hover","pressed","hover_pressed"]:b.add_theme_stylebox_override(slot,hover)
		var ink=Color("eee7d6") if n.status=="done" else Color("273833")
		for slot in ["font_color","font_hover_color","font_pressed_color","font_disabled_color"]:b.add_theme_color_override(slot,ink)
		b.tooltip_text="当前位置：点击进入" if n.status=="current" else ("已经处理" if n.status=="done" else ("已到达后折返；未完成目标" if n.status=="visited" else "尚未到达，不能跳过前方节点"))
		b.mouse_default_cursor_shape=Control.CURSOR_POINTING_HAND if n.status=="current" else Control.CURSOR_ARROW
		b.pressed.connect(func():
			if n.status=="current":entered.emit())
		add_child(b);markers.append(b)
	layout()
func layout():
	if model.is_empty():return
	zoom=minf(size.x/1000.0,size.y/720.0);origin=(size-Vector2(1000,720)*zoom)*.5
	for i in range(markers.size()):
		var b=markers[i];var n=model.nodes[i]
		b.position=origin+(n.pos+Vector2(-95,24 if n.id=="base" else 32))*zoom;b.size=Vector2(190,48)*zoom
		b.add_theme_font_size_override("font_size",maxi(12,int(18*zoom)))
	queue_redraw()
func text_at(pos: Vector2,text: String,color=Color("544932"),size_value=20):draw_string(font,pos,text,HORIZONTAL_ALIGNMENT_LEFT,-1,size_value,color)
func _draw():
	if model.is_empty():return
	draw_rect(Rect2(Vector2.ZERO,size),Color("35483f"));draw_set_transform(origin,0,Vector2.ONE*zoom)
	draw_rect(Rect2(16,16,968,688),Color("e2d2b4"));draw_rect(Rect2(26,26,948,668),Color("9a7955"),false,2)
	# Quiet sheet border and compass: consistent ink, limited ornament.
	for y in [34,686]:draw_line(Vector2(40,y),Vector2(960,y),Color("b7a882"),1,true)
	draw_line(Vector2(920,78),Vector2(920,132),Color("596b72"),2,true)
	draw_line(Vector2(901,106),Vector2(939,106),Color("596b72"),1,true)
	draw_colored_polygon(PackedVector2Array([Vector2(920,73),Vector2(914,94),Vector2(926,94)]),Color("35483f"))
	text_at(Vector2(911,63),"北",Color("596b72"),16)
	# Fixed geographic landmarks: no procedural roll consumes campaign randomness.
	draw_colored_polygon(PackedVector2Array([Vector2(32,300),Vector2(270,235),Vector2(500,285),Vector2(640,180),Vector2(970,200),Vector2(970,580),Vector2(520,555),Vector2(230,630),Vector2(32,530)]),Color("bec3a4"))
	var river=PackedVector2Array([Vector2(565,100),Vector2(530,180),Vector2(565,240),Vector2(570,320),Vector2(600,410),Vector2(575,490),Vector2(630,600)])
	draw_polyline(river,Color("93a9aa"),16,true);draw_polyline(river,Color("cad2be"),3,true)
	for i in range(42):
		var p=Vector2(72+(i*131)%850,190+(i*73)%370)
		if model.nodes.any(func(n):return n.pos.distance_to(p)<78):continue
		draw_line(p+Vector2(0,8),p+Vector2(0,24),Color("76694b"),3)
		draw_colored_polygon(PackedVector2Array([p+Vector2(-14,12),p+Vector2(0,-20),p+Vector2(14,12)]),Color("778569"))
	for i in range(6):
		var p=Vector2(660+i*46,135+abs(3-i)*6)
		draw_colored_polygon(PackedVector2Array([p+Vector2(-38,40),p+Vector2(0,-24),p+Vector2(40,40)]),Color("aaa894"))
	var previous={}
	for n in model.nodes:
		if n.id=="return":
			var source=model.nodes.filter(func(item):return item.id==model.return_from)
			if not source.is_empty():
				var home_path=PackedVector2Array([source[0].pos,Vector2(source[0].pos.x,165),Vector2(320,165),n.pos,model.nodes[0].pos])
				draw_polyline(home_path,Color("b9a677"),10,true);draw_polyline(home_path,Color("8b7351"),3,true)
			else:draw_line(model.nodes[-2].pos,n.pos,Color("c5b68c"),2,true)
		elif not previous.is_empty():
			var a=previous.pos;var b=n.pos;var midpoint=(a+b)*.5+Vector2(0,22)
			var path=PackedVector2Array([a,midpoint,b]);draw_polyline(path,Color("b9a677"),15,true)
			var indirect=model.branches.get(previous.id,"") in ["detour","wait"]
			draw_polyline(path,Color("8b7351") if previous.status=="done" and not indirect else Color("c5b68c"),3,true)
			if model.route=="rescue_path" and previous.id in ["approach","camp"]:
				var detour=PackedVector2Array([a,(a+b)*.5+Vector2(0,-105),b]);draw_polyline(detour,Color("8b7351") if indirect else Color("b4b18b"),5 if indirect else 3,true)
				text_at((a+b)*.5+Vector2(-46,-107),"绕行 +1日" if previous.id=="approach" else "等待 +1日",Color("687051"),16)
				text_at((a+b)*.5+Vector2(-44,16),"直行 · 不加日" if previous.id=="approach" else "突入 · 不加日",Color("756548"),16)
		var c=Color("8b6d45") if n.status in ["done","visited"] else Color("c3b58f")
		if n.status=="current":draw_circle(n.pos,26,Color("b79b62"));c=Color("35483f")
		draw_circle(n.pos,17,c);draw_circle(n.pos,13,Color("eee7d6"))
		node_symbol(n.pos,n.id,Color("35483f") if n.status=="current" else Color("84775e"))
		if n.status=="current":text_at(n.pos+Vector2(-38,-38),"你在这里",Color("8d4827"),20)
		previous=n
	text_at(Vector2(60,78),model.title+" · 行军图",Color("4e4936"),32)
	text_at(Vector2(62,112),"第%d日  /  标记当前位置，确认后进入节点"%model.day,Color("71674d"),18)
	text_at(Vector2(62,628),"● 当前位置    ✓ 已处理    ○ 到达后折返    ◇ 尚未到达",Color("655b43"),18)
	text_at(Vector2(62,662),"查看地图与进入地点不耗日；事件选择的额外消耗会单独提示。",Color("71674d"),17)
	draw_set_transform(Vector2.ZERO,0,Vector2.ONE)

func node_symbol(p: Vector2,id: String,ink: Color):
	if id in ["base","return"]:
		draw_polyline(PackedVector2Array([p+Vector2(-8,0),p+Vector2(0,-7),p+Vector2(8,0)]),ink,2,true)
		draw_rect(Rect2(p+Vector2(-5,0),Vector2(10,7)),ink,false,2)
	elif id=="camp":
		draw_polyline(PackedVector2Array([p+Vector2(-8,7),p+Vector2(0,-8),p+Vector2(8,7),p+Vector2(-8,7)]),ink,2,true)
		draw_line(p+Vector2(0,-3),p+Vector2(3,7),ink,2,true)
	elif id=="caravan":
		draw_rect(Rect2(p+Vector2(-8,-5),Vector2(15,9)),ink,false,2)
		for x in [-5,5]:draw_circle(p+Vector2(x,7),2.5,ink)
	else:
		draw_line(p+Vector2(-6,-7),p+Vector2(6,7),ink,2,true);draw_line(p+Vector2(6,-7),p+Vector2(-6,7),ink,2,true)
