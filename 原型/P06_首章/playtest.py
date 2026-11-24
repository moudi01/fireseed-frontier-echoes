"""Open an isolated P06 playtest or resume it with its recorded candidate."""

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import file_digest, sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep
from uuid import uuid4
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parent
PLAYTESTS = ROOT.parents[1] / 'local/p06_playtest'
CASE = 'review'
RELEASE = re.compile(r'windows-\d{8}-\d{6}-[a-f0-9]{6}')
SAVE_FILES = ('save.json', 'save.json.bak', 'save.json.finale_retry.json')
SESSION_TEMPORARIES = ('ledger.next', 'save.json.finale_retry.json.tmp')
SAVE_TEMPORARY = re.compile(r'save\.json(?:\.bak)?\.[0-9a-f]{32}\.tmp')
WINDOWS_FAULT_POLL_TIMES = (0, 0.3, 1.0, 2.0, 3.8)
WINDOWS_FAULT_WAIT_SECONDS = 5
SCENES = (
    'chapter', 'chapter-book-readers', 'chapter-books', 'archive-review',
    'archive', 'town', 'overlook', 'scouting-exit',
    'road', 'root', 'ado', 'ado-warning',
    'ado-roll-call', 'ado-report', 'ado-remembrance', 'ado-return',
    'guard', 'trench', 'dry-island', 'tidal-yard',
    'north-levee', 'wetland-map', 'shallow-bay', 'north-gap',
    'watchtower-gate', 'missing-search', 'missing-pair', 'transfer-yard',
    'spear', 'skeletons', 'spoils', 'handbook',
    'bookstore', 'book-slot-swap', 'book-target', 'book-research',
    'construction', 'logistics', 'consumables',
)

RECOVER_BACKUP = """
import json
from pathlib import Path
import sys

sys.stderr.reconfigure(encoding='utf-8')
package, primary, output = map(Path, sys.argv[1:])
sys.path.insert(0, str(package))
from stage_runtime import verify_inputs

try:
    manifest = json.loads((package / 'input_manifest.json').read_bytes())
    verify_inputs(manifest, package / 'vendor')
    sys.path.insert(0, str(package / 'vendor/原型/火种计划_远征灰盒'))
    from deployment import DeploymentGame
    from save_storage import recover, save_lock
    with save_lock(primary.parent / 'session'):
        receipt = recover(primary, output, DeploymentGame)
except (OSError, ValueError) as error:
    raise SystemExit(str(error))
print(json.dumps(receipt, ensure_ascii=True))
"""


def prepare_recovery(sidecar, primary, target):
    PLAYTESTS.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='.p06-recovery-', dir=PLAYTESTS) as temporary:
        validated = Path(temporary) / 'save.json'
        process = subprocess.run([str(sidecar / 'runtime/python.exe'), '-B', '-I', '-c', RECOVER_BACKUP,
                                  str(sidecar), str(primary), str(validated)],
                                 capture_output=True, encoding='utf-8', timeout=30)
        if process.returncode:
            raise ValueError(process.stderr.strip() or '匹配的运行时未能读取备份。')
        recovery = json.loads(process.stdout)
        if not recovery.get('source_untouched') or not validated.is_file():
            raise ValueError('运行时未生成校验后的备份存档。')
        target.parent.mkdir(parents=True)
        shutil.copyfile(validated, target)
    return {'SourceSession': str(primary.parents[2]), 'Sequence': recovery['sequence'],
            'Day': recovery['day'], 'Phase': recovery['phase']}


def session_case(directory):
    directory = directory.resolve(strict=True)
    case = directory / 'runs' / CASE
    if not case.is_dir() or case.resolve() != case:
        raise ValueError(f'未找到试玩存档目录 {directory}')
    return directory, case


def session(args):
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}"
    release = args.release
    scene = args.scene or 'ado'
    seed = None
    original = args.resume or args.recover
    if original:
        original, source_case = session_case(original)
        record = original / 'playtest.json'
        if record.is_file():
            previous = json.loads(record.read_text(encoding='utf-8-sig'))
            if not isinstance(previous, dict) or not all(isinstance(previous.get(key), str) for key in ('Scene', 'Release')):
                raise ValueError('试玩会话的候选包记录无法读取。')
            release, scene = previous['Release'], previous['Scene']
        else:
            scene = re.sub(r'-\d{8}-\d{6}-[a-f0-9]{8}$', '', original.name)
        data = original if args.resume else PLAYTESTS / f'recovered-{stamp}'
    else:
        data = PLAYTESTS / f'{scene}-{stamp}'
        if scene != 'chapter':
            seed = ROOT / 'playtest_seeds' / (scene + '.json')
            if not seed.is_file():
                raise FileNotFoundError(f'未找到 {scene} 的起始存档 {seed}')

    if not isinstance(release, str) or not RELEASE.fullmatch(release):
        raise ValueError(f'候选包编号无效 {release}')
    package = ROOT / 'build' / release
    exe = package / 'P06.exe'
    for file in (exe, package / 'sidecar/runtime/python.exe'):
        if not file.is_file():
            raise FileNotFoundError(f'未找到试玩包文件 {file}')
    save = data / 'runs' / CASE / 'save.json'
    recovery = None
    if not args.resume:
        metadata = {'Release': release, 'Scene': scene}
        if args.recover:
            recovery = prepare_recovery(package / 'sidecar', source_case / 'save.json', save)
            metadata['Recovery'] = recovery
        else:
            save.parent.mkdir(parents=True)
            if seed:
                shutil.copyfile(seed, save)
        (data / 'playtest.json').write_text(json.dumps(metadata, ensure_ascii=False) + '\n', encoding='utf-8')
    log = data / 'logs' / f'{stamp}.log'
    return {'Scene': scene, 'Release': release, 'Executable': exe, 'DataDirectory': data,
            'Log': log, 'ExitReport': log.with_suffix('.exit.json'), 'Seed': seed, 'Save': save,
            'Recovery': recovery}


def unique_json_fields(items):
    record = {}
    for key, value in items:
        if key in record:
            raise ValueError(f'Duplicate JSON field: {key}')
        record[key] = value
    return record


def read_record(path, *, pending=False):
    try:
        if pending:
            with path.open('rb') as stream:
                raw = stream.read(65537)
            if len(raw) > 65536:
                return {}, 'invalid', None
        else:
            raw = path.read_bytes()
    except FileNotFoundError:
        return {}, 'missing', None
    except OSError:
        return {}, 'unreadable', None
    try:
        record = json.loads(raw, object_pairs_hook=unique_json_fields if pending else None)
    except (ValueError, RecursionError):
        return {}, 'invalid', raw
    if not isinstance(record, dict):
        return {}, 'invalid', raw
    return record, 'readable', raw


def save_location(state):
    battle = state.get('battle') if state.get('phase') == 'BATTLE' else None
    reports = state.get('battle_reports')
    last_battle = reports[-1] if isinstance(reports, list) and reports else None
    result = {label: state.get(key) for label, key in (
        ('Phase', 'phase'), ('Region', 'region'), ('Site', 'site'), ('DomainSequence', 'sequence'))}
    for label, row in (('LiveBattle', battle), ('LastFinishedBattle', last_battle)):
        result[label] = (
            {key: row.get(key) for key in ('encounter_id', 'battle_id', 'tick', 'result')}
            if isinstance(row, dict) else None
        )

    return result


def file_stamp(path):
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    except OSError:
        return 'unreadable'
    return (stat.st_ino, stat.st_size, stat.st_mtime_ns)


def signed_file(path):
    try:
        with path.open('rb') as stream:
            return 'readable', file_digest(stream, 'sha256').hexdigest()
    except FileNotFoundError:
        return 'missing', None
    except OSError:
        return 'unreadable', None


def interrupted_writes(case):
    names = {name for name in SESSION_TEMPORARIES if file_stamp(case / name) is not None}
    names.update(path.name for path in case.glob('save.json.*.tmp') if SAVE_TEMPORARY.fullmatch(path.name))
    return names


def match_ledger(ledger, ledger_status, state, files, temporary, changing):
    if changing:
        return 'files-changing'
    if temporary:
        return 'interrupted-write'
    if ledger_status == 'missing':
        return 'missing'
    if ledger_status != 'readable':
        return ledger_status
    entries = ledger.get('entries')
    version = ledger.get('version')
    if ledger.get('format') != 'P03-LEDGER-1' or not isinstance(entries, dict) or type(version) is not int or version < 0:
        return 'invalid-ledger'
    statuses = [row.get('status') if isinstance(row, dict) else None for row in entries.values()]
    if 'PREPARED' in statuses:
        return 'unresolved-command'
    if any(status not in ('COMMITTED', 'REJECTED') for status in statuses) or statuses.count('COMMITTED') != version:
        return 'invalid-ledger'
    head = ledger.get('head')
    if version == 0 and head is None and not entries:
        return 'no-commits'
    if (isinstance(head, dict) and head.get('files') == files and isinstance(state.get('id'), str)
            and type(state.get('sequence')) is int
            and head.get('game_id') == state['id'] and head.get('domain_sequence') == state.get('sequence')):
        return 'hash-matches-head'
    return 'head-not-matched'


def pending_outcome(pending, pending_status, temporary_status, ledger, observed):
    if temporary_status != 'missing':
        return {'Status': 'interrupted-pending-write'}
    if pending_status != 'readable':
        return {'Status': pending_status}
    request_id = pending.get('request_id')
    if (not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', request_id)
            or pending.get('op') != 'execute' or type(pending.get('protocol_version')) is not int
            or pending['protocol_version'] != 1
            or not isinstance(pending.get('command'), str) or not isinstance(pending.get('args'), list)
            or not all(isinstance(arg, str) for arg in pending['args'])
            or type(pending.get('expected_version')) is not int or pending['expected_version'] < 0):
        return {'Status': 'invalid-pending-request'}
    if observed['LedgerCheck'] in ('files-changing', 'interrupted-write'):
        return {'Status': 'unverified'}
    entries = ledger.get('entries')
    row = entries.get(request_id) if isinstance(entries, dict) else None
    if row is None:
        if observed['Status'] == 'readable' and observed['LedgerCheck'] in ('hash-matches-head', 'no-commits'):
            if pending['expected_version'] != ledger.get('version', 0):
                return {'Status': 'request-version-mismatch'}
            return {'Status': 'not-recorded'}
        return {'Status': 'unverified'}
    payload = {key: pending[key] for key in ('protocol_version', 'command', 'args')}
    try:
        payload_bytes = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    except UnicodeError:
        return {'Status': 'invalid-pending-request'}
    signature = sha256(payload_bytes).hexdigest()
    if not isinstance(row, dict) or row.get('request') != pending or row.get('payload_hash') != signature:
        return {'Status': 'request-mismatch'}
    if row.get('status') == 'PREPARED':
        return {'Status': 'prepared-unresolved'}
    if observed['LedgerCheck'] != 'hash-matches-head':
        return {'Status': 'unverified'}
    response = row.get('response')
    status = row.get('status')
    if (not isinstance(response, dict) or response.get('status') != status or response.get('request_id') != request_id
            or type(response.get('state_version')) is not int or not 0 <= response['state_version'] <= observed['ConfirmedVersion']
            or response.get('game_id') != ledger['head']['game_id']):
        return {'Status': 'unverified'}
    version = response['state_version']
    if version == observed['ConfirmedVersion'] and any(
            response.get(key) != ledger['head'].get(key) for key in ('files', 'domain_sequence', 'state_digest')):
        return {'Status': 'unverified'}
    if status == 'COMMITTED' and version == pending['expected_version'] + 1:
        ack = response.get('persistence_ack')
        if isinstance(ack, dict) and ack.get('basis') == 'COMMITTED_RESULT_LEDGER' and all(
                ack.get(key) == response.get(key) for key in ('request_id', 'state_version', 'state_digest', 'files')):
            return {'Status': 'committed', 'ReceiptVersion': version}
    elif status == 'REJECTED' and version == pending['expected_version']:
        return {'Status': 'rejected', 'ReceiptVersion': version}
    return {'Status': 'unverified'}


def observe_session(data, save):
    pending_path = data / f'{CASE}.pending.json'
    pending_tmp = pending_path.with_suffix('.json.tmp')
    ledger_path = save.with_name('ledger.json')
    watched = [save.with_name(name) for name in SAVE_FILES] + [ledger_path, pending_path, pending_tmp]
    first_markers = interrupted_writes(save.parent)
    first = {path: file_stamp(path) for path in watched}
    ledger, ledger_status, _ = read_record(ledger_path)
    state, save_status, raw = read_record(save)
    observed = {'Status': save_status, 'SHA256': sha256(raw).hexdigest() if raw is not None else None}
    if save_status == 'readable':
        observed.update(save_location(state))
    file_set = {save.name: (save_status, observed['SHA256'])}
    file_set.update({name: signed_file(save.with_name(name)) for name in SAVE_FILES if name != save.name})
    pending, pending_status, _ = read_record(pending_path, pending=True)
    _, temporary_status, _ = read_record(pending_tmp, pending=True)
    last = {path: file_stamp(path) for path in watched}
    temporary = sorted(first_markers | interrupted_writes(save.parent))
    files = {name: digest for name, (_, digest) in file_set.items()}
    observed.update(Files={name: {'Status': status, 'SHA256': digest} for name, (status, digest) in file_set.items()},
                    LedgerCheck=match_ledger(ledger, ledger_status, state, files, temporary, first != last),
                    InterruptedWrites=temporary)
    if observed['LedgerCheck'] == 'hash-matches-head':
        if save_status == 'readable' and all(status in ('readable', 'missing') for status, _ in file_set.values()):
            observed['ConfirmedVersion'] = ledger['version']
        else:
            observed['LedgerCheck'] = 'unreadable-file-set'
    raw_pending = {'Status': pending_status, 'TemporaryStatus': temporary_status,
                   **{key: pending[key] for key in ('request_id', 'command', 'expected_version') if key in pending}}
    return {'ObservedSave': observed, 'ObservedPending': raw_pending,
            'PendingOutcome': pending_outcome(pending, pending_status, temporary_status, ledger, observed),
            'BackupPresent': file_set['save.json.bak'][0] != 'missing'}


def engine_log_summary(log):
    result = {'RuntimePID': None, 'RuntimeLog': None, 'GracefulCloseLogged': False,
              'CloseReason': None, 'ModelLoadsAtClose': None, 'LastLoggedLocation': None}
    try:
        with log.open(encoding='utf-8', errors='replace') as stream:
            for line in stream:
                runtime = re.fullmatch(r'P06 runtime pid=(\d+) log=(.+)\n?', line)
                if runtime:
                    result.update(RuntimePID=int(runtime[1]), RuntimeLog=str(log.parent / Path(runtime[2]).name))
                elif line.startswith('P06 exit version='):
                    result['GracefulCloseLogged'] = True
                    close = re.search(r' reason=(\w+) active_models=(\d+) queued_models=(\d+)$', line.rstrip())
                    if close:
                        result['CloseReason'] = close[1]
                        result['ModelLoadsAtClose'] = {'Active': int(close[2]), 'Queued': int(close[3])}
                elif line.startswith('P06 state version='):
                    location = re.fullmatch(
                        r'P06 state version=(-?\d+) phase=(\S*) region=(\S*) site=(\S*) encounter=(\S*) tick=(-?\d+)',
                        line.rstrip('\r\n'))
                    if location:
                        result['LastLoggedLocation'] = {
                            'Version': int(location[1]), 'Phase': location[2],
                            'Region': None if location[3] in ('', '<null>') else location[3],
                            'Site': None if location[4] in ('', '<null>') else location[4],
                            'Encounter': location[5] or None, 'Tick': None if location[6] == '-1' else int(location[6]),
                        }
    except OSError:
        pass
    return result


def matching_fault_event(xml, executable, pid, exit_status):
    for event in ElementTree.fromstring(xml).findall('{*}Event'):
        system = event.find('{*}System')
        if system is None:
            continue
        provider = system.find('{*}Provider')
        if provider is None or provider.get('Name') != 'Application Error' or system.findtext('{*}EventID') != '1000':
            continue
        data = event.findall('{*}EventData/{*}Data')
        fields = {field.get('Name'): field.text or '' for field in data if field.get('Name')}
        if not fields and system.findtext('{*}Version') == '0' and len(data) == 15:
            # Application Error v0 can expose the event payload as unnamed strings.
            positions = {'ModuleName': 3, 'ExceptionCode': 6, 'FaultingOffset': 7, 'ProcessId': 8, 'AppPath': 10}
            fields = {key: data[index].text or '' for key, index in positions.items()}
        if os.path.normcase(fields.get('AppPath', '')) != os.path.normcase(str(executable)):
            continue
        try:
            event_pid = int(fields.get('ProcessId', ''), 16)
            exception_code = int(fields.get('ExceptionCode', ''), 16)
            offset = int(fields.get('FaultingOffset', ''), 16)
        except ValueError:
            continue
        if event_pid != pid or exception_code != exit_status:
            continue
        time = system.find('{*}TimeCreated')
        return {'EventRecordID': system.findtext('{*}EventRecordID'),
                'EventTimeUTC': time.get('SystemTime') if time is not None else None,
                'Module': fields.get('ModuleName') or None, 'ExceptionCode': f'0x{exception_code:08X}',
                'ModuleOffset': f'0x{offset:X}'}
    return None


def should_check_windows_fault(pid, exit_status):
    return os.name == 'nt' and pid is not None and (exit_status & 0xC0000000) == 0xC0000000


def windows_fault_report(executable, pid, exit_status, started_at, exited_at):
    if not should_check_windows_fault(pid, exit_status):
        return None
    start = started_at.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    end = (exited_at.astimezone(timezone.utc) + timedelta(seconds=WINDOWS_FAULT_WAIT_SECONDS))
    end = end.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    query = ("*[System[Provider[@Name='Application Error'] and EventID=1000 "
             f"and TimeCreated[@SystemTime >= '{start}' and @SystemTime <= '{end}']] "
             "and EventData[Data='P06.exe']]")
    utility = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/wevtutil.exe'
    command = [str(utility), 'qe', 'Application', f'/q:{query}', '/c:32', '/rd:true',
               '/f:xml', '/e:Events', '/uni:true']
    started = monotonic()
    deadline = started + WINDOWS_FAULT_WAIT_SECONDS
    status = 'unavailable'
    for poll_time in WINDOWS_FAULT_POLL_TIMES:
        delay = started + poll_time - monotonic()
        if delay > 0:
            sleep(delay)
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        try:
            result = subprocess.run(command, capture_output=True, check=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW, timeout=min(2, remaining))
            event = matching_fault_event(result.stdout, executable, pid, exit_status)
        except (OSError, subprocess.SubprocessError, ElementTree.ParseError):
            status = 'unavailable'
        else:
            if event:
                return {'Status': 'matched', 'Event': event}
            status = 'no-match'
    return {'Status': status, 'Event': None}


def write_exit_report(report_path, report):
    try:
        temporary = report_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        for delay in (0.05, 0.10, None):
            try:
                temporary.replace(report_path)
                break
            except OSError as error:
                # A reader on Windows can briefly block replacement of the first report.
                if delay is None or getattr(error, 'winerror', None) not in (5, 32, 33):
                    raise
                sleep(delay)
    except (OSError, ValueError, RecursionError) as error:
        print(f'退出记录写入失败。{error}', file=sys.stderr)


def run_playtest(setup):
    log = setup['Log']
    log.parent.mkdir(exist_ok=True)
    report_path = setup['ExitReport']
    print(f"存档目录 {setup['DataDirectory']}\n本次日志 {log}\n退出记录 {report_path}", flush=True)
    if setup['Recovery']:
        print(f"已恢复备份的第 {setup['Recovery']['Day']} 行动日。备份之后的操作可能未保留。", flush=True)
    exe = setup['Executable']
    data = setup['DataDirectory']
    started = monotonic()
    started_at = datetime.now().astimezone()
    process_id = None
    launch_error = None
    try:
        process = subprocess.Popen([str(exe), '--log-file', str(log), '--', f'--case={CASE}',
                                    f'--data={data}'], cwd=exe.parent)
    except OSError as error:
        launch_error = str(error)
        print(f'未能启动 P06.exe。{error}', file=sys.stderr)
        code = 1
    else:
        process_id = process.pid
        code = process.wait()
    exit_status = code & 0xFFFFFFFF
    exited_at = datetime.now().astimezone()
    elapsed_ms = round((monotonic() - started) * 1000)
    observation = observe_session(data, setup['Save'])
    observation['PendingAtExit'] = observation.pop('ObservedPending')
    check_windows_fault = should_check_windows_fault(process_id, exit_status)
    report = {
        'Release': setup['Release'], 'Executable': str(exe), 'Scene': setup['Scene'], 'PID': process_id,
        'StartedAt': started_at.isoformat(timespec='seconds'),
        'ExitedAt': exited_at.isoformat(timespec='seconds'),
        'ElapsedMs': elapsed_ms,
        'ExitCode': exit_status, 'ExitCodeHex': f'0x{exit_status:08X}', 'LaunchError': launch_error,
        'Log': str(log), 'Save': str(setup['Save']),
        **observation, **engine_log_summary(log),
        'WindowsFault': {'Status': 'checking', 'Event': None} if check_windows_fault else None,
        'ResumeDirectory': str(data),
        'Recovery': setup['Recovery'],
    }
    write_exit_report(report_path, report)
    if exit_status:
        print(f"P06 退出码 {report['ExitCodeHex']}，退出记录位于本次日志旁。", file=sys.stderr, flush=True)
    if check_windows_fault:
        report['WindowsFault'] = windows_fault_report(exe, process_id, exit_status, started_at, exited_at)
        write_exit_report(report_path, report)
    # Windows process statuses are unsigned, while SystemExit takes a signed C int.
    return exit_status if exit_status < 2**31 else exit_status - 2**32


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--scene', choices=SCENES)
    mode.add_argument('--resume', type=Path)
    mode.add_argument('--recover', type=Path, help='从损坏会话的已校验备份新建试玩会话')
    mode.add_argument('--inspect', type=Path, help='只读检查主档、事务账本和待确认请求')
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    try:
        if args.inspect:
            if args.prepare_only:
                parser.error('--inspect 自带只读检查，无需 --prepare-only')
            data, case = session_case(args.inspect)
            save = case / 'save.json'
            print(json.dumps({'DataDirectory': str(data), 'Save': str(save), **observe_session(data, save)}, indent=2))
            return 0
        setup = session(args)
    except (OSError, ValueError, KeyError, subprocess.TimeoutExpired) as error:
        parser.exit(2, f'P06 试玩入口：{error}\n')
    if args.prepare_only:
        print(json.dumps(setup, default=str))
        return 0
    return run_playtest(setup)


if __name__ == '__main__':
    raise SystemExit(main())
