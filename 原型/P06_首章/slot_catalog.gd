extends RefCounted

static var _names := RegEx.create_from_string("^[A-Za-z0-9_-]{1,80}$")


static func valid_name(name: String) -> bool:
	return _names.search(name) != null


static func list_slots(data_dir: String) -> Array[Dictionary]:
	var rows: Array[Dictionary] = []
	var directory := DirAccess.open(data_dir.path_join("runs"))
	if directory == null:
		return rows
	for name in directory.get_directories():
		if not valid_name(name) or directory.is_link(name):
			continue
		var path := directory.get_current_dir().path_join(name)
		var save := path.path_join("save.json")
		var primary := FileAccess.file_exists(save)
		var backup := FileAccess.file_exists(save + ".bak")
		if primary or backup or FileAccess.file_exists(path.path_join("ledger.json")):
			var latest := FileAccess.get_modified_time(save if primary else save + ".bak")
			rows.append({"name": name, "primary": primary, "backup": backup, "modified": latest})
	rows.sort_custom(func(a: Dictionary, b: Dictionary) -> bool:
		return a.name < b.name if a.modified == b.modified else a.modified > b.modified)
	return rows


static func new_name() -> String:
	var date := Time.get_date_string_from_system().replace("-", "")
	return "run-%s-%s" % [date, Crypto.new().generate_random_bytes(12).hex_encode()]
