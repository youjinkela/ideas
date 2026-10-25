#!/usr/bin/env bash
# Offline native upgrade; leaves credentials, firewall and Caddy unchanged.
set -euo pipefail
[[ $(id -u) == 0 ]] || { echo 'Run as root.' >&2; exit 1; }
release=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
base=/opt/idea-echo-native
python=$base/venv/bin/python
wheel=$release/idea_echo_server-0.1.0-py3-none-any.whl
[[ -x $python && -f $wheel && ! -L $base && ! -L $base/venv ]] || { echo 'Native installation not found.' >&2; exit 1; }
[[ $(systemctl show idea-echo -p User --value) == idea-echo ]] || { echo 'Unexpected service account.' >&2; exit 1; }
[[ $(systemctl show idea-echo -p WorkingDirectory --value) == "$base/app" ]] || { echo 'Unexpected service directory.' >&2; exit 1; }
(cd -- "$release" && sha256sum -c SHA256SUMS)
package_dir=$($python -c 'import pathlib,idea_echo; print(pathlib.Path(idea_echo.__file__).resolve().parent)')
[[ $package_dir == "$base/venv/lib/python3.12/site-packages/idea_echo" ]] || { echo 'Unexpected installed package path.' >&2; exit 1; }
rollback=$(mktemp -d /root/idea-echo-delete-upgrade.XXXXXXXX)
chmod 700 "$rollback"
cp -a -- "$package_dir" "$rollback/idea_echo"
systemctl start idea-echo-native-backup.service
systemctl stop idea-echo
rollback_runtime() {
    upgrade_rc=$?
    trap - ERR
    echo 'Upgrade failed; restoring previous application code.' >&2
    systemctl stop idea-echo || true
    cp -a -- "$rollback/idea_echo/." "$package_dir/"
    systemctl start idea-echo || true
    exit "$upgrade_rc"
}
trap rollback_runtime ERR
"$python" -m pip install --no-index --no-deps --force-reinstall "$wheel"
"$python" -m pip check
systemctl start idea-echo
curl --fail --silent --show-error --retry 6 --retry-all-errors --retry-delay 2 --max-time 5 http://127.0.0.1:8000/health > "$rollback/health.json"
"$python" -c 'import json,sys; assert json.load(open(sys.argv[1])).get("sync_deletion") is True' "$rollback/health.json"
systemctl is-active --quiet idea-echo
trap - ERR
cat "$rollback/health.json"
echo
echo 'Synced deletion enabled. Application rollback copy:' "$rollback"
