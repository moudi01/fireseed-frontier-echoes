extends RefCounted
## Derive cosmetic deadlines from the existing schedule without changing any item.
## A root reaches its confirmed cell before its earliest outgoing or incoming cue.
static func window(id:int,unit_type:String,pending:Array,age:float=0.0)->Dictionary:
	var outgoing=-1.0;var incoming=-1.0
	for item in pending:
		var at=float(item.get("at",-1.0))
		if not is_finite(at) or at<0.0 or at>.5:continue
		var event:Dictionary=item.get("event",{});var kind=str(item.get("kind",""))
		if int(event.get("actor",-1))==id and (kind in ["release","ground"] or (kind=="impact" and unit_type!="archer")):
			outgoing=at if outgoing<0 else minf(outgoing,at)
		if int(event.get("target",-1))==id and kind=="impact":incoming=at if incoming<0 else minf(incoming,at)
	var settle=outgoing
	if incoming>=0:settle=incoming if settle<0 else minf(settle,incoming)
	return {"outgoing_at":outgoing,"incoming_at":incoming,
		"turn_deadline":maxf(.001,outgoing-age) if outgoing>=age and outgoing>=0 else -1.0,
		"motion_deadline":maxf(.001,settle-age) if settle>=age and settle>=0 else -1.0}

static func shorten_motion(figure:Dictionary,deadline:float)->bool:
	if deadline<=0 or not is_finite(deadline) or float(figure.get("motion",1.0))>=1.0:return false
	var remaining=(1.0-float(figure.motion))*float(figure.get("motion_duration",.5))
	if remaining<=deadline+.000001:return false
	# Rebase at the displayed root: no position jump, including interrupted travel.
	figure.motion_from=figure.node.position;figure.motion=0.0;figure.motion_duration=maxf(.001,deadline)
	return true
