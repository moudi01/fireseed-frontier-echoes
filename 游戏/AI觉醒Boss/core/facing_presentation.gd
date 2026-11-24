extends RefCounted
## Cosmetic shortest-arc turns. Visual time only; no position, event or rule updates.
const MOVE_RATE=deg_to_rad(540.0)
const ATTACK_RATE=deg_to_rad(1080.0)
static func target(figure: Dictionary,angle: float,snap=false,dead=false,attack=false,contact_deadline=-1.0):
	var current=float(figure.node.rotation.y)
	if dead:angle=current
	angle=wrapf(angle,-PI,PI);figure.facing=angle
	if snap or dead:
		figure.node.rotation.y=angle;figure.turn_from=angle;figure.turn_to=angle;figure.turn_age=0.0;figure.turn_duration=0.0;figure.turn_active=false;return
	var same=absf(wrapf(angle-float(figure.get("turn_to",current)),-PI,PI))<.00001
	var remaining=float(figure.get("turn_duration",0))-float(figure.get("turn_age",0))
	var bounded=is_finite(float(contact_deadline)) and float(contact_deadline)>0
	var urgent=bounded and figure.get("turn_active",false) and remaining>float(contact_deadline)+.000001
	if same and not urgent and not (attack and figure.get("turn_active",false) and remaining>.17):return
	var delta=wrapf(angle-current,-PI,PI)
	if absf(delta)<.002:
		figure.node.rotation.y=angle;figure.turn_active=false;return
	figure.turn_from=current;figure.turn_to=current+delta;figure.turn_age=0.0
	figure.turn_duration=maxf(.06,absf(delta)/(ATTACK_RATE if attack else MOVE_RATE))
	# The unmodified contact/release schedule is the deadline, not a new rule tick.
	if bounded:figure.turn_duration=minf(figure.turn_duration,maxf(.001,float(contact_deadline)))
	figure.turn_active=true
static func advance(figure: Dictionary,delta: float):
	if not figure.get("turn_active",false):return
	figure.turn_age=minf(float(figure.turn_duration),float(figure.turn_age)+delta)
	figure.node.rotation.y=lerpf(float(figure.turn_from),float(figure.turn_to),smoothstep(0,float(figure.turn_duration),float(figure.turn_age)))
	if figure.turn_age>=figure.turn_duration:
		figure.node.rotation.y=wrapf(float(figure.turn_to),-PI,PI);figure.turn_active=false
