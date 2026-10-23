#!/usr/bin/env bash
# Fresh native install only. Does not open firewall ports or create passwords.
set -euo pipefail
if [[ $(id -u) != 0 ]]; then echo 'Run as root on Ubuntu 24.04.' >&2; exit 1; fi
. /etc/os-release
if [[ ${ID:-} != ubuntu || ${VERSION_ID:-} != 24.04 ]]; then echo 'Requires Ubuntu 24.04.' >&2; exit 1; fi
app=/opt/idea-echo-native/app
base=/opt/idea-echo-native
source_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
if [[ $source_root != "$app" || -L $base || -L $app ]]; then echo "Extract package into $app first; symlink paths are not accepted." >&2; exit 1; fi
unit=/etc/systemd/system/idea-echo.service
if [[ -e $unit ]] && ! cmp -s "$app/deploy/native/idea-echo.service" "$unit"; then
  echo 'Existing service differs; refusing to overwrite. Review it before upgrading.' >&2; exit 1
fi
if [[ -e $base/venv || -L $base/venv ]]; then echo 'Existing venv found; this installer is for a fresh installation only.' >&2; exit 1; fi
python3.12 -m venv "$base/venv"
"$base/venv/bin/python" -m pip install --timeout 15 --retries 1 -r "$app/requirements.lock"
"$base/venv/bin/python" -m pip install --timeout 15 --retries 1 --no-deps "$app/server"
"$base/venv/bin/python" -m pip check
if ! getent passwd idea-echo >/dev/null; then
  useradd --system --user-group --home-dir /var/lib/idea-echo --no-create-home --shell /usr/sbin/nologin idea-echo
fi
if [[ $(id -u idea-echo) == 0 ]]; then echo 'Service account must not be root.' >&2; exit 1; fi
# Do not take ownership of an existing user's data directory.
if [[ -e /var/lib/idea-echo || -L /var/lib/idea-echo ]]; then
  if [[ -L /var/lib/idea-echo || $(stat -c %U /var/lib/idea-echo) != idea-echo ]]; then
    echo 'Data path is linked or owned by another user; refusing to alter it.' >&2; exit 1
  fi
else
  install -d -m 0700 -o idea-echo -g idea-echo /var/lib/idea-echo
fi
install -m 0644 "$app/deploy/native/idea-echo.service" "$unit"
systemctl daemon-reload
echo 'Installed but NOT started. Create the private account interactively, then enable the service as documented.'
