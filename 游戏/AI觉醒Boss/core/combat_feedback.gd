extends Node3D
## Event-only cosmetic feedback. No state writes, timers or campaign RNG.
var enabled=true
var voices=[]
var streams={}
var played=0
var muted_events=0
func _ready():
	for name_value in ["bow","hit","shield","formed","down","windup"]:streams[name_value]=load("res://assets/audio028/"+name_value+".wav")
	for i in range(6):
		var voice=AudioStreamPlayer.new();voice.volume_db=-10;add_child(voice);voices.append(voice)
func stop():
	for voice in voices:voice.stream_paused=false;voice.stop();voice.stream=null
func set_enabled(value: bool):
	enabled=value
	if not enabled:stop()
func play_kind(kind: String):
	if not enabled:muted_events+=1;return
	for voice in voices:
		if not voice.playing:
			voice.stream_paused=false;voice.stream=streams.get(kind,streams.hit);voice.play();played+=1;return
	if kind in ["down","formed"] and not voices.is_empty():
		var voice=voices[0];voice.stop();voice.stream_paused=false;voice.stream=streams[kind];voice.play();played+=1
func _exit_tree():stop()
