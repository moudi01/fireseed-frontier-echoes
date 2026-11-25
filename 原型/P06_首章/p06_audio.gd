extends Node

signal cue_played(cue: String)

const Synth = preload("res://p06_audio_synth.gd")
const BowVisual = preload("res://bow_actor.gd")
const CrossbowVisual = preload("res://crossbow_actor.gd")
const PROJECTILE_UNITS := {"S03": "arrow", "M03": "bolt", "EN20": "bolt", "EN22": "arrow", "H02": "arrow", "H04": "arrow"}
const PROJECTILE_MOVES := {"S03-A": "arrow", "M03-A": "bolt", "EN22-A": "arrow"}
const SPEAR_UNITS := ["M01", "EN17"]
const SPEAR_MOVES := ["M01-A", "EN17-A"]
const COMBAT_VOICES := 10
const UI_VOICES := 3
const EFFECT_DB := -13.0
const UI_DB := -17.0
const MUSIC_DB := -11.0
const SILENT_DB := -80.0
const FADE_SECONDS := 0.42

var _effects: Dictionary = {}
var _music: Dictionary = {}
var _combat_voices: Array[AudioStreamPlayer] = []
var _ui_voices: Array[AudioStreamPlayer] = []
var _music_voices: Array[AudioStreamPlayer] = []
var _music_gain := PackedFloat32Array([0.0, 0.0])
var _generation := Thread.new()
var _requested_scene := ""
var _music_scene := ""
var _music_index := -1
var _level_db := 0.0
var _music_allowed := false
var _effects_allowed := false
var _focused := false
var _seen_battle := ""
var _seen_combat_tick := -1
var _seen_events: Dictionary = {}
var _batch: Dictionary = {}
var _scheduled: Array[Dictionary] = []


func _ready() -> void:
	for name: String in Synth.EFFECTS:
		_effects[name] = Synth.stream(Synth.effect_bytes(name), Synth.EFFECT_RATE)
	for index in range(COMBAT_VOICES):
		_combat_voices.append(_voice())
	for index in range(UI_VOICES):
		_ui_voices.append(_voice())
	for index in range(2):
		_music_voices.append(_voice())
	if _generation.start(Synth.music_bytes) != OK:
		_install_music(Synth.music_bytes())


func _exit_tree() -> void:
	if _generation.is_started():
		_generation.wait_to_finish()


func _voice() -> AudioStreamPlayer:
	var voice := AudioStreamPlayer.new()
	voice.volume_db = SILENT_DB
	add_child(voice)
	return voice


func configure(volume: int, music: bool, effects: bool, muted: bool, focused: bool) -> void:
	_focused = focused
	_level_db = linear_to_db(maxf(float(volume) / 100.0, 0.0001))
	_music_allowed = volume > 0 and music and not muted
	_effects_allowed = volume > 0 and effects and not muted
	if not _effects_allowed or not _focused:
		_batch.clear()
		_scheduled.clear()
		for voice in _combat_voices + _ui_voices:
			voice.stop()
	for voice in _combat_voices:
		voice.volume_db = EFFECT_DB + _level_db
	for voice in _ui_voices:
		voice.volume_db = UI_DB + _level_db
	_update_music_levels()


func scene(name: String) -> void:
	_requested_scene = name
	_start_music_scene()


func _install_music(clips: Dictionary) -> void:
	for name: String in clips:
		_music[name] = Synth.stream(clips[name], Synth.MUSIC_RATE, true)
	_start_music_scene()


func _start_music_scene() -> void:
	if _music.is_empty() or _music_scene == _requested_scene:
		return
	_music_scene = _requested_scene
	if _music_scene.is_empty():
		_music_index = -1
		return
	if _music_index == -1:
		_music_index = 0 if _music_gain[0] <= _music_gain[1] else 1
	else:
		_music_index = 1 - _music_index
	var voice := _music_voices[_music_index]
	voice.stop()
	voice.stream = _music[_music_scene]
	_music_gain[_music_index] = 0.0
	voice.volume_db = SILENT_DB
	voice.play()
	_update_music_levels()


func _update_music_levels() -> void:
	for index in range(_music_voices.size()):
		var voice := _music_voices[index]
		voice.stream_paused = not (_music_allowed and _focused)
		voice.volume_db = MUSIC_DB + _level_db + linear_to_db(maxf(_music_gain[index], 0.0001))


func _process(delta: float) -> void:
	if _generation.is_started() and not _generation.is_alive():
		_install_music(_generation.wait_to_finish())
	if _music_allowed and _focused:
		for index in range(_music_voices.size()):
			var voice := _music_voices[index]
			if not voice.playing:
				continue
			var target := 1.0 if index == _music_index else 0.0
			if _music_gain[index] != target:
				_music_gain[index] = move_toward(_music_gain[index], target, delta / FADE_SECONDS)
				voice.volume_db = MUSIC_DB + _level_db + linear_to_db(maxf(_music_gain[index], 0.0001))
			if _music_gain[index] == 0.0 and target == 0.0:
				voice.stop()
	if _scheduled.is_empty():
		return
	var now := Time.get_ticks_msec()
	var waiting: Array[Dictionary] = []
	for entry in _scheduled:
		if now >= int(entry.due):
			_play(entry.cue, _combat_voices)
		else:
			waiting.append(entry)
	_scheduled = waiting


func ui(cue: String) -> void:
	_play(cue, _ui_voices)


func _play(cue: String, voices: Array[AudioStreamPlayer]) -> void:
	if not _effects_allowed or not _focused:
		return
	# Active attacks and high-priority existing warning voices never get replaced.
	for voice in voices:
		if not voice.playing:
			voice.stream = _effects[cue]
			voice.play()
			cue_played.emit(cue)
			return


func observe_battle(battle: Variant, fresh_commit: bool, reduced_motion: bool) -> void:
	_batch.clear()
	if not battle is Dictionary:
		_seen_battle = ""
		_seen_events.clear()
		return
	var tick := int(battle.tick)
	if battle.id != _seen_battle or tick != _seen_combat_tick:
		_seen_battle = battle.id
		_seen_combat_tick = tick
		_seen_events.clear()
	var actors: Dictionary = {}
	for actor: Dictionary in battle.actors:
		actors[actor.id] = actor
	var contacts: Dictionary = {}
	for event: Dictionary in battle.events:
		var id: String = event.get("event_id", "")
		if id.is_empty() or _seen_events.has(id):
			continue
		_seen_events[id] = true
		if fresh_commit and _effects_allowed and _focused:
			_route_event(event, actors, contacts)
	if reduced_motion:
		for cue: String in _batch:
			_batch[cue] = mini(_batch[cue], 36)


func _projectile_release_ms(actor: String, basic: bool) -> int:
	if actor == "S03" and basic:
		return roundi(1000.0 * (BowVisual.BASIC_RELEASE - BowVisual.BASIC_START) / BowVisual.SHOT_SPEED)
	if actor == "M03":
		var release_time: float = CrossbowVisual.BASIC_RELEASE_TIME - 0.50 if basic else CrossbowVisual.BREACH_RELEASE_TIME
		return roundi(1000.0 * release_time / CrossbowVisual.BOLT_RECOVERY_SPEED)
	return 0


func _contact_ms(source: Dictionary, target: Dictionary, ranged: bool, basic: bool) -> int:
	if not ranged or source.is_empty() or target.is_empty():
		return 85
	var q: int = int(source.pos[0]) - int(target.pos[0])
	var r: int = int(source.pos[1]) - int(target.pos[1])
	var steps := maxi(maxi(absi(q), absi(r)), absi(q + r))
	return _projectile_release_ms(source.kind, basic) + clampi(steps * 40, 60, 200)


func _route_event(event: Dictionary, actors: Dictionary, contacts: Dictionary) -> void:
	var source: Dictionary = actors.get(event.get("actor", ""), {})
	var actor: String = source.get("kind", "")
	var projectile: String = PROJECTILE_UNITS.get(actor, "")
	match event.type:
		"basic_start":
			if not projectile.is_empty():
				_batch[projectile] = _projectile_release_ms(actor, true)
			elif actor in SPEAR_UNITS:
				_batch["stab"] = 0
			elif not actor.is_empty() and actor not in ["M02", "M04"]:
				_batch["slash"] = 0
		"release":
			var move: String = event.get("move", "")
			if PROJECTILE_MOVES.has(move):
				_batch[PROJECTILE_MOVES[move]] = _projectile_release_ms(actor, false)
			elif move in SPEAR_MOVES:
				_batch["stab"] = 0
			elif move == "S02-A":
				_batch["slash"] = 0
		"guard_redirect":
			var attacker: Dictionary = actors.get(event.get("attacker", ""), {})
			var action: String = event.get("move", "")
			var ranged := PROJECTILE_MOVES.has(action) or (action == "BASIC" and PROJECTILE_UNITS.has(attacker.get("kind", "")))
			_batch["guard"] = _contact_ms(attacker, source, ranged, action == "BASIC")
		"hit":
			if int(event.get("actual_hp_damage", 0)) <= 0 and int(event.get("absorbed", 0)) <= 0:
				return
			var action: String = event.get("action", "")
			var ranged := PROJECTILE_MOVES.has(action) or (action == "BASIC" and not projectile.is_empty())
			var lag := _contact_ms(source, actors.get(event.target, {}), ranged, action == "BASIC")
			contacts[event.target] = lag
			if event.get("front_guard", false):
				_batch["guard"] = lag
			elif ranged:
				_batch["arrow_hit"] = lag
			elif int(event.get("actual_hp_damage", 0)) > 0:
				_batch["hit"] = lag
		"down":
			_batch["down"] = int(contacts.get(event.actor, 85)) + 36
		"heal":
			if int(event.get("effective", 0)) > 0:
				_batch["heal"] = 95


func flush_combat() -> void:
	# Coalesce identical cues within a saved beat but keep different feedback audible.
	var now := Time.get_ticks_msec()
	for cue: String in _batch:
		_scheduled.append({"cue": cue, "due": now + int(_batch[cue])})
	_batch.clear()
