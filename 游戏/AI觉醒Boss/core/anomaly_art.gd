extends RefCounted
## Shared static staging for formal memory/boundary and the independent demo.
## No collision, flashing, random draws, timers or campaign commands.
const KIT=preload("res://core/scenery_kit.gd")
static func room(parent: Node3D,center=Vector3(0,0,-.5),reduced=true):
	var root=Node3D.new();root.name="WhiteRoom";root.position=center;root.set_meta("reduced",reduced);parent.add_child(root)
	var wall="9eaaa4" if reduced else "d2d9d4"
	KIT.block(root,Vector3(0,-.06,0),Vector3(5.6,.16,4.4),"a6b1ad","stone")
	KIT.block(root,Vector3(0,1.3,-2.2),Vector3(5.6,2.6,.12),wall,"wall")
	KIT.block(root,Vector3(-2.8,1.3,0),Vector3(.12,2.6,4.4),wall,"wall")
	for x in [-2.1,-.7,.7,2.1]:
		for z in [-1.46,0,1.46]:KIT.block(root,Vector3(x,.032,z),Vector3(1.37,.035,1.42),"a3afa6" if reduced else "c0c9c2","stone")
	for x in [-2.65,2.65]:KIT.block(root,Vector3(x,.06,0),Vector3(.025,.018,4.2),"788e89","iron")
	for y in [.18,2.4]:KIT.block(root,Vector3(0,y,-2.12),Vector3(5.4,.035,.025),"9caaa6","stone")
	# One quiet discontinuity repeats the floor seam on the rear wall.
	KIT.block(root,Vector3(.72,1.3,-2.12),Vector3(.025,2.4,.018),"8c9c98","stone")
	KIT.block(root,Vector3(.78,.065,0),Vector3(.018,.012,4.1),"8c9c98","stone")
	var chair=Node3D.new();chair.name="EmptyChair";chair.position=Vector3(0,0,.1);root.add_child(chair)
	KIT.block(chair,Vector3(0,.59,0),Vector3(.77,.11,.75),"7f9188","wood")
	for x in [-.30,.30]:
		for z in [-.29,.29]:KIT.block(chair,Vector3(x,.29,z),Vector3(.075,.58,.075),"566f64","wood")
		KIT.block(chair,Vector3(x,.96,-.32),Vector3(.075,.8,.075),"566f64","wood")
	for y in [.9,1.19]:KIT.block(chair,Vector3(0,y,-.32),Vector3(.61,.18,.06),"92a399","wood")
	# Ground contact remains visible in the brighter setting.
	KIT.block(root,Vector3(0,.054,.13),Vector3(.64,.008,.63),"929f98","stone")
	return root
static func boundary(parent: Node3D,observed=false):
	var root=Node3D.new();root.name="BoundaryHall";parent.add_child(root)
	KIT.block(root,Vector3(0,-.09,-.7),Vector3(8.4,.16,7.0),"737d76","stone")
	for side in [-1,1]:
		KIT.block(root,Vector3(side*2.5,.02,-.7),Vector3(.045,.025,6.5),"a1a793","stone")
		for z in [-3.6,-1.5]:
			KIT.block(root,Vector3(side*3.15,.10,z),Vector3(.85,.22,.85),"8c9486","stone")
			KIT.block(root,Vector3(side*3.15,1.25,z),Vector3(.48,2.3,.48),"8d968a","stone")
			KIT.block(root,Vector3(side*3.15,2.45,z),Vector3(.72,.16,.72),"b2b7a1","stone")
	KIT.block(root,Vector3(0,2.62,-3.6),Vector3(6.9,.20,.56),"a3ab98","stone")
	KIT.block(root,Vector3(0,.11,-3.6),Vector3(3.1,.40,1.0),"8f998d","stone")
	for i in range(5):
		var shift=.18 if observed and i==2 else 0.0
		KIT.block(root,Vector3(shift,.06*i,-1.6-.4*i),Vector3(3.1,.12,.44),"9bA18f","stone")
		KIT.block(root,Vector3(shift,.06*i+.066,-1.45-.4*i),Vector3(3.0,.012,.025),"c0bca3","stone")
	# Sparse seams, no force-field plane or visual navigation barrier.
	for x in [-1.6,0,1.6]:KIT.block(root,Vector3(x,.002,.35),Vector3(.018,.008,3.8),"65766f","stone")
	return root
