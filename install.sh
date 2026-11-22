#!/usr/bin/env bash
# Stage a complete plugin before activation; restore the old version if activation fails.
set -euo pipefail
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
config_root="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy"
plugin_root="$config_root/plugins"
plugin_dir="$plugin_root/zizor.omahome"
updating=false
staging_dir=""
backup_dir=""
phase=preparing
if [[ ${1:-} != "" && ${1:-} != --update ]]; then
  echo 'Usage: bash install.sh [--update]' >&2
  exit 1
fi
command -v omarchy >/dev/null || { echo 'Omarchy is required.' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'Python 3 is required.' >&2; exit 1; }
omarchy plugin validate "$source_dir"
if [[ -e "$plugin_dir" || -L "$plugin_dir" ]]; then
  if [[ ${1:-} != --update ]]; then
    echo 'Omahome is already installed. Run: bash install.sh --update' >&2
    exit 1
  fi
  if [[ -L "$plugin_dir" || ! -d "$plugin_dir" || -n $(find "$plugin_dir" -type l -print -quit) ]]; then
    echo 'Refusing to update a plugin directory containing symlinks.' >&2
    exit 1
  fi
  [[ $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$plugin_dir/manifest.json") == zizor.omahome ]] || {
    echo 'The installed plugin manifest has an unexpected id.' >&2; exit 1;
  }
  updating=true
fi

cleanup() {
  local result=$?
  trap - EXIT HUP INT TERM
  if [[ $phase == activating && ! -e "$plugin_dir" && ! -L "$plugin_dir" && -f "$backup_dir/manifest.json" ]]; then
    if mv -T -n -- "$backup_dir" "$plugin_dir" && [[ ! -d "$backup_dir" ]]; then
      echo 'Activation failed; the previous plugin was restored automatically.' >&2
    else
      printf 'Automatic restore failed. Previous plugin is preserved at %s\n' "$backup_dir" >&2
    fi
  elif [[ $phase == activating && -f "$backup_dir/manifest.json" ]]; then
    printf 'Activation did not finish. Previous plugin is preserved at %s\n' "$backup_dir" >&2
  fi
  if [[ -n $staging_dir && -d $staging_dir ]]; then rm -rf -- "$staging_dir"; fi
  exit "$result"
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

mkdir -p -- "$plugin_root"
# Staging is outside the watched plugins directory. Failed copies or validation
# leave the currently installed version completely untouched.
staging_dir=$(mktemp -d "$config_root/.omahome-install.XXXXXX")
for file in "$source_dir"/*.qml "$source_dir/manifest.json" "$source_dir/README.md" "$source_dir/LICENSE"; do
  cp -- "$file" "$staging_dir/${file##*/}"
done
mkdir -- "$staging_dir/bin"
cp -- "$source_dir/bin/bridge.py" "$staging_dir/bin/bridge.py"
if [[ -d "$source_dir/assets" ]]; then cp -a -- "$source_dir/assets" "$staging_dir/assets"; fi
if [[ -d "$source_dir/docs" ]]; then cp -a -- "$source_dir/docs" "$staging_dir/docs"; fi
omarchy plugin validate "$staging_dir"

if $updating; then
  backup_root="$config_root/plugin-backups"
  mkdir -p -- "$backup_root"
  backup_dir=$(mktemp -d "$backup_root/omahome-$(date +%Y%m%d-%H%M%S).XXXXXX")
  # Arm recovery before moving the old directory, including signal delivery.
  phase=activating
  mv -T -- "$plugin_dir" "$backup_dir"
fi
mv -T -n -- "$staging_dir" "$plugin_dir"
if [[ -d $staging_dir ]]; then
  echo 'Installation destination appeared during setup; nothing was overwritten.' >&2
  exit 1
fi
phase=committed
if $updating; then
  printf 'Omahome updated. Previous plugin saved at %s\n' "$backup_dir"
  printf '%s\n' 'Run omarchy-restart-shell to load the updated plugin.'
else
  omarchy-shell shell rescanPlugins
  omarchy plugin enable zizor.omahome --section right
  printf '%s\n' 'Omahome installed. Click the Home Assistant icon and open Settings.'
fi
