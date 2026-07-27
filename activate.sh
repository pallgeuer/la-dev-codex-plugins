#!/usr/bin/env bash

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    printf '%s\n' "activate.sh must be sourced: source ${BASH_SOURCE[0]}" >&2
    exit 2
fi

_la_dev_codex_plugins_source="${BASH_SOURCE[0]}"
while [[ -h "${_la_dev_codex_plugins_source}" ]]; do
    _la_dev_codex_plugins_dir="$(cd -P -- "$(dirname -- "${_la_dev_codex_plugins_source}")" && pwd)"
    _la_dev_codex_plugins_target="$(readlink "${_la_dev_codex_plugins_source}")"
    if [[ "${_la_dev_codex_plugins_target}" == /* ]]; then
        _la_dev_codex_plugins_source="${_la_dev_codex_plugins_target}"
    else
        _la_dev_codex_plugins_source="${_la_dev_codex_plugins_dir}/${_la_dev_codex_plugins_target}"
    fi
done
_LA_DEV_CODEX_PLUGINS_ROOT="$(cd -P -- "$(dirname -- "${_la_dev_codex_plugins_source}")" && pwd)"
unset _la_dev_codex_plugins_source _la_dev_codex_plugins_dir _la_dev_codex_plugins_target

codex-perform() {
    local perform_python="${CODEX_PERFORM_PYTHON:-python3}"
    command "${perform_python}" -I "${_LA_DEV_CODEX_PLUGINS_ROOT}/src/la_dev_codex_plugins/cli/_perform_bootstrap.py" "$@"
}
