extends SceneTree

# Standalone headless/preview verification for Issue #12: MG02 (Sev) + MIRROR_COURT.
# Zero dependency on hot files (main.gd, hex_board.gd, shield_stage.gd, smoke.gd).
# Run: Godot_v4.7.2-stable_win64_console.exe --headless --path 原型/P06_首章 --script res://mirror_court_preview.gd

const Mg02Actor = preload("res://mg02_actor.gd")
const MirrorKit = preload("res://mirror_court_kit.gd")
const MirrorBoard = preload("res://mirror_court_board.gd")
const Profiles = preload("res://actor_profiles.gd")


func _initialize() -> void:
	_run.call_deferred()


func _run() -> void:
	var report := {
		"mode": "standalone_preview_headless",
		"viewport_target": [1280, 720],
		"board": MirrorBoard.BOARD_ID,
		"region": MirrorBoard.REGION_ID,
		"site": MirrorBoard.SITE_ID,
		"ok": false,
	}

	# 1. Verify MIRROR_COURT backdrop & 3D MultiMesh kit
	var art_path := MirrorBoard.field_art_path("RG03", "G")
	var tex := load(art_path) as Texture2D
	report["backdrop"] = {
		"path": art_path,
		"loaded": tex != null,
		"size": [tex.get_width(), tex.get_height()] if tex != null else [0, 0],
	}
	var kit_counts := {}
	for kind in ["mirror-shrine", "mirror-stele", "mirror-plinth", "mirror-dais", "mirror-lantern"]:
		var node := MirrorKit.piece(kind) as MultiMeshInstance3D
		kit_counts[kind] = node.multimesh.instance_count if (node != null and node.multimesh != null) else 0
		if node != null:
			node.free()
	report["kit_pieces"] = kit_counts
	report["terrain_cells"] = {
		"LOW_OBSTACLE": MirrorBoard.CELLS.LOW_OBSTACLE.size(),
		"HIGH_OBSTACLE": MirrorBoard.CELLS.HIGH_OBSTACLE.size(),
		"HIGH_GROUND": MirrorBoard.CELLS.HIGH_GROUND.size(),
	}

	# 2. Verify MG02_Board.glb assembly with Mg02Actor (extending bow_actor.gd)
	var stage := Node3D.new()
	root.add_child(stage)
	var mg02_scene := load(Mg02Actor.MG02_MODEL) as PackedScene
	var profile := Mg02Actor.profile_entry(Mg02Actor)
	var sev := Mg02Actor.new()
	stage.add_child(sev)
	var assembled := false
	if mg02_scene != null:
		var travel_lib := Mg02Actor.in_place_travel(mg02_scene, profile.clips.travel)
		assembled = sev.assemble_bow(mg02_scene, travel_lib, profile)

	var clips_found: Array[String] = []
	if assembled and sev.player != null:
		for name in sev.player.get_animation_list():
			clips_found.append(String(name))
		clips_found.sort()
		# Exercise MG02-A/B/C prepare, restore, cancel, release, hit, down in normal & reduced modes
		sev.snap(Vector3(0, 0, 0), 0.0, false, true)
		sev.apply_boss_event("prepare", "MG02-A:1", 0.5, false, false)
		sev.apply_boss_event("prepare", "MG02-A:2", 0.5, true, true)
		sev.apply_boss_event("cancel", "", 0.5, true, false)
		sev.apply_boss_event("release", "", 0.5, true, false)
		sev.apply_boss_event("hit", "", 0.5, true, false)
		sev.apply_boss_event("down", "", 0.5, true, false)

	var arrow_ok := sev.arrow_mesh != null
	report["mg02"] = {
		"model": Mg02Actor.MG02_MODEL,
		"scene_loaded": mg02_scene != null,
		"assembled_bow": assembled,
		"clips": clips_found,
		"arrow_mesh_ok": arrow_ok,
		"arrow_origin": [sev.arrow_origin().x, sev.arrow_origin().y, sev.arrow_origin().z] if assembled else [],
		"release_axis": [sev.release_axis().x, sev.release_axis().y] if assembled else [],
	}

	# 3. Verify companion guards (EN03, EN17) load cleanly alongside MG02
	var guards := {}
	for gid in ["EN03", "EN17"]:
		var gpath: String = Profiles.STANDARD[gid].model
		var gscene := load(gpath) as PackedScene
		guards[gid] = {"model": gpath, "loaded": gscene != null}
	report["guards"] = guards

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
		and arrow_ok
		and guards.EN03.loaded
		and guards.EN17.loaded
	)

	var out_path := ProjectSettings.globalize_path("res://evidence/issue12-mg02/godot_preview_verify.json")
	DirAccess.make_dir_recursive_absolute(out_path.get_base_dir())
	var f := FileAccess.open(out_path, FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(report, "\t"))
		f.close()
	print("MIRROR_COURT_PREVIEW_VERIFY ", JSON.stringify(report))
	quit(0 if report.ok else 1)
