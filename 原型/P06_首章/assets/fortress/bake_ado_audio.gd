extends SceneTree

const RATE := 24000
const LENGTHS := {"MG01-A": 0.27, "MG01-B": 0.34, "MG01-C": 0.31, "whistle": 0.39}
const OUTPUT := "res://assets/fortress/audio/"


func _initialize() -> void:
	for key: String in ["warning", "MG01-A", "MG01-B", "MG01-C", "whistle"]:
		var started := Time.get_ticks_usec()
		var stream := _warning() if key == "warning" else _cue(key)
		var generated_usec := Time.get_ticks_usec() - started
		var path := OUTPUT + key.to_lower() + ".wav"
		var status := stream.save_to_wav(path)
		if status != OK:
			push_error("Could not write %s: %s" % [path, error_string(status)])
			quit(1)
			return
		var hash := HashingContext.new()
		hash.start(HashingContext.HASH_SHA256)
		hash.update(stream.data)
		print("%s %d %s %d us" % [key, stream.data.size(), hash.finish().hex_encode(), generated_usec])
	quit()


static func _cue(key: String) -> AudioStreamWAV:
	var count := int(RATE * float(LENGTHS[key]))
	var samples := PackedByteArray()
	samples.resize(count * 2)
	var rng := RandomNumberGenerator.new()
	rng.seed = 20112026
	var rasp := 0.0
	for i in range(count):
		var t := float(i) / RATE
		rasp = lerpf(rasp, rng.randf_range(-1.0, 1.0), 0.26)
		var gain := clampf(minf(t / 0.007, (float(LENGTHS[key]) - t) / 0.045), 0.0, 1.0)
		var value := _sample(key, t, rasp) * gain
		samples.encode_s16(2 * i, int(clampf(value, -1.0, 1.0) * 12500))
	return _wave(samples)


static func _sample(key: String, time: float, noise: float) -> float:
	match key:
		"MG01-A":
			return exp(-11.5 * time) * (sin(TAU * (224.0 * time - 188.0 * time * time)) * 0.55
				+ sin(TAU * 517.0 * time) * 0.24 + noise * 0.71)
		"MG01-B":
			return exp(-9.4 * time) * (0.58 * sin(TAU * 124.0 * time) + 0.29 * sin(TAU * 213.0 * time)
				+ 0.13 * sin(TAU * 365.0 * time)) + noise * 0.52 * exp(-43.0 * time)
		"MG01-C":
			var note := time if time < 0.109 else time - 0.109
			var pitch := 378.0 if time < 0.109 else 327.0
			return clampf(note * 260.0, 0.0, 1.0) * exp(-19.0 * note) * (sin(TAU * pitch * note) * 0.62
				+ sin(TAU * (pitch * 1.51) * note) * 0.18 + noise * 0.33)
		_:
			var second := time >= 0.23
			var note := time - 0.23 if second else time
			var span := 0.086 if second else 0.17
			var window := clampf(minf(note / 0.023, (span - note) / 0.017), 0.0, 1.0)
			var tone := 682.0 if second else 768.0
			return window * (sin(TAU * tone * note + sin(note * 41.0) * 0.32) * 0.68
				+ sin(TAU * tone * 2.02 * note) * 0.13 + noise * 0.29)


static func _warning() -> AudioStreamWAV:
	var samples := PackedByteArray()
	samples.resize(8640)
	for i in range(4320):
		var time := float(i) / 24000.0
		var offset := time if time < 0.075 else time - 0.10
		var gain := clampf(minf(offset / 0.009, (0.074 - offset) / 0.02), 0, 1)
		var frequency := 660.0 if time < 0.075 else 880.0
		samples.encode_s16(i * 2, int(7800.0 * gain * sin(TAU * frequency * offset)))
	return _wave(samples)


static func _wave(samples: PackedByteArray) -> AudioStreamWAV:
	var stream := AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = RATE
	stream.data = samples
	return stream
