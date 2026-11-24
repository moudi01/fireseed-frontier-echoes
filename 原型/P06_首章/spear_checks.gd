extends Node

const Spear = preload("res://spear_actor.gd")


func verify(app: Control) -> String:
	var path := ""
	for token in OS.get_cmdline_user_args():
		if token.begins_with("--fixtures="):
			path = token.trim_prefix("--fixtures=")
	var source: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not source is Dictionary or source.get("verified_files") != 87:
		return "Frozen spear evidence is unavailable"
	var stage = app.board.stage
	await get_tree().process_frame
	var center: Vector2 = stage.size / 2.0
	stage.set_geometry({
		Vector2i(3, 2): center + Vector2(0, 60), Vector2i(3, 3): center,
		Vector2i(3, 4): center - Vector2(0, 60), Vector2i(4, 3): center + Vector2(55, 0)
	}, 35.0)
	for branch in ["hit", "off_axis", "cancel"]:
		var record: Dictionary = source.cases["m01_" + branch]
		var start: Dictionary = record.events[0]
		var frame := _frame(branch)
		stage.apply(frame, true)
		frame["tick"] = start.tick
		frame["events"] = [start]
		stage.apply(frame, false)
		if not stage.actors.has("P"):
			return "Imported spear instance is missing"
		var pawn = stage.actors.P.node
		var origin: Vector3 = pawn.position
		await get_tree().create_timer(0.50).timeout
		if pawn.cast_id != start.action_id or pawn.player.current_animation != Spear.HOLD:
			return "Windup did not enter the locked hold: " + branch
		if branch == "hit":
			# Rebuild a live cast from the persisted pending state and cursor.
			frame.actors[0]["spear_pending"] = {"id": start.action_id, "cells": start.cells,
				"origin": [3, 2], "due": start.release_tick}
			stage.clear_battle()
			stage.apply(frame, true)
			pawn = stage.actors.P.node
			if pawn.cast_id != start.action_id or pawn.player.current_animation != Spear.HOLD:
				return "Pending cast was not restored into hold"
			frame.actors[0].erase("spear_pending")
		if branch == "off_axis":
			frame.actors[1].pos = [4, 3]
		frame["tick"] = start.release_tick
		frame["events"] = record.events.slice(1)
		stage.apply(frame, false)
		var resolved: int = stage.audit.events
		stage.apply(frame, false)
		if stage.audit.events != resolved or not pawn.cast_id.is_empty():
			return "Resolved cast replayed or remained locked"
		var clip := Spear.CANCEL if branch == "cancel" else Spear.THRUST
		if pawn.player.current_animation != clip or pawn.position.distance_to(origin) > 0.002:
			return "Wrong clip or root drift at resolution: " + branch
		if not stage.marks.is_empty():
			return "Spear feedback appeared before its contact frame"
		await get_tree().create_timer(0.47).timeout
		if branch == "hit":
			if not str(stage.marks.get("Target", {}).get("label", "")).ends_with("受阻"):
				return "Confirmed hit and blocked movement did not reach the target"
		elif branch == "off_axis":
			if stage.marks.get("P", {}).get("label") != "放空" or stage.marks.has("Target"):
				return "Offline target received false hit feedback"
		elif not stage.marks.is_empty():
			return "The cancelled cast produced contact feedback"
	var counts: Dictionary = stage.audit
	if counts.spear_windups != 3 or counts.spear_hits != 1 or counts.spear_misses != 1 or counts.spear_blocks != 1 or counts.spear_releases != 2 or counts.spear_cancels != 1:
		return "Unexpected spear branch counts"
	stage.clear_battle()
	return ""


func _frame(id: String) -> Dictionary:
	return {"id": id, "tick": 0, "actors": [
		{"id": "P", "kind": "M01", "side": "player", "pos": [3, 2], "hp": 250, "facing": 1},
		{"id": "Target", "kind": "EN01", "side": "enemy", "pos": [3, 4], "hp": 250, "facing": 4},
	], "events": []}
