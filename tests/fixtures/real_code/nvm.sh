# Node Version Manager
# Implemented as a POSIX-compliant function
# Should work on sh, dash, bash, ksh, zsh
# To use source this file from your bash profile
#
# Implemented by Tim Caswell <tim@creationix.com>
# with much bash help from Matthew Ranney

# "local" warning, quote expansion warning, sed warning, `local` warning
# shellcheck disable=SC2039,SC2016,SC2001,SC3043
{ # this ensures the entire script is downloaded #

# shellcheck disable=SC3028
NVM_SCRIPT_SOURCE="$_"

nvm_is_zsh() {
  [ -n "${ZSH_VERSION-}" ]
}

nvm_stdout_is_terminal() {
  [ -t 1 ]
}

nvm_echo() {
  command printf %s\\n "$*" 2>/dev/null
}

nvm_echo_with_colors() {
  command printf %b\\n "$*" 2>/dev/null
}

nvm_cd() {
  \cd "$@"
}

nvm_err() {
  >&2 nvm_echo "$@"
}

nvm_err_with_colors() {
  >&2 nvm_echo_with_colors "$@"
}

nvm_grep() {
  GREP_OPTIONS='' command grep "$@"
}

nvm_has() {
  type "${1-}" >/dev/null 2>&1
}

nvm_has_non_aliased() {
  nvm_has "${1-}" && ! nvm_is_alias "${1-}"
}

nvm_is_alias() {
  # this is intentionally not "command alias" so it works in zsh.
  \alias "${1-}" >/dev/null 2>&1
}

nvm_command_info() {
  local COMMAND
  local INFO
  COMMAND="${1}"
  if type "${COMMAND}" | nvm_grep -q hashed; then
    INFO="$(type "${COMMAND}" | command sed -E 's/\(|\)//g' | command awk '{print $4}')"
  elif type "${COMMAND}" | nvm_grep -q aliased; then
    # shellcheck disable=SC2230
    INFO="$(which "${COMMAND}") ($(type "${COMMAND}" | command awk '{ $1=$2=$3=$4="" ;print }' | command sed -e 's/^\ *//g' -Ee "s/\`|'//g"))"
  elif type "${COMMAND}" | nvm_grep -q "^${COMMAND} is an alias for"; then
    # shellcheck disable=SC2230
    INFO="$(which "${COMMAND}") ($(type "${COMMAND}" | command awk '{ $1=$2=$3=$4=$5="" ;print }' | command sed 's/^\ *//g'))"
  elif type "${COMMAND}" | nvm_grep -q "^${COMMAND} is /"; then
    INFO="$(type "${COMMAND}" | command awk '{print $3}')"
  else
    INFO="$(type "${COMMAND}")"
  fi
  nvm_echo "${INFO}"
}

nvm_has_colors() {
  local NVM_NUM_COLORS
  if nvm_has tput; then
    NVM_NUM_COLORS="$(command tput -T "${TERM:-vt100}" colors)"
  fi
  [ -t 1 ] && [ "${NVM_NUM_COLORS:--1}" -ge 8 ] && [ "${NVM_NO_COLORS-}" != '--no-colors' ]
}

nvm_curl_libz_support() {
  curl -V 2>/dev/null | nvm_grep "^Features:" | nvm_grep -q "libz"
}

nvm_curl_use_compression() {
  nvm_curl_libz_support && nvm_version_greater_than_or_equal_to "$(nvm_curl_version)" 7.21.0
}

nvm_get_latest() {
  local NVM_LATEST_URL
  local CURL_COMPRESSED_FLAG
  if nvm_has "curl"; then
    if nvm_curl_use_compression; then
      CURL_COMPRESSED_FLAG="--compressed"
    fi
    NVM_LATEST_URL="$(curl ${CURL_COMPRESSED_FLAG:-} -q -w "%{url_effective}\\n" -L -s -S https://latest.nvm.sh -o /dev/null)"
  elif nvm_has "wget"; then
    NVM_LATEST_URL="$(wget -q https://latest.nvm.sh --server-response -O /dev/null 2>&1 | command awk '/^  Location: /{DEST=$2} END{ print DEST }')"
  else
    nvm_err 'nvm needs curl or wget to proceed.'
    return 1
  fi
  if [ -z "${NVM_LATEST_URL}" ]; then
    nvm_err "https://latest.nvm.sh did not redirect to the latest release on GitHub"
    return 2
  fi
  nvm_echo "${NVM_LATEST_URL##*/}"
}

nvm_download() {
  if nvm_has "curl"; then
    local CURL_COMPRESSED_FLAG=""
    local CURL_HEADER_FLAG=""

    if [ -n "${NVM_AUTH_HEADER:-}" ]; then
      sanitized_header=$(nvm_sanitize_auth_header "${NVM_AUTH_HEADER}")
      CURL_HEADER_FLAG="--header \"Authorization: ${sanitized_header}\""
    fi

    if nvm_curl_use_compression; then
      CURL_COMPRESSED_FLAG="--compressed"
    fi
    local NVM_DOWNLOAD_ARGS
    NVM_DOWNLOAD_ARGS=''
    for arg in "$@"; do
      NVM_DOWNLOAD_ARGS="${NVM_DOWNLOAD_ARGS} \"$arg\""
    done
    eval "curl -q --fail ${CURL_COMPRESSED_FLAG:-} ${CURL_HEADER_FLAG:-} ${NVM_DOWNLOAD_ARGS}"
  elif nvm_has "wget"; then
    # Emulate curl with wget
    ARGS=$(nvm_echo "$@" | command sed "
      s/--progress-bar /--progress=bar /
      s/--compressed //
      s/--fail //
      s/-L //
      s/-I /--server-response /
      s/-s /-q /
      s/-sS /-nv /
      s/-o /-O /
      s/-C - /-c /
    ")

    if [ -n "${NVM_AUTH_HEADER:-}" ]; then
      sanitized_header=$(nvm_sanitize_auth_header "${NVM_AUTH_HEADER}")
      ARGS="${ARGS} --header \"${sanitized_header}\""
    fi
    # shellcheck disable=SC2086
    eval wget $ARGS
  fi
}

nvm_sanitize_auth_header() {
    # Remove potentially dangerous characters
    nvm_echo "$1" | command sed 's/[^a-zA-Z0-9:;_. -]//g'
}

nvm_has_system_node() {
  [ "$(nvm deactivate >/dev/null 2>&1 && command -v node)" != '' ]
}

nvm_has_system_iojs() {
  [ "$(nvm deactivate >/dev/null 2>&1 && command -v iojs)" != '' ]
}

nvm_is_version_installed() {
  if [ -z "${1-}" ]; then
    return 1
  fi
  local NVM_NODE_BINARY
  NVM_NODE_BINARY='node'
  if [ "_$(nvm_get_os)" = '_win' ]; then
    NVM_NODE_BINARY='node.exe'
  fi
  if [ -x "$(nvm_version_path "$1" 2>/dev/null)/bin/${NVM_NODE_BINARY}" ]; then
    return 0
  fi
  return 1
}

nvm_print_npm_version() {
  if nvm_has "npm"; then
    local NPM_VERSION
    NPM_VERSION="$(npm --version 2>/dev/null)"
    if [ -n "${NPM_VERSION}" ]; then
      command printf " (npm v${NPM_VERSION})"
    fi
  fi
}

nvm_install_latest_npm() {
  nvm_echo 'Attempting to upgrade to the latest working version of npm...'
  local NODE_VERSION
