"""Native systemd backup job; run via its oneshot unit to serialize invocations."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from uuid import uuid4

from idea_echo.backup import create_backup, restore_backup, rotate_backups


def run_once(data_dir: Path, backup_dir: Path) -> dict:
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    staged = backup_dir / f'.pending-{uuid4()}.zip'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    published = backup_dir / f'idea-echo-{stamp}.zip'
    try:
        create_backup(Path(data_dir), staged)
        with tempfile.TemporaryDirectory(prefix='.restore-check-', dir=backup_dir) as trial:
            restore_backup(staged, Path(trial))
        # Same-filesystem atomic publication, refusing to replace an existing backup.
        with staged.open('r+b') as archive:
            os.fsync(archive.fileno())
        os.link(staged, published)
    finally:
        staged.unlink(missing_ok=True)
    removed = rotate_backups(backup_dir)
    return {'file': published.name, 'restore_checked': True, 'removed': len(removed)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path('/var/lib/idea-echo'))
    parser.add_argument('--backup-dir', type=Path, default=Path('/var/lib/idea-echo/backups'))
    args = parser.parse_args()
    os.umask(0o077)
    print(json.dumps(run_once(args.data_dir, args.backup_dir)), flush=True)


if __name__ == '__main__':
    main()
