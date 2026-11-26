"""Recover a Windows release backup into a separate, playable P06 slot."""
from argparse import ArgumentParser
from datetime import datetime
import json
import os
from pathlib import Path
import re
from subprocess import Popen
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4


SIDECAR = Path(__file__).resolve().parent
PACKAGE = SIDECAR.parent
EXE = PACKAGE / 'P06.exe'
RUNTIME = SIDECAR / 'runtime/python.exe'
RUNS = PACKAGE / 'data/runs'
VENDOR = SIDECAR / 'vendor'


def slot_path(name):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', name) or os.path.isreserved(name):
        raise ValueError('槽名须使用 1–80 位英文字母、数字、下划线或短横线，且须是 Windows 可用名称。')
    for directory in (RUNS.parent, RUNS, RUNS / name):
        if directory.is_symlink() or directory.is_junction():
            raise ValueError(f'存档目录不能使用链接或目录联接：{directory.name}')
    return RUNS / name


def regular_file(path):
    if path.is_symlink() or path.is_junction() or not path.is_file():
        raise ValueError(f'找不到可读取的普通文件：{path}')
    return path


def load_authority():
    sys.path.insert(0, str(SIDECAR))
    from stage_runtime import verify_inputs

    manifest = json.loads((SIDECAR / 'input_manifest.json').read_bytes())
    verify_inputs(manifest, VENDOR)
    sys.path.insert(0, str(VENDOR / '原型/火种计划_远征灰盒'))
    from deployment import DeploymentGame
    import save_storage

    return DeploymentGame, save_storage


def validate_campaign(state, loader, storage):
    if not state.get('campaign') or state.get('developer_drill_only'):
        raise ValueError('备份不属于本包可读取的正常战役会话。')
    rules = state.get('source_sha256')
    runtime = state.get('runtime_sha256')
    game = storage.validate_state(loader, state)
    if rules != game.cat.hashes or runtime != game.cat.runtime_hashes:
        raise ValueError('备份的规则或运行时版本不符；请保留备份并使用匹配的游戏包。')
    return game.s


def recover_here(source, output, loader, storage):
    primary = source / 'save.json'
    if primary.exists() or primary.is_symlink() or primary.is_junction():
        regular_file(primary)
    regular_file(source / 'save.json.bak')
    with storage.save_lock(source / 'session'):
        try:
            storage.recover(primary, output, loader)
        except (ValueError, RecursionError) as error:
            if not isinstance(error, RecursionError) and 'save_tools.py' not in str(error):
                raise
            raise ValueError('备份无法解析。请保留原文件，并核对选用的备份。') from error
    _, state = storage._read_unlocked(output)
    validate_campaign(state, loader, storage)


def import_backup(backup, output, loader, storage):
    # The explicitly chosen directory is the only place consulted. A recorded
    # source_path is metadata, never a filesystem input to the import.
    backup = regular_file(backup.expanduser()).resolve(strict=True)
    primary = backup.parent / 'save.json'
    if primary.exists() or primary.is_symlink() or primary.is_junction():
        raise ValueError('所选备份的目录中已有主档。主档可读时请直接续玩；主档损坏时请选择原位置恢复。')
    _, state = read_backup(backup, loader, storage)
    write_primary(output, state, storage)


def read_backup(backup, loader, storage):
    try:
        raw, row = storage._read_unlocked(backup)
    except (ValueError, RecursionError) as error:
        raise ValueError('所选备份无法解析。请保留原文件，并核对选用的备份。') from error
    if row.get('format') != storage.FORMAT or not isinstance(row.get('source_path'), str) or not row['source_path']:
        raise ValueError('所选文件不是此游戏的备份格式。')
    state = row.get('state')
    if not isinstance(state, dict) or row.get('sha256') != storage._backup_state_digest(state):
        raise ValueError('备份内容校验失败；原文件已保留。')
    return storage.digest(raw), validate_campaign(state, loader, storage)


def write_primary(output, state, storage):
    with output.open('xb') as stream:
        stream.write(storage.encode(state))
        stream.flush()
        os.fsync(stream.fileno())


def interrupted_receipt(source):
    from protocol_service import decode_json, request_payload_hash, validate_request

    try:
        ledger = decode_json((source / 'ledger.json').read_bytes())
        version = ledger['version']
        entries = ledger['entries']
        if ledger['format'] != 'P03-LEDGER-1' or type(version) is not int or version < 0:
            raise ValueError()
        pending = [(key, row) for key, row in entries.items() if row['status'] == 'PREPARED']
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise ValueError('原槽事务账本无法核对；请保留原件。') from error
    if not pending:
        raise ValueError('原槽没有未决写档。请正常续玩；主档损坏或丢失时可使用原位置恢复。')
    if len(pending) != 1:
        raise ValueError('原槽有多笔未决记录，无法确定对应备份；请保留原件。')
    key, row = pending[0]
    try:
        request = validate_request(row['request'])
        before = row['before']
        files = before['files']
        head = ledger.get('head')
        if (request['op'] != 'execute' or request['request_id'] != key
                or row['version'] != version or request['expected_version'] != version
                or row['payload_hash'] != request_payload_hash(request)
                or (head != before and not (version == 0 and head is None))
                or not isinstance(files['save.json'], str) or 'save.json.bak' not in files
                or type(before['domain_sequence']) is not int):
            raise ValueError()
        if version > 0:
            receipt, = [entry['response'] for entry in entries.values()
                        if entry['status'] == 'COMMITTED' and entry['version'] == version - 1]
            if receipt['state_version'] != version or any(receipt[k] != before[k] for k in before):
                raise ValueError()
    except (ValueError, TypeError, KeyError, AttributeError) as error:
        raise ValueError('未决请求与对应版本、收据或账本头不符；请保留原件。') from error
    return before


def recover_interrupted(source, output, loader, storage):
    from archive_cache import digest

    lock_file = source / 'session.lock'
    if lock_file.exists() or lock_file.is_symlink() or lock_file.is_junction():
        regular_file(lock_file)
    if not source.is_dir():
        raise ValueError('找不到所选原槽。')
    ledger = source / 'ledger.json'
    if not ledger.exists():
        raise ValueError('原槽没有可核对的未决写档账本。')
    regular_file(ledger)
    if not lock_file.exists():
        # Avoid creating a lock file just to reject a healthy archive copy.
        interrupted_receipt(source)
    with storage.save_lock(source / 'session'):
        regular_file(ledger)
        before = interrupted_receipt(source)
        primary = regular_file(source / 'save.json')
        backup = regular_file(source / 'save.json.bak')
        raw, primary_state = storage._read_unlocked(primary)
        primary_state = validate_campaign(primary_state, loader, storage)
        backup_sha, backup_state = read_backup(backup, loader, storage)

        def matches_before(state):
            return (state['sequence'] == before['domain_sequence']
                    and digest(state, sort_keys=True) == before['state_digest'])

        if primary_state['id'] != before['game_id'] or backup_state['id'] != before['game_id']:
            raise ValueError('主档、备份和未决事务不属于同一周目。')
        # The ledger binds either the still-present old backup or the newly
        # rotated backup containing the authenticated pre-command primary.
        same_primary = storage.digest(raw) == before['files']['save.json']
        if same_primary:
            proven = matches_before(primary_state) and (
                backup_sha == before['files']['save.json.bak'] or matches_before(backup_state))
        else:
            proven = primary_state['sequence'] > before['domain_sequence'] and matches_before(backup_state)
        if not proven:
            raise ValueError('备份与未决请求的提交前状态不符；请保留原件。')
        write_primary(output, backup_state, storage)


def restore(target, *, source=None, backup=None, interrupted=None):
    destination = slot_path(target)
    if destination.exists():
        raise ValueError(f'目标槽 {target} 已存在，请选择新的槽名。')
    loader, storage = load_authority()
    RUNS.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.p06-recovery-', dir=RUNS) as directory:
        staging = Path(directory) / 'validated'
        staging.mkdir()
        output = staging / 'save.json'
        if source is not None:
            recover_here(slot_path(source), output, loader, storage)
        elif interrupted is not None:
            recover_interrupted(slot_path(interrupted), output, loader, storage)
        else:
            import_backup(backup, output, loader, storage)
        # Publish only the validated primary. The migrated slot has its own
        # ledger, and a backup alone does not authenticate a finale retry file.
        lock = staging / 'save.json.lock'
        lock.unlink(missing_ok=True)
        if destination.exists() or destination.is_symlink() or destination.is_junction():
            raise ValueError(f'目标槽 {target} 已存在，请选择新的槽名。')
        staging.rename(destination)  # Windows refuses to replace an existing destination.


def open_slot(name):
    regular_file(slot_path(name) / 'save.json')
    Popen([str(EXE), '--', f'--case={name}'], cwd=PACKAGE)
    print(f'正在打开存档槽 {name}。')


def new_slot_name():
    return f'recovered-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:6]}'


def describe_new_slot(target):
    print(f'已恢复到新槽 {target}。已有的主档、备份和账本均保留。')
    print(f'再次进入该槽：恢复存档.cmd --open {target}，或在恢复菜单中选择打开。')
    print('备份只恢复该次快照。独立的终战重试检查点不会随备份恢复。')


INTERRUPTED_NOTICE = '从原槽备份创建新槽，可能丢失备份之后的进度。原主档、备份、账本和临时文件均保留。'


def menu():
    print('火种计划 · 存档恢复')
    print('1  从原位置备份恢复到新槽（原主档损坏或丢失）')
    print('2  导入搬移后只剩的备份到新槽（须确认）')
    print('3  打开已恢复的新槽')
    print('4  未决写档恢复到新槽（须确认）')
    print('回车退出。')
    choice = input('请选择：').strip()
    if not choice:
        return
    if choice == '3':
        open_slot(input('槽名：').strip())
        return
    if choice not in ('1', '2', '4'):
        raise ValueError('请选择 1、2、3 或 4。')
    source = None
    backup = None
    interrupted = None
    if choice == '1':
        source = input('原槽名（默认 rg01）：').strip() or 'rg01'
    elif choice == '4':
        interrupted = input('原槽名（默认 rg01）：').strip() or 'rg01'
        print(INTERRUPTED_NOTICE)
        if input('输入 RECOVER 确认：').strip() != 'RECOVER':
            print('已取消恢复。')
            return
    else:
        path = input('所选备份文件路径：').strip().strip('"')
        if not path:
            raise ValueError('请选择需要导入的备份文件。')
        print('导入仅适用于搬移后只剩备份的目录，并会新建存档槽。')
        if input('输入 IMPORT 确认导入：').strip() != 'IMPORT':
            print('已取消导入。')
            return
        backup = Path(path)
    target = input('新槽名（回车自动生成）：').strip() or new_slot_name()
    restore(target, source=source, backup=backup, interrupted=interrupted)
    describe_new_slot(target)
    if input('回车打开新槽，输入 N 退出：').strip().lower() != 'n':
        open_slot(target)


def main():
    parser = ArgumentParser(prog='恢复存档.cmd', description='从备份恢复到新槽，原会话保留。')
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--recover', metavar='旧槽名', help='主档损坏或丢失时，使用原位置的备份')
    action.add_argument('--recover-interrupted', metavar='旧槽名', help='从未决写档的原槽恢复，须同时确认')
    action.add_argument('--import-backup', metavar='备份路径', type=Path, help='导入已搬移的备份，须同时确认')
    action.add_argument('--open', metavar='槽名', help='用 P06.exe 打开已有槽')
    parser.add_argument('--target', metavar='新槽名', help='省略时自动生成新槽名')
    parser.add_argument('--confirm-interrupted', action='store_true', help=INTERRUPTED_NOTICE)
    parser.add_argument('--confirm-import', action='store_true', help='明确确认将已搬移的备份导入新槽')
    interactive = len(sys.argv) == 1
    try:
        if Path(sys.executable).resolve() != RUNTIME.resolve() or not EXE.is_file():
            raise ValueError('请双击发布包根目录的恢复存档.cmd，并保留旁边的 P06.exe 和 sidecar 目录。')
        if interactive:
            menu()
        else:
            args = parser.parse_args()
            if args.open is not None:
                if args.target or args.confirm_import or args.confirm_interrupted:
                    parser.error('--open 只接受要打开的槽名。')
                open_slot(args.open)
            else:
                if (args.import_backup is not None) != args.confirm_import:
                    parser.error('导入备份须同时指定 --import-backup 和 --confirm-import。')
                if (args.recover_interrupted is not None) != args.confirm_interrupted:
                    parser.error('未决写档恢复须同时指定 --recover-interrupted 和 --confirm-interrupted。')
                if args.confirm_interrupted:
                    print(INTERRUPTED_NOTICE)
                target = args.target if args.target is not None else new_slot_name()
                restore(target, source=args.recover, backup=args.import_backup, interrupted=args.recover_interrupted)
                describe_new_slot(target)
        return 0
    except (OSError, ValueError, TypeError, KeyError, EOFError, RecursionError) as error:
        print(f'恢复入口：{error}', file=sys.stderr)
        if interactive and sys.stdin.isatty():
            input('回车关闭。')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
