extends SceneTree

# Standalone headless verification for Issue #13: MG03 (Yilei) + SALT_CROSSING (RG04).
# Zero dependency on hot files (main.gd, hex_board.gd, shield_stage.gd, actor_profiles.gd, smoke.gd).
# Run: Godot_v4.7.2-stable_win64_console.exe --headless --path 原型/P06_首章 --script res://salt_crossing_preview.gd

const Mg03Actor = preload("res://mg03_actor.gd")
const SaltKit = preload("res://salt_crossing_kit.gd")
const SaltBoard = preload("res://salt_crossing_board.gd")


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var report := {
		"mode": "standalone_preview_headless",
		"viewport_target": [1280, 720],
		"board": SaltBoard.BOARD_ID,
		"region": SaltBoard.REGION_ID,
		"site": SaltBoard.SITE_ID,
		"ok": false,
	}

	# 1. Verify SALT_CROSSING backdrop & 3D MultiMesh kit
	var art_path := SaltBoard.field_art_path("RG04", "G")
	var tex := load(art_path) as Texture2D
	report["backdrop"] = {
		"path": art_path,
		"loaded": tex != null,
		"size": [tex.get_width(), tex.get_height()] if tex != null else [0, 0],
	}
	var kit_counts := {}
	for kind in ["salt-bollard", "salt-dais", "salt-pier", "salt-bell-post"]:
		var node := SaltKit.piece(kind) as MultiMeshInstance3D
		kit_counts[kind] = node.multimesh.instance_count if (node != null and node.multimesh != null) else 0
		if node != null:
			node.free()
	report["kit_pieces"] = kit_counts
	report["terrain_cells"] = {
		"HIGH_GROUND": SaltBoard.CELLS.HIGH_GROUND.size(),
		"SHALLOW_WATER": SaltBoard.CELLS.SHALLOW_WATER.size(),
		"LOW_OBSTACLE": SaltBoard.CELLS.LOW_OBSTACLE.size(),
	}

	# 2. Verify MG03_Board.glb assembly with Mg03Actor (all 18 clips + Needle & Ledger + normal/reduced_motion)
	var stage := Node3D.new()
	root.add_child(stage)
	var mg03_scene := load(Mg03Actor.MG03_MODEL) as PackedScene
	var profile := Mg03Actor.profile_entry(Mg03Actor)
	var yilei := Mg03Actor.new()
	stage.add_child(yilei)
	var assembled := false
	if mg03_scene != null:
		var travel_lib := Mg03Actor.in_place_travel(mg03_scene, profile.clips.travel)
		assembled = yilei.assemble_mg03(mg03_scene, travel_lib, profile)

	var clips_found: Array[String] = []
	var state_checks := {}
	if assembled and yilei.player != null:
		for name in yilei.player.get_animation_list():
			clips_found.append(String(name))
		clips_found.sort()
		yilei.snap(Vector3.ZERO, 0.0, false, true)
		for reduced in [false, true]:
			var mode_key := "reduced" if reduced else "normal"
			var seq: Array[String] = []
			for mv in Mg03Actor.MG03_MOVES:
				yilei.apply_boss_event("prepare", mv, mv + ":1:" + mode_key, 0.3, reduced, false)
				seq.append(mv + ":prep=" + str(yilei.player.current_animation))
				yilei.apply_boss_event("prepare", mv, mv + ":restore:" + mode_key, 0.3, reduced, true)
				seq.append(mv + ":rest=" + str(yilei.player.current_animation))
				yilei.apply_boss_event("cancel", mv, "", 0.3, reduced, false)
				yilei.apply_boss_event("release", mv, "", 0.3, reduced, false)
			yilei.apply_boss_event("attack", "", "", 0.3, reduced, false)
			yilei.apply_boss_event("hit", "", "", 0.3, reduced, false)
			yilei.apply_boss_event("down", "", "", 0.3, reduced, false)
			yilei.snap(Vector3.ZERO, 0.0, false, true)
			state_checks[mode_key] = seq

	var needle_ok := yilei.find_child("MG03_Needle", true, false) != null
	var ledger_ok := yilei.find_child("MG03_Ledger", true, false) != null

	report["mg03"] = {
		"model": Mg03Actor.MG03_MODEL,
		"scene_loaded": mg03_scene != null,
		"assembled_mg03": assembled,
		"needle_node_ok": needle_ok,
		"ledger_node_ok": ledger_ok,
		"clip_count": clips_found.size(),
		"clips": clips_found,
		"state_checks": state_checks,
	}

	# 3. Verify EN06 guard model loads cleanly alongside MG03 (EN15 has no 3D model yet -> 2D marker fallback)
	var en06_scene := load("res://assets/enemies/EN06_Runtime.glb") as PackedScene
	report["guards"] = {
		"EN06": {"model": "res://assets/enemies/EN06_Runtime.glb", "loaded": en06_scene != null},
		"EN15": {"model": null, "fallback": "2d_marker"},
	}

	stage.queue_free()
	await process_frame

	var all_kit_ok := true
	for k in kit_counts:
		if int(kit_counts[k]) <= 0:
			all_kit_ok = false
	report["ok"] = (
		report.backdrop.loaded
		and all_kit_ok
		and assembled
		and needle_ok
		and ledger_ok
		and clips_found.size() >= 18
		and en06_scene != null
	)

	var out_path := ProjectSettings.globalize_path("res://evidence/issue13-mg03/godot_preview_verify.json")
	DirAccess.make_dir_recursive_absolute(out_path.get_base_dir())
	var f := FileAccess.open(out_path, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(report, "\t"))
		f.close()
	print("SALT_CROSSING_PREVIEW_VERIFY ", JSON.stringify(report))
	quit(0 if report.ok else 1)
