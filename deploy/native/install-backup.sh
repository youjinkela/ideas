#!/usr/bin/env bash
# Add backups to an existing native installation; never restart the API.
set -euo pipefail
if [[ $(id -u) != 0 ]]; then echo 'Run as root on Ubuntu 24.04.' >&2; exit 1; fi
. /etc/os-release
if [[ ${ID:-} != ubuntu || ${VERSION_ID:-} != 24.04 ]]; then echo 'Requires Ubuntu 24.04.' >&2; exit 1; fi
base=/opt/idea-echo-native
data=/var/lib/idea-echo
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
for path in "$base" "$base/venv" "$base/maintenance" "$data" "$data/backups"; do
  if [[ -L $path ]]; then echo "Linked path not allowed: $path" >&2; exit 1; fi
done
if [[ ! -x $base/venv/bin/python || ! -f $data/ideas.db ]]; then
  echo 'Existing native Python installation and database required.' >&2; exit 1
fi
if ! id idea-echo >/dev/null 2>&1 || [[ $(id -u idea-echo) == 0 ]]; then
  echo 'Non-root idea-echo service account required.' >&2; exit 1
fi
for path in "$data" "$data/backups"; do
  if [[ -e $path ]] && [[ ! -d $path || $(stat -c %U "$path") != idea-echo ]]; then
    echo "Refusing to change data owned by another user: $path" >&2; exit 1
  fi
done
if [[ -e $base/maintenance ]] && [[ ! -d $base/maintenance || $(stat -c %U "$base/maintenance") != root ]]; then
  echo 'Maintenance directory must be root-owned.' >&2; exit 1
fi
# Check every target before installing any file; customized files need manual review.
for name in backup-job.py idea-echo-native-backup.service idea-echo-native-backup.timer; do
  target=/etc/systemd/system/$name
  if [[ $name == backup-job.py ]]; then target=$base/maintenance/$name; fi
  if [[ -L $target ]] || { [[ -e $target ]] && ! cmp -s "$source_dir/$name" "$target"; }; then
    echo "Existing target differs or is linked; not overwritten: $target" >&2; exit 1
  fi
done
runuser -u idea-echo -- "$base/venv/bin/python" -c 'from idea_echo.backup import create_backup, restore_backup, rotate_backups'
systemd-analyze verify "$source_dir/idea-echo-native-backup.service" "$source_dir/idea-echo-native-backup.timer"
install -d -o root -g root -m 0755 "$base/maintenance"
install -d -o idea-echo -g idea-echo -m 0700 "$data/backups"
install -o root -g root -m 0644 "$source_dir/backup-job.py" "$base/maintenance/backup-job.py"
install -o root -g root -m 0644 "$source_dir/idea-echo-native-backup.service" /etc/systemd/system/idea-echo-native-backup.service
install -o root -g root -m 0644 "$source_dir/idea-echo-native-backup.timer" /etc/systemd/system/idea-echo-native-backup.timer
systemctl daemon-reload
if ! systemctl start idea-echo-native-backup.service; then
  journalctl -u idea-echo-native-backup.service -n 30 --no-pager
  echo 'First backup failed; timer was not enabled by this installer.' >&2; exit 1
fi
systemctl enable --now idea-echo-native-backup.timer
journalctl -u idea-echo-native-backup.service -n 10 --no-pager
systemctl list-timers idea-echo-native-backup.timer --no-pager
echo 'Backup verified and timer enabled. Download a backup to private off-server storage as well.'
