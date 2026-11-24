extends RefCounted
## Cosmetic schedule only. The caller retains the authoritative tick snapshot.
## Times use visual seconds; the caller applies pause and speed before advance().
const MELEE_CONTACT = 0.18
const MAX_RELEASE = 0.24
var age = 0.0
var last_tick = -1
var pending = []
var active = false
var death_times = {}
var trace = []
var enabled = true

func clear() -> void:
	age = 0.0
	last_tick = -1
	pending.clear()
	active = false
	death_times.clear()
	trace.clear()

func _discard(tick: int) -> void:
	age = 0.0
	last_tick = tick
	pending.clear()
	active = false
	death_times.clear()

func set_enabled(value: bool) -> void:
	enabled = value
	if not enabled:
		_discard(last_tick)

func _unit(source: Dictionary, id: int) -> Dictionary:
	return source.get(id, source.get(str(id), {}))

func _melee_at(figures:Dictionary,id:int)->float:
	var at=float(_unit(figures,id).get("melee_contact_at",MELEE_CONTACT))
	return at if is_finite(at) and at>=.03 and at<=.42 else MELEE_CONTACT

func _add(kind: String, event: Dictionary, at: float, index: int) -> void:
	var key = "%d:%d:%s" % [last_tick, index, kind]
	var item = {"kind": kind, "event": event.duplicate(true), "at": at,
		"key": key, "tick": last_tick, "order": pending.size()}
	pending.append(item)
	trace.append({"action": "queued", "kind": kind, "key": key,
		"at": at, "tick": last_tick})

func queue_tick(tick: int, events: Array, current: Dictionary, previous: Dictionary,
		figures: Dictionary, snap: bool = false) -> void:
	# A restored/stepped snapshot is final presentation, never an invented replay.
	if snap or not enabled:
		_discard(tick)
		return
	if tick == last_tick:
		return
	var continuous = last_tick >= 0 and tick == last_tick + 1
	_discard(tick)
	if not continuous:
		return
	for index in range(events.size()):
		var event = events[index]
		if not event is Dictionary:
			continue
		var action = str(event.get("action", ""))
		var actor = int(event.get("actor", -1))
		# Current-tick deaths may still have attacked simultaneously. An actor or
		# victim already dead in the preceding snapshot cannot produce a new hit.
		if not _unit(previous, actor).get("alive", true):
			continue
		if action == "cancelled":
			var cell = event.get("target_cell", [])
			if event.get("attack_type", "") == "charged_strike" and cell is Array and cell.size() == 2:
				_add("ground", event, _melee_at(figures,actor), index)
			continue
		if action != "attack":
			continue
		if not _unit(previous, int(event.get("target", -1))).get("alive", true):
			continue
		var actor_unit = _unit(current, actor)
		if actor_unit.is_empty():
			actor_unit = _unit(previous, actor)
		if actor_unit.get("unit_type", "") == "archer":
			var figure = _unit(figures, actor)
			var rate = maxf(0.001, float(figure.get("clip_rate", 1.0)))
			# .03 is this model's local BowRelease arrow-detachment frame.
			# The bound prevents malformed rates from spilling past the next tick.
			var release = clampf(0.03 / rate, 0.0, MAX_RELEASE)
			var origin = event.get("actor_pos", actor_unit.get("position", []))
			var target = event.get("target_pos", _unit(current, int(event.get("target", -1))).get("position", []))
			var distance = 0.0
			if origin is Array and target is Array and origin.size() == 2 and target.size() == 2:
				distance = Vector2(float(origin[0]), float(origin[1])).distance_to(Vector2(float(target[0]), float(target[1])))
			var flight = clampf(0.12 + distance * 0.02, 0.12, 0.20)
			_add("release", event, release, index)
			_add("impact", event, release + flight, index)
		else:
			_add("impact", event, _melee_at(figures,actor), index)
	# Same-time contacts retain source-event order; no RNG or target arbitration.
	pending.sort_custom(func(a, b):
		return a.order < b.order if float(a.at) == float(b.at) else a.at < b.at)
	for raw_id in current:
		var id = int(raw_id)
		var old = _unit(previous, id)
		if old.is_empty() or not old.get("alive", true) or _unit(current, id).get("alive", true):
			continue
		var until = 0.0
		for item in pending:
			var event = item.event
			var incoming = item.kind == "impact" and int(event.get("target", -1)) == id
			var own_release = int(event.get("actor", -1)) == id and (item.kind in ["release", "ground"] or (item.kind == "impact" and _unit(current, id).get("unit_type", "") != "archer"))
			if incoming or own_release:
				until = maxf(until, float(item.at))
		death_times[id] = until
	active = not pending.is_empty()

func advance(seconds: float) -> Array:
	var due = []
	if not enabled:
		return due
	age += maxf(0.0, seconds)
	while not pending.is_empty() and float(pending[0].at) <= age + 0.000001:
		var item = pending.pop_front()
		item.erase("order")
		due.append(item)
		trace.append({"action": "dispatched", "kind": item.kind, "key": item.key,
			"at": item.at, "tick": item.tick})
	active = not pending.is_empty()
	return due
