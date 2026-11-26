extends SceneTree

## Headless standalone preview verifier for #14 DEMON + shared CITADEL_RING.
## Verifies DEMON_Board.glb (26+ clips, A/B/C/D + MIMIC normal/reduced + cancel/interrupt),
## EN04/EN17 3D guards, CitadelRingKit, CitadelRingBoard, and citadel_ring_ink.png.

const Demon = preload("res://demon_actor.gd")
const CitadelKit = preload("res://citadel_ring_kit.gd")
const CitadelBoard = preload("res://citadel_ring_board.gd")


func _init() -> void:
	var root := Node3D.new()
	get_root().add_child(root)

	var demon_scene := load(Demon.DEMON_MODEL) as PackedScene
	var profile: Dictionary = Demon.profile_entry(Demon)
	var demon := Demon.new()
	root.add_child(demon)
	var travel_lib := Demon.in_place_travel(demon_scene, str(profile.clips.travel)) if demon_scene != null else null
	var assembled: bool = demon_scene != null and demon.assemble_demon(demon_scene, travel_lib, profile)
	var clips: Array[String] = []
	if demon.player != null:
		for c in demon.player.get_animation_list():
			clips.append(str(c))
	clips.sort()

	var state_checks := {"normal": [], "reduced": []}
	for mode: String in ["normal", "reduced"]:
		var is_red: bool = mode == "reduced"
		for move_id: String in ["DEMON-A", "DEMON-B", "DEMON-C", "DEMON-D", "MIMIC-H08-A"]:
			demon.apply_boss_event("prepare", move_id, "preview:%s:%s" % [mode, move_id], 0.0, is_red, false)
			var prep_clip: String = str(demon.player.current_animation) if demon.player != null else ""
			if move_id == "DEMON-D":
				demon.apply_boss_event("cancel", move_id, "preview:%s:%s" % [mode, move_id], 0.0, is_red, false)
			else:
				demon.apply_boss_event("release", move_id, "preview:%s:%s" % [mode, move_id], 0.0, is_red, false)
			var end_clip: String = str(demon.player.current_animation) if demon.player != null else ""
			demon.apply_boss_event("rest", "", "", 0.0, is_red, false)
			state_checks[mode].append("%s:prep=%s,end=%s" % [move_id, prep_clip, end_clip])

	var en04_ok: bool = load("res://assets/enemies/EN04_Board.glb") != null
	var en17_ok: bool = load("res://assets/enemies/EN17_Board.glb") != null
	var bg_tex := load(CitadelBoard.FIELD_ART) as Texture2D

	var kit_pieces := {}
	for asset: String in CitadelKit.ASSETS:
		var node := CitadelKit.piece(asset)
		kit_pieces[asset] = node.get_child_count()
		node.queue_free()

	var ok: bool = assembled and clips.size() >= 26 and en04_ok and en17_ok and bg_tex != null
	var result := {
		"ok": ok,
		"mode": "standalone_preview_headless",
		"board": CitadelBoard.BOARD_ID,
		"viewport_target": [1280, 720],
		"demon": {
			"model": Demon.DEMON_MODEL,
			"scene_loaded": demon_scene != null,
			"assembled_demon": assembled,
			"clip_count": clips.size(),
			"clips": clips,
			"state_checks": state_checks,
		},
		"guards": {
			"EN04": {"model": "res://assets/enemies/EN04_Board.glb", "loaded": en04_ok},
			"EN17": {"model": "res://assets/enemies/EN17_Board.glb", "loaded": en17_ok},
		},
		"backdrop": {
			"path": CitadelBoard.FIELD_ART,
			"loaded": bg_tex != null,
			"size": [bg_tex.get_width(), bg_tex.get_height()] if bg_tex != null else [0, 0],
		},
		"kit_pieces": kit_pieces,
		"preview_layout": {
			"LOW_OBSTACLE": CitadelBoard.PREVIEW_CELLS["LOW_OBSTACLE"].size(),
			"HIGH_GROUND": CitadelBoard.PREVIEW_CELLS["HIGH_GROUND"].size(),
			"HIGH_OBSTACLE": CitadelBoard.PREVIEW_CELLS["HIGH_OBSTACLE"].size(),
		},
		"null_safe_checks": {
			"town_inactive": not CitadelBoard.is_active({"phase": "TOWN", "map": {"board_id": "CITADEL_RING"}}),
			"regroup_inactive": not CitadelBoard.is_active({"phase": "FINAL_REGROUP", "map": {"board_id": "CITADEL_RING"}}),
			"null_safe": not CitadelBoard.is_active(null),
			"battle_active": CitadelBoard.is_active({"phase": "BATTLE", "map": {"board_id": "CITADEL_RING"}}),
		},
	}
	print("CITADEL_RING_PREVIEW_VERIFY ", JSON.stringify(result))
	quit(0 if ok else 1)
