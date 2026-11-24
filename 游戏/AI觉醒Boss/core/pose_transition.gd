extends SkeletonModifier3D
## Short neutral-pose settling. Skill clips, rule clocks and world roots remain authoritative.
const DURATION=.10
var figure={}
var enabled=true
var valid=false
var last=[]
var source=[]
var age=0.0
var duration=DURATION
var latest={"weight":1.0,"applied":false}
func configure(f:Dictionary):
 figure=f;valid=f.model.get_meta("action_issues",["unchecked"]).is_empty() and get_skeleton().get_bone_count()==24
func reset():
 source=[];age=0.0;latest={"weight":1.0,"applied":false}
func begin(allowed:bool):
 reset()
 if allowed and enabled and valid and last.size()==get_skeleton().get_bone_count():source=last.duplicate();duration=DURATION
func advance(seconds:float):
 if source.is_empty():return
 age=minf(duration,age+maxf(0,seconds))
 if age>=duration:source=[]
func _process_modification_with_delta(_delta:float):
 latest={"weight":1.0,"applied":false}
 if not enabled or not valid or source.is_empty():return
 var sk=get_skeleton();var t=smoothstep(0,duration,age)
 for i in range(source.size()):sk.set_bone_pose(i,source[i].interpolate_with(sk.get_bone_pose(i),t))
 latest={"weight":t,"applied":true}
func remember():
 if not valid or not figure.node.is_visible_in_tree():return
 last=[];var sk=get_skeleton()
 for i in range(sk.get_bone_count()):last.append(sk.get_bone_pose(i))
static func is_neutral(clip:String,action:Dictionary,unit:Dictionary):
 return clip in ["Idle","BowReady","Armature|walking_man|baselayer","ShieldWalk"] or (clip=="ShieldWall" and action.hold and not unit.get("is_winding",false) and unit.get("charge_ticks_left",0)==0)
