# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   File:   ./tests/utils/utils.sh
#   Author: Jiri Kucera <jkucera@redhat.com>
#   Brief:  Common shell utilities that helps test volume_key
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   Copyright (c) 2020 Red Hat, Inc.
#
#   This program is free software: you can redistribute it and/or
#   modify it under the terms of the GNU General Public License as
#   published by the Free Software Foundation, either version 2 of
#   the License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be
#   useful, but WITHOUT ANY WARRANTY; without even the implied
#   warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
#   PURPOSE.  See the GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program. If not, see http://www.gnu.org/licenses/.
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

##
# SCRIPTDIR
#
# Path to the directory with auxiliary scripts.
SCRIPTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

# Include beakerlib wrapper:
. "${SCRIPTDIR}/rlwrap.sh" || {
  echo "${SCRIPTDIR}/rlwrap.sh cannot be included." >&2
  exit 1
}

##
# ClearGpgAgentsCache
#
# If CLEAR_GPG_AGENTS_CACHE is set, clear gpg-agent's password cache.
function ClearGpgAgentsCache() {
  local __pid=""

  if [[ "${CLEAR_GPG_AGENTS_CACHE:-}" == "1" ]] \
  && __pid="$(pidof -s gpg-agent)"
  then
    kill -s SIGHUP ${__pid} || :
  fi
}

##
# CreateEncryptedVolume --image IMAGE --password PASS [--with-losetup]
#
#   --image IMAGE
#       path to image file from which volume is created; IMAGE is created by
#       dd so it should not to point to an existing file
#   --password PASS
#       password needed to encrypt the volume
#   --with-losetup
#       create a volume as loop device
#
# Create encrypted volume from IMAGE (use PASS for the encryption). The name of
# created volume is stored to Result.
function CreateEncryptedVolume() {
  local __image=""
  local __volume=""
  local __password=""
  local __with_losetup=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --image) shift; __image="$1" ;;
      --password) shift; __password="$1" ;;
      --with-losetup) __with_losetup="yes" ;;
      *) invalid_argument "$1"; return $? ;;
    esac
    shift
  done

  required_options image password || return $?

  RunCmd dd if=/dev/zero of="${__image}" bs=1M count=256 || return $?

  __volume="${__image}"
  if [[ "${__with_losetup}" == "yes" ]]; then
    RunCmd losetup -v -f "${__image}" || return $?
    __volume="$(
      set -o pipefail
      losetup -a | grep "${__image}" | cut -d: -f1
    )" || return $?
  fi

  RunCmdViaExpect
    Command cryptsetup luksFormat "${__volume}"
    Input --password "${__password}"
  FinishRun || return $?

  Result="${__volume}"
}

##
# CreateCertificate --name NAME [--rsa-bits BITS]
#
#   --name NAME
#       certificate name
#   --rsa-bits BITS
#       RSA bits (default: 1024)
#
# Create NAME.key, NAME.cert, and NAME.pem inside current working directory.
function CreateCertificate() {
  local __name=""
  local __rsa_bits=1024
  local __key=""
  local __cert=""
  local __pem=""
  local __subject=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --name) shift; __name="$1" ;;
      --rsa-bits) shift; __rsa_bits="$1" ;;
      *) invalid_argument "$1"; return $? ;;
    esac
    shift
  done

  required_options name || return $?

  __key="${__name}.key"
  __cert="${__name}.cert"
  __pem="${__name}.pem"

  RunCmd openssl genrsa ${__rsa_bits} \> "${__key}" || return $?

  __subject="/C=XX/ST=FooState/L=FooLocality/O=FooOrg/OU=FooOrgUnit"
  __subject="${__subject}/CN=John/SN=Doe/emailAddress=jdoe@foo.bar"

  RunCmd openssl req -new -x509 -nodes -sha1 -days 365 \
    -key "${__key}" -subj "'${__subject}'" \> "${__cert}" \
  || return $?

  RunCmd cat "${__cert}" "${__key}" \> "${__pem}"
}

##
# SetupNSSDatabase --dest DEST --cert-name NAME --password PASS
#
#   --dest DEST
#       path to directory that become NSS database
#   --cert-name NAME
#       the name of the certificate
#   --password PASS
#       a password (common for certificate and for NSS database)
#
# Create and initialize NSS database DEST with certificate NAME and secure it
# with password PASS.
function SetupNSSDatabase() {
  local __dest=""
  local __cert_name=""
  local __password=""
  local __pwdfile=""
  local __pem=""
  local __p12=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --dest) shift; __dest="$1" ;;
      --cert-name) shift; __cert_name="$1" ;;
      --password) shift; __password="$1" ;;
      *) invalid_argument "$1"; return $? ;;
    esac
    shift
  done

  required_options dest cert-name password || return $?

  RunCmd mkdir -p "${__dest}" || return $?

  __pwdfile="$(mktemp "./pwdfileXXXXX")" || return $?

  __pem="${__cert_name}.pem"
  __p12="${__cert_name}.p12"

  RunCmd echo "${__password}" \> "${__pwdfile}" || return $?

  RunCmd certutil -N -d "${__dest}" -f "${__pwdfile}" || return $?

  RunCmd openssl pkcs12 -export -in "${__pem}" -out "${__p12}" \
    -name "${__cert-name}" -password "pass:${__password}" \
  || return $?

  RunCmd pk12util -i "${__p12}" -d "${__dest}" \
    -K "${__password}" -W "${__password}"
}
