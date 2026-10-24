"""Observe only the isolated USB fixture, without starting the phone app or verifier."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=['long', 'recovery'])
    parser.add_argument('--screen-off-seconds', type=int, default=900)
    parser.add_argument('--timeout-seconds', type=int, default=1200)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    adb = root / '.tooling/android-sdk/platform-tools/adb.exe'
    package = 'com.ideaecho.app.acceptance'

    def command(*parts):
        return subprocess.run([str(adb), *parts], capture_output=True, text=True, timeout=15)

    fixture = command('exec-out', 'run-as', package, 'cat', f'files/background-{args.phase}.json')
    fixture.check_returncode()
    prepared = json.loads(fixture.stdout)
    initial_process_absent = not command('shell', 'pidof', package).stdout.strip()
    started = time.monotonic()
    asleep_since = None
    with httpx.Client(base_url='http://127.0.0.1:47841', trust_env=False, timeout=5) as client:
        login = client.post('/v1/auth/login', json={'username': 'device-test', 'password': 'device-test-only-password'})
        login.raise_for_status()
        owner = login.json()['account_id']
        client.headers['Authorization'] = 'Bearer ' + login.json()['token']
        key = hashlib.sha256(('http://127.0.0.1:47841\n' + owner).encode()).hexdigest()
        while time.monotonic() - started < args.timeout_seconds:
            power = command('shell', 'dumpsys', 'power')
            asleep = re.search(r'mWakefulness=Asleep\b', power.stdout) is not None
            now = time.monotonic()
            if asleep and asleep_since is None:
                asleep_since = now
            if not asleep:
                asleep_since = None
            changes = client.get('/v1/changes?after=0')
            changes.raise_for_status()
            records = [e for e in changes.json()['events'] if e['kind'] == 'record' and e['entity_id'] == prepared['idea_id']]
            assert len(records) <= 1, 'Duplicate test record event'
            preferences = command('exec-out', 'run-as', package, 'cat', 'shared_prefs/sync-status.xml')
            success_at = 0
            error = ''
            if preferences.returncode == 0:
                values = {e.attrib['name']: e.attrib.get('value', e.text or '') for e in ET.fromstring(preferences.stdout)}
                success_at = int(values.get(key + '-success', 0))
                error = values.get(key + '-error', '')
            verified_images = 0
            if records:
                for image in records[0]['payload']['attachments']:
                    response = client.get('/v1/attachments/' + image['id'])
                    response.raise_for_status()
                    remote = response.json()
                    if remote['content_ready'] and remote['sha256'] == image['sha256']:
                        verified_images += 1
            screen_off_duration = now - asleep_since if asleep_since is not None else 0
            if (len(records) == 1 and verified_images == 2 and not error
                    and success_at >= prepared['prepared_at'] and screen_off_duration >= args.screen_off_seconds):
                result = {
                    'phase': args.phase, 'idea_id': prepared['idea_id'], 'work_id': prepared['work_id'],
                    'prepared_at': prepared['prepared_at'], 'not_before': prepared['not_before'],
                    'last_success_at': success_at, 'observed_at_utc': datetime.now(timezone.utc).isoformat(),
                    'continuous_screen_off_seconds': int(screen_off_duration),
                    'process_absent_at_observation_start': initial_process_absent,
                    'test_record_events': 1, 'verified_images': 2, 'observed_before_verifier': True,
                }
                args.output.parent.mkdir(parents=True, exist_ok=True)
                with args.output.open('x', encoding='utf-8') as destination:
                    json.dump(result, destination, indent=2)
                print(json.dumps(result), flush=True)
                return
            time.sleep(10)
    raise SystemExit('Timed out: unattended background completion was not established')


if __name__ == '__main__':
    main()
