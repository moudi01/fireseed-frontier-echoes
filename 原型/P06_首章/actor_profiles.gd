extends RefCounted

const Actor = preload("res://shield_actor.gd")
const Melee = preload("res://melee_actor.gd")
const Bow = preload("res://bow_actor.gd")
const Targeted = preload("res://targeted_actor.gd")
const Crossbow = preload("res://crossbow_actor.gd")
const Spear = preload("res://spear_actor.gd")
const Hero = preload("res://hero_actor.gd")
const Mimic = preload("res://mimic_actor.gd")
const DualSac = preload("res://dual_sac_actor.gd")
const Echo = preload("res://echo_actor.gd")
const Wasp = preload("res://wasp_actor.gd")
const RingGuard = preload("res://ring_guard_actor.gd")
const SkeletonEnemy = preload("res://skeleton_actor.gd")
const Ado = preload("res://ado_actor.gd")
const Mg02 = preload("res://mg02_actor.gd")
const Mg03 = preload("res://mg03_actor.gd")
const Mg04 = preload("res://mg04_actor.gd")
const Demon = preload("res://demon_actor.gd")
const Admin = preload("res://admin_actor.gd")
const AdminGuards = preload("res://admin_guard_profiles.gd")
const En02 = preload("res://en02_actor.gd")
const En02Profile = preload("res://en02_profile.gd")
const En05Profile = preload("res://en05_profile.gd")
const En07Profile = preload("res://en07_profile.gd")
const El04Profile = preload("res://el04_profile.gd")
const En08Profile = preload("res://en08_profile.gd")
const En15Profile = preload("res://en15_profile.gd")
const En19Profile = preload("res://en19_profile.gd")
const En20Profile = preload("res://en20_profile.gd")
const GoblinCrossbow = preload("res://goblin_crossbow_actor.gd")

const ASSETS := "res://assets/"
const ENEMIES := ASSETS + "enemies/"
const SHIELD_MODEL := ASSETS + "S01-M_Shield_Feedback.glb"
const FORTRESS := ASSETS + "fortress/"
const ADO_ASSET := "MG01_Board.glb"
const ADO_MODEL := FORTRESS + ADO_ASSET
const SPEAR_MODEL := ASSETS + "M01_Tripo_Lane_Spear.glb"
const HERO_KINDS := ["H01", "H02", "H03", "H04", "H05", "H06", "H07", "H08", "H09", "H10", "H11", "H12"]
const SKELETON_KINDS := ["EN21", "EN22"]

# Background prefetch/attachment is limited to the existing contact queue.
# Ado uses the queue for its special preview and attaches synchronously once ready.
const STANDARD := {
	"S01": {"model": SHIELD_MODEL, "script": Actor, "side": "player", "assembly": "shield",
		"clips": {"guard": Actor.GUARD, "travel": Actor.MOVE, "stop": Actor.STOP, "attack": Actor.ATTACK,
			"hit": Actor.HIT, "down": Actor.DOWN, "block": Actor.BLOCK},
		"stop_time": 0.20},
	"S02": {"model": ASSETS + "S02-M_GapRuntime.glb", "script": Melee, "side": "player",
		"assembly": "melee", "prefetch": true, "stagger": true,
		"clips": {"guard": "MeleeGuard", "travel": "MeleeAdvance", "stop": "MeleeStop",
			"attack": "MeleeAttack", "hit": "MeleeHit", "down": "MeleeDown"},
		"stop_time": 0.16, "attack_entry": 0.10, "attack_contact": 0.22},
	"S03": {"model": ASSETS + "S03-M_Meshy_BowRuntime.glb", "script": Bow, "side": "player",
		"assembly": "bow", "prefetch": true, "stagger": true, "require_root_track": false,
		"clips": {"guard": "BowGuard", "travel": "BowWalk", "stop": "BowStop",
			"attack": "BowAttack", "hit": "BowHitFront", "down": "BowDown"}},
	"M01": {"model": SPEAR_MODEL, "script": Spear, "side": "player", "prefetch": true, "spear_setting": true},
	"M03": {"model": ASSETS + "M03_BreachRuntime.glb", "script": Crossbow, "side": "player",
		"assembly": "crossbow", "prefetch": true, "prefetch_travel": true,
		"clips": {"guard": "RangedGuard", "travel": "RangedAdvance", "stop": "RangedStop",
			"attack": "RangedAttack", "hit": "RangedHit", "down": "RangedDown"}},
	"EN01": {"model": ASSETS + "gray_oak/en01_articulated.glb", "script": Mimic, "side": "enemy", "head_height": 0.78},
	"EN03": {"model": ENEMIES + "EN03_Runtime.glb", "script": Wasp, "side": "enemy", "head_height": 1.15},
	"EN04": {"model": ENEMIES + "EN04_Board.glb", "script": RingGuard, "side": "enemy", "prefetch": true},
	"EN06": {"model": ENEMIES + "EN06_Runtime.glb", "script": Echo, "side": "enemy", "head_height": 1.15},
	"EN17": {"model": ENEMIES + "EN17_Board.glb", "script": Spear, "side": "enemy",
		"assembly": "enemy_spear", "prefetch": true},
	"EN21": {"model": ENEMIES + "EN21_Board.glb", "script": SkeletonEnemy, "side": "enemy", "assembly": "skeleton"},
	"EN22": {"model": ENEMIES + "EN22_Board.glb", "script": SkeletonEnemy, "side": "enemy", "assembly": "skeleton"},
	"EL02": {"model": ENEMIES + "EL02_Board.glb", "script": DualSac, "side": "enemy", "head_height": 1.15, "prefetch": true},
	"MG01": {"model": ADO_MODEL, "script": Ado, "side": "enemy", "head_height": 2.40,
		"contact_height": 2.70, "prefetch": true, "background": false},
}

# Presentation only. Move and pending keys come from the existing battle view.
const TARGETED := {
	"M02": {
		"model": "res://assets/M02_Tripo_AidRuntime.glb", "effect": "aid",
		"move": "M02-A", "pending": "aid_pending",
		"clips": {"guard": "AidIdle", "travel": "AidWalk", "stop": "AidStop",
			"attack": "AidFire", "hit": "AidHit", "down": "AidDown", "raise": "AidRaise",
			"hold": "AidHold", "abort": "AidCancel", "release": "AidFire"},
		"release": {"socket": "AidMuzzle", "contact": 23.0 / 30.0, "entry": 0.42, "speed": 4.4},
	},
	"M04": {
		"model": "res://assets/M04_MistRuntime.glb", "effect": "mist",
		"move": "M04-A", "pending": "mist_pending", "attack_contact": 0.46,
		"clips": {"guard": "MistIdle", "travel": "MistWalk", "stop": "MistStop",
			"attack": "MistAttack", "hit": "MistHit", "down": "MistDown", "raise": "MistRaise",
			"hold": "MistHold", "abort": "MistCancel", "release": "MistRelease"},
		"release": {"socket": "MistPalm", "contact": 12.0 / 30.0, "speed": 4.0},
	},
}


const HERO_CLIPS := {"guard": "HeroIdle", "travel": "HeroWalk", "stop": "HeroStop",
	"attack": "HeroAttack", "hit": "HeroHit", "down": "HeroDown"}


static var entries: Dictionary = _build_entries()


static func _build_entries() -> Dictionary:
	var result := STANDARD.duplicate()
	var charger := En02Profile.entry(En02)
	charger["assembly"] = "charge"
	result["EN02"] = charger
	var eel := En05Profile.entry(Admin)
	eel["assembly"] = "enemy_cast"
	result["EN05"] = eel
	var heron := En07Profile.entry(Admin)
	heron["assembly"] = "enemy_cast"
	result["EN07"] = heron
	var elite := El04Profile.entry(Admin)
	elite["assembly"] = "enemy_cast"
	result["EL04"] = elite
	var spores := En08Profile.entry(Admin)
	spores["assembly"] = "enemy_cast"
	result["EN08"] = spores
	var choir := En15Profile.entry(Admin)
	choir["assembly"] = "enemy_cast"
	result["EN15"] = choir
	var raider := En19Profile.entry(Admin)
	raider["assembly"] = "enemy_cast"
	result["EN19"] = raider
	var crossbow := En20Profile.entry(GoblinCrossbow)
	crossbow["assembly"] = "enemy_cast"
	# Local clip time at the authored recoil marker.
	crossbow["bolt_release_time"] = 0.153
	result["EN20"] = crossbow
	var sev := Mg02.profile_entry(Mg02)
	sev["optional"] = true
	result["MG02"] = sev
	result["MG03"] = Mg03.profile_entry(Mg03)
	result["MG04"] = Mg04.profile_entry(Mg04)
	result["DEMON"] = Demon.profile_entry(Demon)
	result["ADMIN"] = Admin.profile_entry(Admin)
	var guards := AdminGuards.entries(Admin)
	for kind in guards:
		guards[kind]["assembly"] = "admin_guard"
	result.merge(guards)
	for kind in TARGETED:
		var row: Dictionary = TARGETED[kind].duplicate()
		row.merge({"script": Targeted, "side": "player", "assembly": "targeted",
			"prefetch": true, "prefetch_travel": true, "require_root_track": false, "stop_limit": 0.24})
		result[kind] = row
	for kind in HERO_KINDS:
		result[kind] = {"model": ASSETS + "heroes/" + kind + "_Runtime.glb", "script": Hero,
			"side": "player", "assembly": "hero", "prefetch": true, "optional": true,
			"require_root_track": false, "clips": HERO_CLIPS,
			"stop_time": 0.16, "attack_entry": 0.08, "attack_contact": 0.28}
	return result
