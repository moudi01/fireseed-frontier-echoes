extends RefCounted
## Original mono PCM. A fixed seed and envelopes make the sounds reproducible in an export.

const EFFECT_RATE := 22050
const MUSIC_RATE := 16000
const MUSIC_SECONDS := 12
# Duration, note sweep (Hz), ring partial, filtered noise, decay, peak.
const EFFECTS := {
	"slash": [0.12, 245.0, 82.0, 2.11, 0.48, 4.0, 0.32],
	"stab": [0.14, 420.0, 118.0, 2.77, 0.28, 4.5, 0.34],
	"guard": [0.20, 1180.0, 850.0, 1.57, 0.10, 4.9, 0.39],
	"arrow": [0.11, 940.0, 288.0, 2.9, 0.31, 4.6, 0.33],
	"bolt": [0.14, 775.0, 190.0, 1.66, 0.38, 4.4, 0.37],
	"arrow_hit": [0.11, 430.0, 145.0, 2.42, 0.27, 5.0, 0.32],
	"hit": [0.13, 175.0, 62.0, 2.18, 0.27, 4.4, 0.38],
	"down": [0.24, 108.0, 40.0, 1.63, 0.30, 4.2, 0.44],
	"heal": [0.30, 430.0, 650.0, 1.5, 0.02, 2.9, 0.35],
	"confirm": [0.095, 510.0, 710.0, 1.49, 0.02, 3.8, 0.29],
	"cancel": [0.09, 480.0, 300.0, 1.62, 0.02, 4.0, 0.25],
	"tab": [0.07, 620.0, 580.0, 2.02, 0.03, 4.9, 0.22],
	"place": [0.11, 248.0, 156.0, 1.70, 0.12, 4.2, 0.33],
}
# Four three-second voicings, using pitches from each scene's own scale.
const HARMONY := {
	"town": [[48, 55, 64], [45, 52, 60], [53, 60, 69], [43, 55, 62]],
	"wild": [[45, 52, 59], [43, 50, 57], [40, 52, 55], [45, 57, 64]],
	"fortress": [[38, 45, 53], [36, 43, 51], [34, 41, 48], [38, 44, 50]],
}


static func effect_bytes(name: String) -> PackedByteArray:
	var spec: Array = EFFECTS[name]
	var duration: float = spec[0]
	var count := roundi(duration * EFFECT_RATE)
	var bytes := PackedByteArray()
	bytes.resize(count * 2)
	var seed := 29389 + EFFECTS.keys().find(name) * 151
	var air := 0.0
	var pitch := 0.0
	for i in range(count):
		var progress := float(i) / float(count - 1)
		var frequency := lerpf(spec[1], spec[2], progress)
		pitch += TAU * frequency / EFFECT_RATE
		seed = (1664525 * seed + 1013904223) & 0xffffffff
		var grit := float(seed >> 16) / 32768.0 - 1.0
		air = lerpf(air, grit, 0.30)
		var ring := 0.70 * sin(pitch) + 0.25 * sin(pitch * float(spec[3]))
		var envelope := minf(progress * 38.0, 1.0) * minf((1.0 - progress) * 7.0, 1.0) * exp(-progress * float(spec[5]))
		var grit_level: float = spec[4]
		var value := lerpf(ring, air * 1.35, grit_level) * envelope * float(spec[6])
		bytes.encode_s16(i * 2, roundi(value * 32767.0))
	return bytes


static func music_bytes() -> Dictionary:
	var clips := {}
	for name: String in HARMONY:
		clips[name] = _music_bytes(name)
	return clips


static func _music_bytes(name: String) -> PackedByteArray:
	var count := MUSIC_SECONDS * MUSIC_RATE
	var bytes := PackedByteArray()
	bytes.resize(count * 2)
	var pulse := 2.0 if name == "fortress" else 1.0
	var bed := {"town": [110.0, 165.0], "wild": [82.0, 123.0], "fortress": [55.0, 82.0]}
	for bar in range(4):
		var chord: Array = HARMONY[name][bar]
		var notes: Array[float] = []
		for pitch: int in chord:
			notes.append(440.0 * pow(2.0, float(pitch - 69) / 12.0))
		for step in range(3 * MUSIC_RATE):
			var local := float(step) / MUSIC_RATE
			var time := local + 3.0 * bar
			var pad_gain := sin(PI * local / 3.0)
			var pad := pad_gain * (0.046 * sin(TAU * notes[0] * local) + 0.033 * sin(TAU * notes[1] * local))
			var pluck_time := fposmod(local * pulse, 1.0) / pulse
			var pluck := minf(pluck_time * 25.0, 1.0) * exp(-pluck_time * 7.0) * minf((1.0 / pulse - pluck_time) * 12.0, 1.0)
			pluck *= 0.058 * sin(TAU * notes[2] * pluck_time) + 0.012 * sin(TAU * notes[2] * 2.0 * pluck_time)
			var breath := 0.81 + 0.19 * cos(TAU * time / MUSIC_SECONDS)
			var drone := sin(TAU * float(bed[name][0]) * time) + 0.45 * sin(TAU * float(bed[name][1]) * time)
			var value := pad + pluck + 0.049 * breath * drone
			bytes.encode_s16((bar * 3 * MUSIC_RATE + step) * 2, roundi(value * 32767.0))
	return bytes


static func stream(bytes: PackedByteArray, rate: int, loop := false) -> AudioStreamWAV:
	var wave := AudioStreamWAV.new()
	wave.format = AudioStreamWAV.FORMAT_16_BITS
	wave.mix_rate = rate
	wave.data = bytes
	if loop:
		wave.loop_mode = AudioStreamWAV.LOOP_FORWARD
		wave.loop_end = bytes.size() >> 1
	return wave
