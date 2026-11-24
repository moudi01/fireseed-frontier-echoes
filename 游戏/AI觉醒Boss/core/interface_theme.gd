extends RefCounted
const ACTION_HEIGHT=40
const ACTION_GAP=8
static func action_style(button: Button,role="secondary"):
	button.custom_minimum_size.y=ACTION_HEIGHT
	button.alignment=HORIZONTAL_ALIGNMENT_CENTER
	button.theme_type_variation={"primary":"PrimaryAction","danger":"DangerAction"}.get(role,"")
const SURFACES={"eddfbf":"202f31","dfc99f":"2d4142","f8e8c5":"3c5552","c8a673":"233736","d4c5a7":"273333","e8d5b3":"3a514a","fff0ca":"263d3b"}
static func title_font() -> SystemFont:
	var f=SystemFont.new();f.font_names=PackedStringArray(["SimSun","Noto Serif CJK SC","Microsoft YaHei"]);return f
static func box(color: String,border="727663",margin=12) -> StyleBoxFlat:
	var s=StyleBoxFlat.new();s.bg_color=Color(SURFACES.get(color,color));s.border_color=Color("738071");s.set_border_width_all(1);s.set_corner_radius_all(6);s.content_margin_left=margin;s.content_margin_right=margin;s.content_margin_top=10;s.content_margin_bottom=10
	s.shadow_color=Color(0,0,0,.22);s.shadow_size=10;s.shadow_offset=Vector2(0,4);return s
static func create() -> Theme:
	var t=Theme.new();var f=SystemFont.new();f.font_names=PackedStringArray(["Microsoft YaHei UI","Microsoft YaHei","Noto Sans CJK SC"]);t.default_font=f;t.default_font_size=17
	for type in ["Label","CheckBox","Button","OptionButton","LineEdit","SpinBox"]:
		t.set_color("font_color",type,Color("eee8d8"));t.set_color("font_hover_color",type,Color("fff4d8"));t.set_color("font_pressed_color",type,Color("fff4d8"));t.set_color("font_disabled_color",type,Color("88938b"))
	for type in ["Button","OptionButton","LineEdit"]:
		t.set_stylebox("normal",type,box("dfc99f"));t.set_stylebox("hover",type,box("f8e8c5"));t.set_stylebox("pressed",type,box("c8a673"));t.set_stylebox("disabled",type,box("d4c5a7"));t.set_stylebox("focus",type,box("e8d5b3"))
	t.set_type_variation("PrimaryAction","Button")
	for state in ["normal","hover","pressed","focus"]:
		t.set_stylebox(state,"PrimaryAction",box("c5a872" if state=="normal" else ("dfc48e" if state=="hover" else "b29662")))
	for state in ["font_color","font_hover_color","font_pressed_color"]:t.set_color(state,"PrimaryAction",Color("263330"))
	t.set_type_variation("DangerAction","Button")
	for state in ["normal","hover","pressed","focus"]:
		var style=box("dfc99f" if state=="normal" else "f8e8c5")
		style.border_color=Color("ac8276");t.set_stylebox(state,"DangerAction",style)
	for state in ["font_color","font_hover_color","font_pressed_color"]:t.set_color(state,"DangerAction",Color("efc5b3"))
	for type in ["PrimaryAction","DangerAction"]:
		t.set_stylebox("disabled",type,t.get_stylebox("disabled","Button"));t.set_color("font_disabled_color",type,Color("88938b"))
	t.set_stylebox("separator","HSeparator",separator())
	t.set_constant("separation","VBoxContainer",12);t.set_constant("h_separation","GridContainer",8);t.set_constant("v_separation","GridContainer",8)
	return t
static func separator() -> StyleBoxLine:
	var line=StyleBoxLine.new();line.color=Color(.58,.62,.51,.32);line.thickness=1;line.grow_begin=0;line.grow_end=0;return line
