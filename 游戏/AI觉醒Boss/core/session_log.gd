extends RefCounted
## Opt-in local diagnostics. Never used by simulation, saving, or action-day accounting.
var file: FileAccess
var started=0
var focused=0.0
var closed=false
var error=""
var path=""
func open(folder: String) -> bool:
	started=Time.get_ticks_msec();focused=0.0;closed=false
	var probe=folder.simplify_path()
	while not probe.is_empty():
		if FileAccess.file_exists(probe):error="试玩记录路径被文件占用";return false
		if DirAccess.dir_exists_absolute(probe):break
		var parent=probe.get_base_dir()
		if parent==probe:break
		probe=parent
	if DirAccess.make_dir_recursive_absolute(folder)!=OK:error="无法创建试玩记录目录";return false
	path=folder.path_join("session_%d_%d.jsonl"%[OS.get_process_id(),Time.get_ticks_usec()]);file=FileAccess.open(path,FileAccess.WRITE)
	if file==null:error="无法写入试玩记录";return false
	record("session_start",{"schema":1,"clock":"wall_and_focused_seconds","local_only":true});return true
func advance(delta: float,has_focus: bool):
	if has_focus:focused+=maxf(0.0,delta)
func record(kind: String,fields: Dictionary={}):
	if file==null or closed:return
	var data={"kind":kind,"elapsed_s":float(Time.get_ticks_msec()-started)/1000.0,"focused_s":focused};data.merge(fields)
	file.store_line(JSON.stringify(data));file.flush()
	if file.get_error()!=OK:error="试玩记录写入失败"
func finish():
	if closed:return
	record("session_end");closed=true
	if file!=null:file.close();file=null
