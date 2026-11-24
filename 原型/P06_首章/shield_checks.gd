extends Node

const Actor = preload("res://shield_actor.gd")

var stage: Control


func verify(app: Control) -> String:
	var path := ""
	for token in OS.get_cmdline_user_args():
		if token.begins_with("--fixtures="):
			path = token.trim_prefix("--fixtures=")
	var source: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not source is Dictionary or source.get("verified_files") != 87:
		return "Frozen event fixtures are unavailable"
	stage = app.board.stage
	await get_tree().process_frame
	var center: Vector2 = stage.size / 2.0
	stage.set_geometry({
		Vector2i(3, 2): center + Vector2(0, 75), Vector2i(3, 3): center + Vector2(0, 25),
		Vector2i(3, 4): center + Vector2(0, -25), Vector2i(3, 5): center + Vector2(0, -75),
	}, 34.0)
	var clips: Dictionary = stage.audit.clips
	var chain: Dictionary = source.cases.s01_move_basic_target_down
	var frame := _frame("move", [3, 2], [3, 5])
	stage.apply(frame, true)
	if not stage.actors.has("P"):
		return "No imported shield instance"
	var pawn = stage.actors.P.node
	for tick in [1, 2, 3]:
		frame.events = chain.events.filter(func(event: Dictionary) -> bool: return int(event.tick) == tick)
		frame.tick = tick
		frame.actors[0].pos = [3, 2 + mini(2, tick)]
		stage.apply(frame, false)
		var consumed: int = stage.audit.events
		stage.apply(frame, false)
		if stage.audit.events != consumed:
			return "A repeated snapshot replayed battle events"
		if tick == 1:
			stage.set_paused(true)
			var held: Vector3 = pawn.position
			await get_tree().create_timer(0.17).timeout
			if held.distance_to(pawn.position) > 0.002:
				return "Settings failed to pause the moving shield"
			stage.set_paused(false)
		await get_tree().create_timer(0.52).timeout
	var expected: Vector3 = stage._world(stage._at([3, 4]))
	if pawn.position.distance_to(expected) > 0.002 or clips.get(Actor.MOVE, 0) != 2 or clips.get(Actor.STOP, 0) != 2 or clips.get(Actor.ATTACK, 0) != 1 or stage.audit.contacts != 1:
		return "Move/stop/attack failed to reach the authoritative cell or contact"
	for branch in ["front_guard", "absorbed", "direct_hit", "down"]:
		var record: Dictionary = source.cases["s01_" + branch]
		var feedback := _frame(branch, [3, 2], [3, 3])
		stage.apply(feedback, true)
		feedback.events = record.events.duplicate(true)
		feedback.actors[0].hp = record.result_hp
		for event in feedback.events:
			if event.type == "hit":
				event["front_guard"] = branch == "front_guard"
		stage.apply(feedback, false)
		await get_tree().create_timer(0.64 if branch != "down" else 1.57).timeout
		if branch == "down":
			pawn = stage.actors.P.node
			if not pawn.fallen or pawn.player.current_animation_position < 1.4:
				return "Lethal hit failed to hold its down pose"
			var count: int = clips.get(Actor.DOWN, 0)
			stage.clear_battle()
			stage.apply(feedback, true)
			if not stage.actors.P.node.fallen or clips.get(Actor.DOWN, 0) != count or stage.actors.P.node.player.current_animation_position < 1.4:
				return "Resumed down pose replayed a past event"
	if clips.get(Actor.BLOCK, 0) != 1 or clips.get(Actor.HIT, 0) != 1 or clips.get(Actor.DOWN, 0) != 1 or stage.audit.absorptions != 1:
		return "Block, absorption, damage or lethal hit were conflated"
	stage.clear_battle()
	return ""


func _frame(id: String, player: Array, enemy: Array) -> Dictionary:
	return {"id": id, "tick": 0, "actors": [
		{"id": "P", "kind": "S01", "side": "player", "pos": player, "hp": 250, "facing": 1},
		{"id": "Target", "kind": "EN01", "side": "enemy", "pos": enemy, "hp": 250, "facing": 4},
	], "events": []}
