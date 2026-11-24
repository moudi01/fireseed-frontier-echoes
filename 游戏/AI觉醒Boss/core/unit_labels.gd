extends Node
## Screen-space names only. All combat, picking, health and warnings stay on Board.
const LAYOUT=preload("res://core/label_layout.gd")
var board
var layer=CanvasLayer.new()
var holder=Control.new()
var nodes={}
var report=[]
var reserved=[]
var enabled=true
var preferred={}
var leaders={}
func configure(owner_board):
	board=owner_board;layer.layer=-1;layer.name="UnitNames";add_child(layer)
	holder.mouse_filter=Control.MOUSE_FILTER_IGNORE;layer.add_child(holder)
func _process(_delta):refresh()
func clear_nodes():
	for node in nodes.values():holder.remove_child(node);node.queue_free()
	for line in leaders.values():holder.remove_child(line);line.queue_free()
	leaders.clear()
	nodes.clear();preferred.clear();report.clear()
	if is_instance_valid(board):board.label_layout_report=[]
func desired(id:int)->bool:
	var figure=board.figures[id]
	return figure.node.is_visible_in_tree() and figure.get("nameplate_allowed",true)
func refresh():
	if not is_instance_valid(board) or board.camera==null:return
	layer.visible=board.is_visible_in_tree() and enabled
	if not board.is_visible_in_tree():return
	var viewport=board.get_viewport().get_visible_rect();holder.size=viewport.size
	for id in nodes.keys():
		if not board.figures.has(id):
			holder.remove_child(nodes[id]);nodes[id].queue_free();nodes.erase(id);preferred.erase(id)
			if leaders.has(id):holder.remove_child(leaders[id]);leaders[id].queue_free();leaders.erase(id)
	var blocks=reserved.duplicate()
	for figure in board.figures.values():
		if not figure.health_back.is_visible_in_tree():continue
		var world=figure.health_back.global_position;var center=board.camera.unproject_position(world)
		var pixels=board.camera.unproject_position(world+board.camera.global_basis.x).distance_to(center)
		var size=figure.health_back.mesh.size*pixels*absf(figure.node.global_basis.get_scale().x)
		blocks.append(Rect2(center-size*.5,size).grow(3))
	for warning in board.effects.get_children():
		if not warning is Label3D or not warning.is_visible_in_tree():continue
		var center=board.camera.unproject_position(warning.global_position);var pixels=board.camera.unproject_position(warning.global_position+board.camera.global_basis.x).distance_to(center)
		var size=warning.font.get_string_size(warning.text,HORIZONTAL_ALIGNMENT_LEFT,-1,warning.font_size)*warning.pixel_size*pixels
		blocks.append(Rect2(center-size*.5,size).grow(4))
	var items=[];var omitted=[]
	for id in board.figures:
		var figure=board.figures[id];var source:Label3D=figure.label
		var show=desired(id)
		if not nodes.has(id):
			var line=Line2D.new();line.width=1;line.default_color=Color(.78,.82,.73,.55);line.z_index=-1;holder.add_child(line);leaders[id]=line
			var label=Label.new();label.mouse_filter=Control.MOUSE_FILTER_IGNORE;label.add_theme_font_override("font",board.font);label.add_theme_color_override("font_outline_color",Color(0.08,.09,.08,.92));label.add_theme_constant_override("outline_size",3);holder.add_child(label);nodes[id]=label
			var padding=StyleBoxEmpty.new();padding.content_margin_left=3;padding.content_margin_right=3;padding.content_margin_top=3;padding.content_margin_bottom=3;label.add_theme_stylebox_override("normal",padding)
		var label:Label=nodes[id];label.visible=false;leaders[id].visible=false
		if not enabled:source.visible=show and (board.stats.size()<=16 or id in board.selected_ids or id==board.label_focus_id or not board.stats.get(id,{}).get("alive",true));continue
		source.visible=false
		var alive=board.stats.get(id,{}).get("alive",true) or figure.get("contact_death_pending",false)
		var world=figure.node.to_global(Vector3(0,1.65 if alive else .12,0))
		var anchor=board.camera.unproject_position(world)
		var priority=1000 if id in board.selected_ids else (900 if id==board.label_focus_id else (800 if int(board.stats.get(id,{}).get("charge_ticks_left",0))>0 else (100 if alive else 50)))
		if not show or board.camera.is_position_behind(world) or not viewport.has_point(anchor):
			omitted.append({"id":id,"visible":false,"rect":Rect2(),"offset":Vector2.ZERO,"anchor":anchor,"priority":priority,"reason":"policy" if not show else "outside_camera"});continue
		if label.get_theme_color("font_color")!=source.modulate:label.add_theme_color_override("font_color",source.modulate)
		var pixel_units=board.camera.unproject_position(world+board.camera.global_basis.x).distance_to(anchor)
		var font_size=clampi(roundi(source.font_size*source.pixel_size*pixel_units*absf(figure.node.global_basis.get_scale().x)),16,28)
		if label.text!=source.text or label.get_meta("measured_font",-1)!=font_size:
			label.text=source.text;label.add_theme_font_size_override("font_size",font_size)
			label.custom_minimum_size=Vector2.ZERO;label.size=Vector2.ZERO
			var measured=label.get_combined_minimum_size().ceil()+Vector2(4,2)
			label.custom_minimum_size=measured;label.size=measured;label.set_meta("measured_font",font_size)
		var size=label.custom_minimum_size
		items.append({"id":id,"anchor":anchor,"size":size,"priority":priority,"preferred_offset":preferred.get(id,Vector2.ZERO)})
	items.sort_custom(func(a,b):return a.id<b.id if a.priority==b.priority else a.priority>b.priority)
	if items.size()>24:
		for item in items.slice(24):omitted.append({"id":item.id,"visible":false,"rect":Rect2(),"offset":Vector2.ZERO,"anchor":item.anchor,"priority":item.priority,"reason":"budget"})
		items=items.slice(0,24)
	# Selected/focus/windup names get a wider bounded escape corridor. Lower
	# priority names cannot displace them or share their final rectangles.
	var important=items.filter(func(item):return item.priority>=800)
	var ordinary=items.filter(func(item):return item.priority<800)
	report=LAYOUT.solve(important,viewport.grow(-8),blocks,160.0)
	var lower_blocks=blocks.duplicate()
	for row in report:
		if row.visible:lower_blocks.append(row.rect.grow(3))
	report.append_array(LAYOUT.solve(ordinary,viewport.grow(-8),lower_blocks))
	for row in report:
		var id=int(row.id);row["anchor"]=items.filter(func(item):return int(item.id)==id)[0].anchor;row["priority"]=items.filter(func(item):return int(item.id)==id)[0].priority
		var label:Label=nodes[id];label.visible=row.visible
		if row.visible:
			label.position=row.rect.position;label.size=row.rect.size;preferred[id]=row.offset
			if row.offset.length()>8:
				var end=Vector2(clampf(row.anchor.x,row.rect.position.x,row.rect.end.x),clampf(row.anchor.y,row.rect.position.y,row.rect.end.y))
				leaders[id].points=PackedVector2Array([row.anchor,end]);leaders[id].visible=true
	report.append_array(omitted)
	if not enabled:report=[];preferred.clear()
	board.label_layout_report=report
