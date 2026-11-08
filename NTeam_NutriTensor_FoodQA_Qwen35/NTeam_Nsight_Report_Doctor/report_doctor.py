#!/usr/bin/env python3
"""Diagnose Nsight report opening; no GPU or project changes.

Usage: python nteam_nsight_report_doctor.py path/to/qwen_vision.nsys-rep
       python nteam_nsight_report_doctor.py path/to/report.ncu-rep --open
"""
import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

NSYS = {'.nsys-rep': 'Nsight Systems', '.qdstrm': 'Nsight Systems intermediate', '.sqlite': 'SQLite statistics export'}
NCU = {'.ncu-rep': 'Nsight Compute', '.ncu-repz': 'Nsight Compute compressed'}


def classify(path: Path) -> str:
    name = path.name.lower()
    for ext in (*NSYS, *NCU):
        if name.endswith(ext):
            return ext
    return 'unknown'


def fmt_bytes(n: int) -> str:
    for unit in ('B', 'KiB', 'MiB', 'GiB'):
        if n < 1024 or unit == 'GiB':
            return f'{n:.1f} {unit}'
        n /= 1024
    return str(n)


def inspection(path: Path) -> tuple[bool, str]:
    if not path.exists():
        return False, f'MISSING: {path}'
    if not path.is_file():
        return False, 'Not a regular file.'
    try:
        with path.open('rb') as handle:
            header = handle.read(32)
        size = path.stat().st_size
    except OSError as exc:
        return False, f'Not readable: {exc}'
    if size == 0:
        return False, 'EMPTY FILE: report generation did not finish.'
    ext = classify(path)
    if ext == '.sqlite':
        if header[:16] != b'SQLite format 3\x00':
            return False, '.sqlite extension, but not a SQLite database.'
        try:
            uri = path.resolve().as_uri() + '?mode=ro'
            con = sqlite3.connect(uri, uri=True)
            try:
                outcome = con.execute('PRAGMA quick_check').fetchone()[0]
            finally:
                con.close()
            if outcome != 'ok':
                return False, f'SQLite integrity check returned: {outcome}'
        except sqlite3.Error as exc:
            return False, f'SQLite read error: {exc}'
        return True, f'Valid SQLite export ({fmt_bytes(size)}). NOT a GUI report.'
    if ext == '.qdstrm':
        return True, f'Intermediate collection file ({fmt_bytes(size)}). Convert using nsys import.'
    if ext == 'unknown':
        return False, f'Unknown extension ({fmt_bytes(size)}). Expected .nsys-rep or .ncu-rep.'
    return True, f'{NSYS.get(ext) or NCU.get(ext)} report exists ({fmt_bytes(size)}).'


def command_path(name: str) -> str | None:
    candidate = shutil.which(name)
    return str(Path(candidate).resolve()) if candidate else None


def run_check(command: list[str], timeout: int = 90) -> tuple[int, str]:
    try:
        p = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=timeout)
        return p.returncode, p.stdout[-4500:]
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 125, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--open', action='store_true', help='Launch the matching GUI after checks')
    parser.add_argument('--refresh-sqlite', action='store_true', help='Re-export stale SQLite using nsys stats')
    args = parser.parse_args()
    path = args.report.expanduser().resolve()
    ext = classify(path)

    print('Nsight Report Doctor')
    print('Report:', path)
    print('Extension:', ext)
    ok, note = inspection(path)
    print('Inspection:', note)
    for name in ('nsys', 'nsys-ui', 'ncu', 'ncu-ui'):
        print(f'{name:7}:', command_path(name) or 'NOT FOUND')
    if not ok:
        print('ACTION: Do not try opening this path until the above condition is fixed.')
        return 2

    if ext == '.sqlite':
        print('ACTION: Open the sibling *.nsys-rep with nsys-ui; SQLite is for stats, not the timeline GUI.')
        return 0
    if ext == '.qdstrm':
        print('ACTION: nsys import --input-file', str(path), '--output-file', str(path.with_suffix('.nsys-rep')))
        return 0

    if ext == '.nsys-rep':
        nsys = command_path('nsys')
        gui = command_path('nsys-ui')
        if nsys:
            code, out = run_check([nsys, '--version'], timeout=15)
            print('nsys --version:', out.strip() if code == 0 else f'ERROR: {out}')
            cmd = [nsys, 'stats', '--report', 'nvtx_sum']
            if args.refresh_sqlite:
                cmd += ['--force-export=true']
            cmd.append(str(path))
            print('Checking with:', ' '.join(cmd))
            rc, result = run_check(cmd)
            print('stats return code:', rc)
            print('stats output (last 4500 chars):\n' + result)
            if rc != 0:
                print('ACTION: CLI cannot parse report. Check version/file corruption; do not overwrite original.')
                return 3
        else:
            print('WARNING: nsys CLI missing; cannot verify report integrity.')
        if not gui:
            print('ACTION: Install Nsight Systems GUI matching your CLI version (or newer).')
            return 4
        print('OPEN WITH:', gui, str(path))
        print('NOTE: nsys-ui GUI should be same/newer than nsys CLI that generated this report.')
    elif ext in ('.ncu-rep', '.ncu-repz'):
        ncu = command_path('ncu')
        gui = command_path('ncu-ui')
        if ncu:
            rc, output = run_check([ncu, '--import', str(path), '--page', 'details'], timeout=90)
            print('ncu import return code:', rc)
            print('ncu output (last 4500 chars):\n' + output)
            if rc != 0:
                print('ACTION: ncu cannot read the report. Verify version, report integrity and file size.')
                return 3
        if not gui:
            print('ACTION: Install Nsight Compute GUI matching the report collector.')
            return 4
        print('OPEN WITH:', gui, str(path))
    else:
        return 2

    if args.open:
        print('Starting GUI...')
        try:
            subprocess.Popen([gui, str(path)], start_new_session=True)
        except OSError as exc:
            print('GUI launch error:', exc)
            return 5
    return 0


if __name__ == '__main__':
    sys.exit(main())
