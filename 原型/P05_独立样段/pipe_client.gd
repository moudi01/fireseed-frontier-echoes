extends Node

signal refreshed(row: Dictionary)
signal notice(message: String)
signal busy_changed(value: bool)

var busy := false
var blocked := false
var frame: Dictionary = {}
var data_dir: String
var case_name: String
var pending: Dictionary = {}
var _pipe: FileAccess
var _stderr: FileAccess
var _pid := -1
var _thread: Thread
var _operation := ""
var _expires := 0


func boot(bundle: String, directory: String, session: String) -> void:
	data_dir = directory
	case_name = session
	if DirAccess.make_dir_recursive_absolute(data_dir) != OK:
		_stop("无法建立样段存档目录。")
		return
	if FileAccess.file_exists(_pending_path()):
		var saved: Variant = JSON.parse_string(FileAccess.get_file_as_string(_pending_path()))
		if not saved is Dictionary or not saved.has("request_id"):
			_stop("请求记录无法读取，已停止提交。")
			return
		pending = saved
	if FileAccess.file_exists(_pending_path() + ".tmp"):
		_stop("请求记录存在未完成的写入，请保留现场。")
		return
	var process := OS.execute_with_pipe(bundle.path_join("runtime/python.exe"), PackedStringArray([
		"-B", "-I", bundle.path_join("protocol_service.py"), "--case-id", case_name, "--runs-dir", data_dir.path_join("runs")
	]), true)
	if process.is_empty():
		_stop("无法启动样段运行时，请核对旁载包。")
		return
	_pipe = process["stdio"]
	_stderr = process["stderr"]
	_pid = process["pid"]
	_set_busy(true)
	_read("ready")


func submit(command: String, args: Array) -> bool:
	if busy or blocked or frame.is_empty() or not pending.is_empty():
		return false
	var request_id := Crypto.new().generate_random_bytes(16).hex_encode()
	var request := {"protocol_version": 1, "op": "execute", "request_id": request_id,
		"expected_version": int(frame["state_version"]), "expected_epoch": frame["connection_epoch"],
		"command": command, "args": args}
	if not _preserve_pending(request):
		_stop("请求记录无法保存，操作未发送。")
		return false
	pending = request
	_set_busy(true)
	_send(request, "execute")
	return true


func _pending_path() -> String:
	return data_dir.path_join(case_name + ".pending.json")


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


func _send(request: Dictionary, operation: String) -> void:
	_pipe.store_line(JSON.stringify(request))
	_pipe.flush()
	if _pipe.get_error() != OK:
		_stop("连接中断，已保留原请求供下次启动查询。")
		return
	_read(operation)


func _read(operation: String) -> void:
	_operation = operation
	_expires = Time.get_ticks_msec() + 15000
	_thread = Thread.new()
	if _thread.start(_read_worker) != OK:
		_thread = null
		_stop("无法读取运行时回复。")


func _read_worker() -> void:
	var line := _pipe.get_line()
	call_deferred("_receive", line)


func _receive(line: String) -> void:
	_thread.wait_to_finish()
	_thread = null
	_expires = 0
	if blocked:
		return
	var incoming: Variant = JSON.parse_string(line)
	if not incoming is Dictionary:
		_stop("旁载连接已关闭。未确认的请求将按原编号查询。")
		return
	var row: Dictionary = incoming
	match _operation:
		"ready":
			if row.get("status") != "READY":
				_stop("旁载进程未能打开此存档。")
				return
			if not pending.is_empty():
				_send({"protocol_version": 1, "op": "query", "request_id": pending["request_id"]}, "query")
			else:
				_snapshot()
		"execute", "query":
			_handle_result(row)
		"snapshot":
			if row.get("status") != "SNAPSHOT":
				_stop("无法读取可用状态。")
				return
			frame = row
			refreshed.emit(frame)
			_set_busy(false)


func _handle_result(row: Dictionary) -> void:
	var status: String = row.get("status", "")
	var next: String = row.get("next_action", "")
	if status == "UNKNOWN" or next == "QUERY_AND_STOP" or next == "QUERY_ORIGINAL_REQUEST":
		_stop("结果待核实。已保留原请求和存档，当前会话停止提交。")
		return
	if status == "COMMITTED":
		var ack: Dictionary = row.get("persistence_ack", {})
		if ack.get("request_id") != pending.get("request_id") or ack.get("state_digest") != row.get("state_digest") or ack.get("files") != row.get("files") or ack.get("state_version") != row.get("state_version"):
			_stop("收到无法核对的保存回执，当前会话停止提交。")
			return
		notice.emit(str(row.get("result", "已完成。")))
	elif status == "NOT_FOUND" and _operation == "query":
		notice.emit("运行时没有记录该请求，请核对当前状态后重新选择操作。")
	elif status == "REJECTED":
		notice.emit("当前条件不允许或状态已更新，请核对可用操作。")
	else:
		_stop("收到无法识别的运行时回复，当前会话停止提交。")
		return
	if DirAccess.remove_absolute(_pending_path()) != OK:
		_stop("无法清理已核对的请求记录，请保留现场。")
		return
	pending.clear()
	_snapshot()


func _snapshot() -> void:
	_send({"protocol_version": 1, "op": "snapshot"}, "snapshot")


func _stop(message: String) -> void:
	blocked = true
	notice.emit(message)
	_set_busy(false)


func _process(_delta: float) -> void:
	if _expires > 0 and Time.get_ticks_msec() >= _expires:
		_expires = 0
		_stop("运行时回复超时。保留原请求，重启时先查询。")
		if _pid >= 0 and OS.is_process_running(_pid):
			OS.kill(_pid)


func _exit_tree() -> void:
	if _pid >= 0 and OS.is_process_running(_pid):
		OS.kill(_pid)
	if _thread != null and _thread.is_started():
		_thread.wait_to_finish()
