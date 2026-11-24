extends RefCounted
## Immutable journal + two current mirrors. A durable journal entry is the commit point.
const RULES=preload("res://core/campaign_rules.gd")
var engine: RefCounted
var root=""
var state: Dictionary={}
var error=""
var warning=""
var faults: Dictionary={}
var decode_error=""
var load_blocked=false

func _init(rule_engine=null) -> void:
	engine=rule_engine

func normalize(value):
	if value is float and engine.CORE.integer(value):return int(value)
	if value is Array:
		return value.map(func(item):return normalize(item))
	if value is Dictionary:
		var output={}
		for key in value:output[key]=normalize(value[key])
		return output
	return value

func parse(text: String):
	var json=JSON.new()
	return json.data if json.parse(text)==OK else null

func decode(path: String) -> Dictionary:
	decode_error=""
	if DirAccess.dir_exists_absolute(path):path=path.path_join("record.save")
	if not FileAccess.file_exists(path):return {}
	var file=FileAccess.open(path,FileAccess.READ)
	if file==null or file.get_length()>32*1024*1024:return {}
	var envelope=parse(file.get_as_text())
	if not envelope is Dictionary or envelope.get("magic")!="AI_BOSS_SAVE":return {}
	if not engine.CORE.integer(envelope.get("version")) or int(envelope.version)!=1:
		decode_error="不支持的存档格式版本；文件保留，未创建新进度";return {}
	if not envelope.get("payload_json") is String:return {}
	if envelope.payload_json.sha256_text()!=envelope.get("sha256"):return {}
	var payload=normalize(parse(envelope.payload_json))
	if payload is Dictionary and (not RULES.supported_schema(payload) or not RULES.supported_settlement(payload)):
		decode_error="不支持的存档结构或结算规则版本；文件保留，未升级或创建新进度";return {}
	if not payload is Dictionary or not engine.valid_state(payload) or payload.revision!=envelope.get("revision"):return {}
	return payload

func open(path: String) -> bool:
	root=path;error="";warning="";state={};load_blocked=true
	if DirAccess.make_dir_recursive_absolute(root.path_join("journal"))!=OK:
		error="无法建立存档目录";return false
	var highest=0;var candidates=[]
	var directory=DirAccess.open(root.path_join("journal"))
	for name in directory.get_files()+directory.get_directories():
		if name.begins_with("entry_") and name.ends_with(".save"):
			var number=name.trim_prefix("entry_").trim_suffix(".save")
			if number.is_valid_int():
				highest=maxi(highest,int(number));candidates.append(root.path_join("journal").path_join(name))
	for name in ["latest.save","recovery.save"]:
		var candidate=root.path_join(name)
		if FileAccess.file_exists(candidate):candidates.append(candidate)
	var best={}
	for candidate in candidates:
		var decoded=decode(candidate)
		if not decode_error.is_empty():error=decode_error;return false
		if not decoded.is_empty() and (best.is_empty() or int(decoded.revision)>int(best.revision)):best=decoded
	if highest>0 and (best.is_empty() or int(best.revision)<highest):
		error="最新已确认进度的所有副本均损坏；已保留文件，拒绝回退到旧行动";return false
	if not candidates.is_empty() and best.is_empty():
		error="存档损坏，未建立新进度覆盖旧文件";return false
	state=best
	if not state.is_empty():
		var latest=decode(root.path_join("latest.save"));var recovery=decode(root.path_join("recovery.save"))
		if latest.is_empty() or recovery.is_empty() or int(latest.revision)!=int(state.revision) or int(recovery.revision)!=int(state.revision):warning="已从有效的行动记录恢复；未重新抽取部署或发奖"
	load_blocked=false
	return true

func commit_record(path: String,text: String) -> bool:
	# The final directory is immutable and non-empty. On Windows, rename cannot
	# replace another non-empty directory; competing revisions cannot overwrite.
	if FileAccess.file_exists(path) or DirAccess.dir_exists_absolute(path):return false
	var staging=root.path_join("staging")
	if FileAccess.file_exists(staging):return false
	if DirAccess.make_dir_recursive_absolute(staging)!=OK:return false
	var prepared=staging.path_join("entry_%d_%d"%[OS.get_process_id(),Time.get_ticks_usec()])
	if DirAccess.make_dir_absolute(prepared)!=OK:return false
	var file=FileAccess.open(prepared.path_join("record.save"),FileAccess.WRITE)
	if file==null:DirAccess.remove_absolute(prepared);return false
	file.store_string(text);file.flush();var result=file.get_error();file.close()
	if result==OK and DirAccess.rename_absolute(prepared,path)==OK:return true
	DirAccess.remove_absolute(prepared.path_join("record.save"));DirAccess.remove_absolute(prepared)
	return false

func atomic_write(path: String,text: String) -> bool:
	var temporary=path+".tmp"
	var file=FileAccess.open(temporary,FileAccess.WRITE)
	if file==null:return false
	file.store_string(text);file.flush()
	var result=file.get_error();file.close()
	if result!=OK:return false
	return DirAccess.rename_absolute(temporary,path)==OK

func find_committed(command: Dictionary,digest: String) -> Dictionary:
	var current=get_script().new(engine)
	if not current.open(root):return {"ok":false,"committed":null,"error":"无法确认本次提交状态；已保留文件："+current.error}
	if not current.state.is_empty() and current.state.applied_commands.has(command.id):
		if current.state.applied_commands[command.id]!=digest:return {"ok":false,"error":"同一命令ID携带不同内容"}
		state=current.state;warning=current.warning
		return {"ok":true,"duplicate":true,"committed":true,"warning":warning}
	return {}

func dispatch(command: Dictionary) -> Dictionary:
	if load_blocked:return {"ok":false,"committed":false,"error":"存档未能安全加载，禁止创建或覆盖进度："+error}
	error="";warning=""
	if not command.get("id") is String or command.id.is_empty() or command.id.length()>200:return {"ok":false,"error":"命令ID无效"}
	var digest=JSON.stringify({"kind":command.get("kind"),"payload":command.get("payload",{})},"",true).sha256_text()
	if not state.is_empty() and state.applied_commands.has(command.id):
		if state.applied_commands[command.id]!=digest:return {"ok":false,"error":"同一命令ID携带不同内容"}
		return {"ok":true,"duplicate":true,"committed":true}
	var revision=int(state.get("revision",0))
	if not command.has("expected_revision") or command.expected_revision!=revision:
		var existing=find_committed(command,digest)
		return existing if not existing.is_empty() else {"ok":false,"error":"页面状态已变化，请刷新后确认"}
	var outcome=engine.apply(state,command)
	if not outcome.ok:return outcome
	var next=outcome.state
	if not engine.valid_state(next):return {"ok":false,"committed":false,"error":"命令结果未通过状态校验；未写盘"}
	next.revision=revision+1;next.applied_commands[command.id]=digest
	var payload=JSON.stringify(next,"",true)
	var envelope=JSON.stringify({"magic":"AI_BOSS_SAVE","version":1,"revision":next.revision,"payload_json":payload,"sha256":payload.sha256_text()})
	var journal=root.path_join("journal/entry_%08d.save"%int(next.revision))
	if faults.get("before_journal",false) or FileAccess.file_exists(journal) or not commit_record(journal,envelope):
		if not faults.get("before_journal",false) and (FileAccess.file_exists(journal) or DirAccess.dir_exists_absolute(journal)):
			var existing=find_committed(command,digest)
			if not existing.is_empty():return existing
			error="其他实例已更新进度；本次未提交，请重启续玩"
		else:error="行动未提交：无法写入新的行动记录；人员与资源未改变"
		return {"ok":false,"committed":false,"error":error}
	# The command is durable now. Mirror failure must not report it as uncommitted.
	state=next
	if faults.get("after_journal",false) or not atomic_write(root.path_join("latest.save"),envelope) or not atomic_write(root.path_join("recovery.save"),envelope):
		warning="行动已经提交，快照未完成；重启将从行动记录恢复"
	return {"ok":true,"committed":true,"duplicate":false,"warning":warning}
