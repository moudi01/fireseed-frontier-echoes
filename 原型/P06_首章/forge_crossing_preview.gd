extends SceneTree

# Standalone headless verification for Issue #13: MG04 (Helan) + FORGE_CROSSING (RG05/G).
# Zero dependency on hot files (main.gd, hex_board.gd, shield_stage.gd, actor_profiles.gd, smoke.gd).
# Run: Godot_v4.7.2-stable_win64_console.exe --headless --path 原型/P06_首章 --script res://forge_crossing_preview.gd

const Mg04Actor = preload("res://mg04_actor.gd")
const ForgeKit = preload("res://forge_crossing_kit.gd")
const ForgeBoard = preload("res://forge_crossing_board.gd")


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var report := {
		"mode": "standalone_preview_headless",
		"viewport_target": [1280, 720],
		"board": ForgeBoard.BOARD_ID,
		"region": ForgeBoard.REGION_ID,
		"site": ForgeBoard.SITE_ID,
		"ok": false,
	}

	# 1. Verify FORGE_CROSSING backdrop & 3D MultiMesh kit
	var art_path := ForgeBoard.field_art_path("RG05", "G")
	var tex := load(art_path) as Texture2D
	report["backdrop"] = {
		"path": art_path,
		"loaded": tex != null,
		"size": [tex.get_width(), tex.get_height()] if tex != null else [0, 0],
	}
	var kit_counts := {}
	for kind in ["forge-pillar", "forge-anvil", "forge-gantry", "forge-anchor"]:
		var node := ForgeKit.piece(kind) as MultiMeshInstance3D
		kit_counts[kind] = node.multimesh.instance_count if (node != null and node.multimesh != null) else 0
		if node != null:
			node.free()
	report["kit_pieces"] = kit_counts
	report["preview_layout"] = {
		"HIGH_OBSTACLE": ForgeBoard.PREVIEW_CELLS.HIGH_OBSTACLE.size(),
		"HIGH_GROUND": ForgeBoard.PREVIEW_CELLS.HIGH_GROUND.size(),
		"LOW_OBSTACLE": ForgeBoard.PREVIEW_CELLS.LOW_OBSTACLE.size(),
		"ANCHORS": ForgeBoard.PREVIEW_ANCHORS.size(),
	}

	# 2. Verify MG04_Board.glb assembly with Mg04Actor (all 18 clips + Hammer + normal/reduced_motion)
	var stage := Node3D.new()
	root.add_child(stage)
	var mg04_scene := load(Mg04Actor.MG04_MODEL) as PackedScene
	var profile := Mg04Actor.profile_entry(Mg04Actor)
	var helan := Mg04Actor.new()
	stage.add_child(helan)
	var assembled := false
	if mg04_scene != null:
		var travel_lib := Mg04Actor.in_place_travel(mg04_scene, profile.clips.travel)
		assembled = helan.assemble_mg04(mg04_scene, travel_lib, profile)

	var clips_found: Array[String] = []
	var state_checks := {}
	if assembled and helan.player != null:
		for name in helan.player.get_animation_list():
			clips_found.append(String(name))
		clips_found.sort()
		helan.snap(Vector3.ZERO, 0.0, false, true)
		for reduced in [false, true]:
			var mode_key := "reduced" if reduced else "normal"
			var seq: Array[String] = []
			for mv in Mg04Actor.MG04_MOVES:
				helan.apply_boss_event("prepare", mv, mv + ":1:" + mode_key, 0.3, reduced, false)
				seq.append(mv + ":prep=" + str(helan.player.current_animation))
				helan.apply_boss_event("prepare", mv, mv + ":restore:" + mode_key, 0.3, reduced, true)
				seq.append(mv + ":rest=" + str(helan.player.current_animation))
				helan.apply_boss_event("cancel", mv, "", 0.3, reduced, false)
				helan.apply_boss_event("release", mv, "", 0.3, reduced, false)
			helan.apply_boss_event("attack", "", "", 0.3, reduced, false)
			helan.apply_boss_event("hit", "", "", 0.3, reduced, false)
			helan.apply_boss_event("down", "", "", 0.3, reduced, false)
			helan.snap(Vector3.ZERO, 0.0, false, true)
			state_checks[mode_key] = seq

	var hammer_ok := helan.find_child("MG04_Hammer", true, false) != null

	report["mg04"] = {
		"model": Mg04Actor.MG04_MODEL,
		"scene_loaded": mg04_scene != null,
		"assembled_mg04": assembled,
		"hammer_node_ok": hammer_ok,
		"clip_count": clips_found.size(),
		"clips": clips_found,
		"state_checks": state_checks,
	}

	# 3. Verify BOTH 3D guards (EN04, EN17) load cleanly alongside MG04
	var en04_scene := load("res://assets/enemies/EN04_Board.glb") as PackedScene
	var en17_scene := load("res://assets/enemies/EN17_Board.glb") as PackedScene
	report["guards"] = {
		"EN04": {"model": "res://assets/enemies/EN04_Board.glb", "loaded": en04_scene != null},
		"EN17": {"model": "res://assets/enemies/EN17_Board.glb", "loaded": en17_scene != null},
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
		and hammer_ok
		and clips_found.size() >= 18
		and en04_scene != null
		and en17_scene != null
	)

	var out_path := ProjectSettings.globalize_path("res://evidence/issue13-mg04/godot_preview_verify.json")
	DirAccess.make_dir_recursive_absolute(out_path.get_base_dir())
	var f := FileAccess.open(out_path, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(report, "\t"))
		f.close()
	print("FORGE_CROSSING_PREVIEW_VERIFY ", JSON.stringify(report))
	quit(0 if report.ok else 1)
