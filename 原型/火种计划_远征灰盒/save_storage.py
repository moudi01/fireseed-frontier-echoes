"""Single-writer save backup, corruption diagnostics and explicit recovery.

Backups contain the previous committed state, never an uncommitted command.
Recovery always creates a new file and never changes the damaged source.
"""
from pathlib import Path
from contextlib import contextmanager, ExitStack
import errno
import hashlib
import json
import os

FORMAT='TINDER-SAVE-BACKUP-1'


def digest(raw):return hashlib.sha256(raw).hexdigest()
def encode(state):return json.dumps(state,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')


def _backup_state_digest(state):
    """FORMAT 1 signs the original pretty JSON, independent of file layout."""
    return digest(json.dumps(state,ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8'))
def backup_path(path):return Path(str(Path(path).resolve())+'.bak')


@contextmanager
def save_lock(path):
    """Nonblocking OS lock covering one save's check/backup/replace transaction.

    Keep the sidecar in place: unlinking it can split waiters across different
    files. The OS owns the lock lifetime, so an exited process leaves no stale
    ownership to guess from a PID or an expiry timestamp. This is not reentrant.
    """
    path=Path(path).resolve()
    path.parent.mkdir(parents=True,exist_ok=True)
    with Path(str(path)+'.lock').open('a+b') as handle:
        if os.name=='nt':
            import msvcrt
            if os.fstat(handle.fileno()).st_size==0:
                handle.write(b'\0');handle.flush()
            handle.seek(0)
            acquire=lambda:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            release=lambda:msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            acquire=lambda:fcntl.flock(handle.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            release=lambda:fcntl.flock(handle.fileno(),fcntl.LOCK_UN)
        try:acquire()
        except OSError as exc:
            if exc.errno in (errno.EACCES,errno.EAGAIN,errno.EDEADLK):
                raise ValueError('存档正在被其他操作使用；本次未提交，请稍后重新读取再试。') from exc
            raise
        try:yield
        finally:
            if os.name=='nt':handle.seek(0)
            release()


def _nonfinite(value):
    raise ValueError('存档含非有限数值：'+value)


def _read_unlocked(path):
    path=Path(path)
    try:
        raw=path.read_bytes();state=json.loads(raw.decode('utf-8'),parse_constant=_nonfinite)
        if not isinstance(state,dict):raise ValueError('根对象不是存档')
    except (UnicodeError,json.JSONDecodeError,ValueError) as exc:
        raise ValueError(f'存档无法解析：{path}。原件未改动；可运行 save_tools.py inspect 检查备份。') from exc
    return raw,state


def read(path):
    with save_lock(path):return _read_unlocked(path)


def write_sidecar(path,payload):
    """Atomic non-rollback sidecar used by explicit retry checkpoints."""
    path=Path(path).resolve();raw=encode(payload)
    with save_lock(path):
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_name(path.name+'.tmp')
        try:
            temporary.write_bytes(raw);os.replace(temporary,path)
        except Exception:
            temporary.unlink(missing_ok=True);raise


def read_sidecar(path):
    with save_lock(path):
        return _read_unlocked(path)[1]


def save(game,writer):
    with save_lock(game.save_path):return _save_unlocked(game,writer)


def _save_unlocked(game,writer):
    path=Path(game.save_path).resolve();key=str(path);new=encode(game.s)
    previous=getattr(game,'_disk_snapshot',None)
    if path.exists():
        old=path.read_bytes()
        if previous!=(key,digest(old)):
            raise ValueError('目标存档已存在或被其他进程改动；拒绝覆盖。请重新读取，或指定新的存档路径。')
        if old==new:return  # Read-only commands do not rotate the safety copy.
        old_state=json.loads(old.decode('utf-8'))
        writer(backup_path(path),{'format':FORMAT,'source_path':key,
               'sha256':_backup_state_digest(old_state),'state':old_state})
    elif (previous and previous[0]==key) or backup_path(path).exists():
        raise ValueError('原存档已丢失，保留现有备份；请先使用 save_tools.py 检查和恢复到新文件。')
    writer(path,game.s)
    game._disk_snapshot=(key,digest(new))


def validate_state(loader,state):
    try:return loader.from_state(state)
    except (KeyError,TypeError,IndexError,AttributeError) as exc:
        raise ValueError('存档结构不完整或字段类型异常；不能继续读取。') from exc


def _load_backup_unlocked(path,loader):
    _,row=_read_unlocked(backup_path(path))
    if row.get('format')!=FORMAT or row.get('source_path')!=str(Path(path).resolve()):
        raise ValueError('备份来源不匹配；不能用于此存档。')
    state=row.get('state')
    if not isinstance(state,dict) or row.get('sha256')!=_backup_state_digest(state):
        raise ValueError('备份内容校验失败，保留原件。')
    return validate_state(loader,state)


def load_backup(path,loader):
    with save_lock(path):return _load_backup_unlocked(path,loader)


def inspect(path,loader):
    with save_lock(path):return _inspect_unlocked(path,loader)


def _inspect_unlocked(path,loader):
    path=Path(path);rows=[]
    for kind,candidate in [('primary',path),('backup',backup_path(path))]:
        try:
            if kind=='primary':
                _,state=_read_unlocked(path);game=validate_state(loader,state)
            else:game=_load_backup_unlocked(path,loader)
            s=game.s
            rows.append(dict(kind=kind,path=str(candidate),readable=True,id=s['id'],
                             version=s['version'],sequence=s['sequence'],day=s['day'],phase=s['phase'],
                             developer_only=bool(s.get('developer_drill_only'))))
        except (OSError,ValueError) as exc:
            rows.append(dict(kind=kind,path=str(candidate),readable=False,reason=str(exc)))
    return rows


def recover(path,output,loader):
    path=Path(path).resolve();output=Path(output).resolve()
    if output.resolve() in (path.resolve(),backup_path(path).resolve()) or output.exists():
        raise ValueError('恢复目标必须是新文件，不能覆盖原存档、备份或已有文件。')
    # Both source generations and target creation stay protected. A busy lock
    # fails without waiting, while the fixed order also makes ownership clear.
    with ExitStack() as locks:
        for target in sorted((path,output),key=lambda p:os.path.normcase(str(p.resolve()))):
            locks.enter_context(save_lock(target))
        if output.exists():
            raise ValueError('恢复目标必须是新文件，不能覆盖原存档、备份或已有文件。')
        return _recover_unlocked(path,output,loader)


def _recover_unlocked(path,output,loader):
    # A healthy current save is not a player-facing rollback menu. Different
    # versions/modes must use their matching runtime, not bypass it via backup.
    try:
        _,state=_read_unlocked(path)
    except (FileNotFoundError,ValueError):state=None
    if state is not None:
        from engine import VERSION
        if state.get('version')!=VERSION:
            raise ValueError('原存档版本不匹配，请使用匹配程序；恢复不执行版本迁移。')
        if bool(state.get('developer_drill_only'))!=loader.developer_drills:
            raise ValueError('原存档属于不同入口，不能通过恢复互载。')
        from data import Catalog
        cat=Catalog()
        for key,expected in [('source_sha256',cat.hashes),('runtime_sha256',cat.runtime_hashes)]:
            if key in state and state[key]!=expected:
                raise ValueError('原存档的规则或代码不匹配，请使用匹配程序；恢复不能绕过版本校验。')
        try:validate_state(loader,state)
        except ValueError:pass
        else:raise ValueError('主存档仍然有效，请正常读取；恢复不用于回退已提交的选择。')
    game=_load_backup_unlocked(path,loader)
    output.parent.mkdir(parents=True,exist_ok=True)
    # Exclusive creation prevents an existing destination being overwritten.
    created=False
    try:
        with output.open('xb') as handle:
            created=True;handle.write(encode(game.s));handle.flush();os.fsync(handle.fileno())
    except Exception:
        if created:output.unlink(missing_ok=True)
        raise
    return dict(output=str(output),id=game.s['id'],sequence=game.s['sequence'],
                day=game.s['day'],phase=game.s['phase'],source_untouched=True,
                notice='已恢复上一份提交；其后的操作可能未保留。原件和备份均未修改。')
