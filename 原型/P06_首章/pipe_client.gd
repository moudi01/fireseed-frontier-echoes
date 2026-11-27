extends Node

signal refreshed(row: Dictionary)
signal notice(message: String, command: String, args: Array)
signal busy_changed(value: bool)
signal contact_model_hint(kinds: Array)

enum ExchangeError { NONE, SAVE_REQUEST, SEND_REQUEST }
const MAX_REQUEST_BYTES := 65536

var busy := false
var blocked := false
var can_reconnect := false
var save_version_incompatible := false
var frame: Dictionary = {}
var data_dir: String
var case_name: String
var pending: Dictionary = {}
var runtime_log := ""
var _pipe: FileAccess
var _stderr: FileAccess
var _pid := -1
var _thread: Thread
var _bundle: String
var _slot_mode := "legacy"
var _operation := ""
var _receipt_for_snapshot: Dictionary = {}
var _expires := 0
var _inline_presentation := false
var _battle_board_refs := false
var _reconnect_until := 0
var views_in_receipts := 0
var snapshot_requests := 0
var battle_boards_reused := 0
var profile_receipts := false
var receipt_timings: Array[Dictionary] = []
var contact_hint_timing: Dictionary = {}
var _receipt_timing: Dictionary = {}


func boot(bundle: String, directory: String, session: String, slot_mode := "legacy") -> void:
	_bundle = bundle
	_slot_mode = slot_mode
	data_dir = directory
	case_name = session
	_open()


func _open() -> void:
	pending = {}
	_receipt_for_snapshot = {}
	runtime_log = ""
	save_version_incompatible = false
	if DirAccess.make_dir_recursive_absolute(data_dir) != OK:
		_stop("无法建立样段存档目录。")
		return
	var log_directory := data_dir.path_join("logs")
	DirAccess.make_dir_recursive_absolute(log_directory)
	runtime_log = log_directory.path_join("runtime-" + Crypto.new().generate_random_bytes(12).hex_encode() + ".log")
	var args := PackedStringArray(["-B", "-I", _bundle.path_join("launch_runtime.py"), runtime_log,
		"--case-id", case_name, "--runs-dir", data_dir.path_join("runs")])
	if _slot_mode != "legacy":
		args.append_array(["--slot-mode", _slot_mode])
	var process := OS.execute_with_pipe(_bundle.path_join("runtime/python.exe"), args, true)
	if process.is_empty():
		_stop("无法启动样段运行时，请核对旁载包。")
		return
	_pipe = process["stdio"]
	_stderr = process["stderr"]
	_pid = process["pid"]
	print("P06 runtime pid=%d log=%s" % [_pid, runtime_log])
	if not busy:
		_set_busy(true)
	_exchange("ready")


func submit(command: String, args: Array) -> bool:
	if busy or blocked or frame.is_empty() or not pending.is_empty():
		return false
	var request_id := Crypto.new().generate_random_bytes(16).hex_encode()
	var request := {"protocol_version": 1, "op": "execute", "request_id": request_id,
		"expected_version": int(frame["state_version"]), "expected_epoch": frame["connection_epoch"],
		"command": command, "args": args.duplicate(true)}
	if _inline_presentation:
		request["inline_presentation"] = true
		if _battle_board_refs:
			var known := _known_battle_board()
			if not known.is_empty():
				request["battle_board"] = known
	pending = request
	_set_busy(true)
	return _exchange("execute", request)


func _pending_path() -> String:
	return data_dir.path_join(case_name + ".pending.json")


func _load_pending() -> bool:
	# READY means no other runtime can change this session's request files.
	if FileAccess.file_exists(_pending_path()):
		var journal := FileAccess.open(_pending_path(), FileAccess.READ)
		var saved: Variant = null
		if journal != null and journal.get_length() <= MAX_REQUEST_BYTES:
			saved = JSON.parse_string(journal.get_as_text())
		if not saved is Dictionary or not saved.get("request_id") is String:
			_stop("请求记录无法读取，已停止提交。")
			return false
		pending = saved
	if FileAccess.file_exists(_pending_path() + ".tmp"):
		_stop("请求记录存在未完成的写入，请保留现场。")
		return false
	return true


func _preserve_pending(request: Dictionary) -> bool:
	var temporary := _pending_path() + ".tmp"
	var file := FileAccess.open(temporary, FileAccess.WRITE)
	if file == null:
		return false
	file.store_string(JSON.stringify(request))
	file.flush()
	var status := file.get_error()
	file.close()
	return status == OK and DirAccess.rename_absolute(temporary, _pending_path()) == OK


func _set_busy(value: bool) -> void:
	busy = value
	busy_changed.emit(value)


func _exchange(operation: String, request: Dictionary = {}) -> bool:
	_operation = operation
	_expires = Time.get_ticks_msec() + 15000
	_thread = Thread.new()
	if _thread.start(_exchange_worker.bind(request, operation == "execute")) != OK:
		_thread = null
		if operation == "execute":
			pending.clear()
		_stop("无法启动运行时通信。")
		return false
	return true


func _exchange_worker(request: Dictionary, save_request: bool) -> void:
	if save_request and not _preserve_pending(request):
		call_deferred("_receive", null, ExchangeError.SAVE_REQUEST)
		return
	if not request.is_empty():
		_pipe.store_line(JSON.stringify(request))
		_pipe.flush()
		if _pipe.get_error() != OK:
			call_deferred("_receive", null, ExchangeError.SEND_REQUEST)
			return
	var line := _pipe.get_line()
	var incoming: Variant = null if line.is_empty() else JSON.parse_string(line)
	call_deferred("_receive", incoming, ExchangeError.NONE)


func _receive(incoming: Variant, error: ExchangeError) -> void:
	var started := Time.get_ticks_usec() if profile_receipts else 0
	_thread.wait_to_finish()
	if profile_receipts:
		_receipt_timing = {"started_usec": started, "join_usec": Time.get_ticks_usec() - started}
	_thread = null
	_expires = 0
	if blocked:
		return
	if error == ExchangeError.SAVE_REQUEST:
		pending.clear()
		_stop("请求记录无法保存，操作未发送。")
		return
	if error == ExchangeError.SEND_REQUEST:
		_stop("连接中断。重新连接时会按原编号核对待确认请求。", true)
		return
	if not incoming is Dictionary:
		if _operation == "ready":
			_stop("运行时未能打开试玩会话。请查看会话目录。")
		else:
			_stop("旁载连接已关闭。重新连接会核对原请求编号。", true)
		return
	var row: Dictionary = incoming
	match _operation:
		"ready":
			if row.get("status") == "SESSION_BUSY":
				_stop("此试玩会话正在使用。请关闭原窗口，再选择「重新连接」。", true)
				return
			if row.get("status") == "SLOT_MISSING":
				_stop("所选存档的主档已丢失。请查看恢复提示或另选存档。")
				return
			if row.get("status") == "SLOT_VERSION_INCOMPATIBLE":
				save_version_incompatible = true
				_stop("存档版本与当前旁载运行时不兼容。")
				return
			if row.get("status") == "SLOT_EXISTS":
				_stop("新槽名已被使用。现有存档仍可从主菜单打开。")
				return
			if row.get("status") != "READY":
				_stop("旁载进程未能打开此存档。")
				return
			if _slot_mode == "new":
				_slot_mode = "existing"
			if not _load_pending():
				_kill_sidecar()
				return
			_inline_presentation = row.get("inline_presentation", false) == true
			_battle_board_refs = row.get("battle_board_refs", false) == true
			if not pending.is_empty():
				_exchange("query", {"protocol_version": 1, "op": "query", "request_id": pending["request_id"],
					"match_pending": true})
			else:
				_snapshot()
				var kinds: Variant = row.get("contact_model_kinds")
				if kinds is Array and not kinds.is_empty():
					if profile_receipts:
						contact_hint_timing = {"at_usec": Time.get_ticks_usec(), "kinds": kinds}
					contact_model_hint.emit(kinds)
		"execute", "query":
			_handle_result(row)
		"snapshot":
			if row.get("status") != "SNAPSHOT":
				_stop("无法核对存档和提交记录，当前会话停止提交。")
				return
			if not _receipt_for_snapshot.is_empty():
				if _receipt_for_snapshot.get("status") == "COMMITTED" and not _snapshot_matches_receipt(row):
					_stop("当前存档无法核对已收到的保存回执，当前会话停止提交。")
					return
				if not _finish_request(_receipt_for_snapshot):
					return
				_receipt_for_snapshot = {}
			_publish(row)


func _handle_result(row: Dictionary) -> void:
	var status: String = row.get("status", "")
	var next: String = row.get("next_action", "")
	if _operation == "query" and row.get("error") == "PENDING_JOURNAL_UNVERIFIED":
		_stop("待确认请求无法与事务账本核对。已保留原记录，请查看会话目录。")
		return
	if status == "UNKNOWN" or next == "QUERY_AND_STOP" or next == "QUERY_ORIGINAL_REQUEST":
		_stop("结果待核实。已保留原请求和存档，当前会话停止提交。")
		return
	if _operation == "query" and row.get("request_id") != pending.get("request_id"):
		_stop("收到无法对应原编号的结果，当前会话停止提交。")
		return
	if status == "COMMITTED":
		var ack: Dictionary = row.get("persistence_ack", {})
		if ack.get("request_id") != pending.get("request_id") or ack.get("state_digest") != row.get("state_digest") or ack.get("files") != row.get("files") or ack.get("state_version") != row.get("state_version"):
			_stop("收到无法核对的保存回执，当前会话停止提交。")
			return
	elif status != "REJECTED" and not (status == "NOT_FOUND" and _operation == "query"):
		_stop("收到无法识别的运行时回复，当前会话停止提交。")
		return
	if status == "COMMITTED" and _operation == "execute" and row.get("presentation") is Dictionary:
		if not _restore_battle_board(row):
			_receipt_for_snapshot = row
			_snapshot()
			return
		if not _finish_request(row):
			return
		views_in_receipts += 1
		_publish(row)
	else:
		_receipt_for_snapshot = row
		_snapshot()


func _publish(row: Dictionary) -> void:
	var started := Time.get_ticks_usec() if profile_receipts else 0
	frame = row
	refreshed.emit(frame)
	var rendered := Time.get_ticks_usec() if profile_receipts else 0
	_set_busy(false)
	if profile_receipts:
		_receipt_timing["version"] = int(row.get("state_version", -1))
		_receipt_timing["refresh_usec"] = rendered - started
		_receipt_timing["render_usec"] = Time.get_ticks_usec() - rendered
		_receipt_timing["total_usec"] = Time.get_ticks_usec() - int(_receipt_timing.started_usec)
		receipt_timings.append(_receipt_timing)


func _known_battle_board() -> String:
	var presentation: Dictionary = frame.get("presentation", {})
	var map_data: Variant = presentation.get("map")
	var slice: Dictionary = presentation.get("slice", {})
	var battle: Variant = slice.get("battle_view")
	if slice.get("phase") != "BATTLE" or not battle is Dictionary or not map_data is Dictionary \
			or map_data.get("battle_cells", []).is_empty():
		return ""
	return str(battle.get("id", ""))


func _restore_battle_board(row: Dictionary) -> bool:
	var presentation: Dictionary = row.presentation
	var map_data: Variant = presentation.get("map")
	if not map_data is Dictionary or not map_data.has("battle_board_ref"):
		return true
	var board_ref: Variant = map_data.battle_board_ref
	var slice: Dictionary = presentation.get("slice", {})
	var battle: Variant = slice.get("battle_view")
	if not board_ref is String or board_ref.is_empty() or board_ref != _known_battle_board() \
			or frame.get("game_id") != row.get("game_id") or slice.get("phase") != "BATTLE" \
			or not battle is Dictionary or battle.get("id") != board_ref:
		return false
	var previous: Dictionary = frame.presentation
	if not previous.slice.get("town_board_cells") is Array or not previous.slice.get("town_deploy_cells") is Array:
		return false
	presentation["map"] = previous.map
	slice["town_board_cells"] = previous.slice.town_board_cells
	slice["town_deploy_cells"] = previous.slice.town_deploy_cells
	battle_boards_reused += 1
	return true


func _finish_request(row: Dictionary) -> bool:
	var started := Time.get_ticks_usec() if profile_receipts else 0
	var removed := DirAccess.remove_absolute(_pending_path())
	if profile_receipts:
		_receipt_timing["remove_pending_usec"] = Time.get_ticks_usec() - started
	if removed != OK:
		_stop("无法清理已核对的请求记录，请保留现场。")
		return false
	match row.get("status"):
		"COMMITTED":
			notice.emit(str(row.get("result", "已完成。")), str(pending.get("command", "")), pending.get("args", []))
		"NOT_FOUND":
			notice.emit("运行时没有记录该请求，请核对当前状态后重新选择操作。", "", [])
		"REJECTED":
			notice.emit("当前条件不允许或状态已更新，请核对可用操作。", "", [])
	pending.clear()
	return true


func _snapshot_matches_receipt(row: Dictionary) -> bool:
	var version := int(row.get("state_version", -1))
	var received := int(_receipt_for_snapshot.state_version)
	if version < received or row.get("game_id") != _receipt_for_snapshot.get("game_id"):
		return false
	return version > received or (row.get("state_digest") == _receipt_for_snapshot.get("state_digest") \
		and row.get("files") == _receipt_for_snapshot.get("files"))


func _snapshot() -> void:
	snapshot_requests += 1
	_exchange("snapshot", {"protocol_version": 1, "op": "snapshot"})


func _stop(message: String, reconnectable := false) -> void:
	_expires = 0
	blocked = true
	can_reconnect = reconnectable
	push_warning("P06 blocked (%s): %s" % [_operation, message])
	notice.emit(message, "", [])
	_set_busy(false)


func reconnect() -> bool:
	if busy or not blocked or not can_reconnect:
		return false
	can_reconnect = false
	_reconnect_until = Time.get_ticks_msec() + 5000
	_set_busy(true)
	_kill_sidecar()
	return true


func cancel_snapshot_for_close() -> bool:
	if not busy or _operation != "snapshot" or not pending.is_empty():
		return false
	# READY has completed the session setup. This exchange only reads the snapshot.
	blocked = true
	_expires = 0
	_kill_sidecar()
	return true


func _process(_delta: float) -> void:
	var now := Time.get_ticks_msec()
	if _reconnect_until > 0:
		if _thread == null and (_pid < 0 or not OS.is_process_running(_pid)):
			_reconnect_until = 0
			_pipe = null
			_stderr = null
			_pid = -1
			_inline_presentation = false
			_battle_board_refs = false
			blocked = false
			_open()
		elif now >= _reconnect_until:
			_reconnect_until = 0
			_stop("旧连接尚未退出。请稍后重新连接。", true)
		return
	if _expires > 0 and now >= _expires:
		_expires = 0
		_stop("操作超时。重新连接时会核对已记录的请求。", _operation != "ready")
		_kill_sidecar()


func _kill_sidecar() -> void:
	if _pid >= 0 and OS.is_process_running(_pid):
		OS.kill(_pid)


func _exit_tree() -> void:
	_kill_sidecar()
	if _thread != null and _thread.is_started():
		_thread.wait_to_finish()
