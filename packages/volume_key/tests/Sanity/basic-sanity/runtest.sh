#!/bin/bash
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   File:   ./tests/Sanity/basic-sanity/runtest.sh
#   Author: Jan Blazek <jblazek@redhat.com>
#           Jiri Kucera <jkucera@redhat.com>
#   Brief:  Basic sanity test for volume_key utility
#
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   Copyright (c) 2017-2020 Red Hat, Inc.
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

_TESTDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

# Include Beaker environment
. /usr/share/beakerlib/beakerlib.sh || exit 1

# Include utils
. ${_TESTDIR}/../../utils/utils.sh || {
  echo "${_TESTDIR}/../../utils/utils.sh cannot be included." >&2
  exit 1
}

# Include test settings:
. ${_TESTDIR}/../../settings/environment.sh || {
  errmsg "${_TESTDIR}/../../settings/environment.sh cannot be included."
  exit 1
}

TEST="${TEST:-/CoreOS/volume_key/tests/Sanity/basic-sanity}"
TESTVERSION="${TESTVERSION:-1.0}"
PACKAGES="${PACKAGES:-volume_key}"
REQUIRES="${REQUIRES:-cryptsetup nss-tools expect tcllib}"

_GNUPG_DIR="${HOME}/.gnupg"
_IMAGE="${_IMAGE:-image}"
_IMAGE_IMG="${_IMAGE}.img"
_PACKET="${_PACKET:-packet}"
_NEW_PACKET="${_NEW_PACKET:-new-packet}"
_PACKET_ASYM="${_PACKET_ASYM:-packet-asym}"
_NEW_PACKET_ASYM="${_NEW_PACKET_ASYM:-new-packet-asym}"
_ESCROW="${_ESCROW:-escrow}"
_ESCROW_PEM="${_ESCROW}.pem"
_NSSDB="${_NSSDB:-nssdb}"

_LUKS_PASS="${_LUKS_PASS:-lukspass}"
_PACKET_PASS="${_PACKET_PASS:-packetpass}"
_NEW_PACKET_PASS="${_NEW_PACKET_PASS:-newpacketpass}"
_CERT_PASS="${_CERT_PASS:-certpass}"
_NEW_LUKS_PASS="${_NEW_LUKS_PASS:-newlukspass}"
_NEW_LUKS_PASS_ASYM="${_NEW_LUKS_PASS_ASYM:-newlukspass-asym}"

_TEMP_DIR=""
_VOLUME=""

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~ Setup
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

function Setup() {
  LANG=C
  LC_ALL=C
  export EXPECT_SCRIPTS_PATH="${SCRIPTDIR}"

  rlAssertRpm --all || return $?

  if [[ -d "${_GNUPG_DIR}" ]]; then
    rlFileBackup "${_GNUPG_DIR}" || return $?
    AtCleanup rlFileRestore
  else
    AtCleanup Cleanup_RemoveGnuPG
  fi

  rlRun CreateTemporaryDirectory || return $?
  _TEMP_DIR="${Result}"
  AtCleanup Cleanup_RemoveTemporaryDirectory

  PushDir "${_TEMP_DIR}" || return $?
  AtCleanup PopDir

  CreateEncryptedVolume \
    --image "${_IMAGE_IMG}" \
    --password "${_LUKS_PASS}" \
    ${USE_LOSETUP:+--with-losetup} \
  || return $?
  _VOLUME="${Result}"
  AtCleanup Cleanup_DestroyVolume

  CreateCertificate --name "${_ESCROW}" || return $?

  SetupNSSDatabase --dest "${_TEMP_DIR}/${_NSSDB}" \
    --cert-name "${_ESCROW}" --password "${_CERT_PASS}"
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~ Cleanup
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

function Cleanup_RemoveGnuPG() {
  RunCmd rm -rfv "${_GNUPG_DIR}"
}

function Cleanup_RemoveTemporaryDirectory() {
  RunCmd rm -rfv "${_TEMP_DIR}"
}

function Cleanup_DestroyVolume() {
  if [[ "${USE_LOSETUP:+yes}" == "yes" ]]; then
    RunCmd losetup -d "${_VOLUME}"
  fi
}

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# ~~ Tests
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

function TestVolumeKeySave() {
  RunCmdViaExpect
    Command volume_key 
    Command   --save "${_VOLUME}" --output-format=passphrase -o "${_PACKET}"
    Input --lukspass "${_LUKS_PASS}"
    Input --packetpass "${_PACKET_PASS}"
    Input ${USING_PINENTRY:+--pinentry}
  FinishRun
}
AddTest TestVolumeKeySave "save"

function TestVolumeKeyRestore() {
  rlAssertExists "${_PACKET}" || return $?

  ClearGpgAgentsCache
  RunCmdViaExpect
    Command volume_key --restore "${_VOLUME}" "${_PACKET}"
    Input --lukspass "${_NEW_LUKS_PASS}"
    Input --packetpass "${_PACKET_PASS}"
    Input ${USING_PINENTRY:+--pinentry}
  FinishRun || return $?

  RunCmdViaExpect
    Command cryptsetup luksOpen "${_VOLUME}" "${_IMAGE}"
    Input --password "${_NEW_LUKS_PASS}"
  FinishRun || return $?

  RunCmd ls -la /dev/mapper
  rlAssertExists "/dev/mapper/${_IMAGE}"

  RunCmd cryptsetup luksClose "${_IMAGE}"
}
AddTest TestVolumeKeyRestore "restore"

function TestVolumeKeySetupVolume() {
  rlAssertExists "${_PACKET}" || return $?

  ClearGpgAgentsCache
  RunCmdViaExpect
    Command volume_key --setup-volume "${_VOLUME}" "${_PACKET}" "${_IMAGE}"
    Input --packetpass "${_PACKET_PASS}"
    Input ${USING_PINENTRY:+--pinentry}
  FinishRun || return $?

  RunCmd ls -la /dev/mapper
  rlAssertExists "/dev/mapper/${_IMAGE}"

  RunCmd cryptsetup luksClose "${_IMAGE}"
}
AddTest TestVolumeKeySetupVolume "setup-volume"

function TestVolumeKeyReencrypt() {
  rlAssertExists "${_PACKET}" || return $?

  ClearGpgAgentsCache
  RunCmdViaExpect
    Command volume_key --reencrypt "${_PACKET}" -o "${_NEW_PACKET}"
    Input --packetpass "${_PACKET_PASS}"
    Input --newpacketpass "${_NEW_PACKET_PASS}"
    Input ${USING_PINENTRY:+--pinentry}
  FinishRun || return $?

  ClearGpgAgentsCache
  RunCmdViaExpect
    Command volume_key --setup-volume "${_VOLUME}" "${_NEW_PACKET}" "${_IMAGE}"
    Input --packetpass "${_NEW_PACKET_PASS}"
    Input ${USING_PINENTRY:+--pinentry}
  FinishRun || return $?

  RunCmd ls -la /dev/mapper
  rlAssertExists "/dev/mapper/${_IMAGE}"

  RunCmd cryptsetup luksClose "${_IMAGE}"
}
AddTest TestVolumeKeyReencrypt "reencrypt"

function TestVolumeKeyDump() {
  local __uuid=""

  rlAssertExists "${_PACKET}" || return $?

  ClearGpgAgentsCache
  RunCmdViaExpect
    rlRunOptions -s
    Command volume_key --dump "${_PACKET}"
    Input --packetpass "${_PACKET_PASS}"
    Input ${USING_PINENTRY:+--pinentry}
  FinishRun || return $?

  __uuid="$(blkid -o value -s UUID "${_VOLUME}")"

  rlAssertGrep '^Packet format:\W+Passphrase-encrypted' "${rlRun_LOG}" -E
  rlAssertGrep '^Volume format:\W+crypt_LUKS' "${rlRun_LOG}" -E
  rlAssertGrep "^Volume UUID:\W+${__uuid}" "${rlRun_LOG}" -E
  rlAssertGrep "^Volume path:\W+${_VOLUME}" "${rlRun_LOG}" -E
}
AddTest TestVolumeKeyDump "dump"

function TestVolumeKeySecrets() {
  rlAssertExists "${_PACKET}" || return $?

  ClearGpgAgentsCache
  RunCmdViaExpect
    rlRunOptions -s
    Command volume_key --secrets "${_PACKET}"
    Input --packetpass "${_PACKET_PASS}"
    Input ${USING_PINENTRY:+--pinentry}
  FinishRun || return $?

  rlAssertGrep 'Data encryption key:\W+[0-9A-F]+' "${rlRun_LOG}" -E
}
AddTest TestVolumeKeySecrets "secrets"

function TestVolumeKeySaveAsymmetric() {
  RunCmdViaExpect
    Command volume_key 
    Command   --save "${_VOLUME}" --output-format=asymmetric
    Command   -c "${_ESCROW_PEM}" -o "${_PACKET_ASYM}"
    Input --lukspass "${_LUKS_PASS}"
  FinishRun
}
AddTest TestVolumeKeySaveAsymmetric "save asymmetric"

function TestVolumeKeyRestoreAsymmetric() {
  rlAssertExists "${_PACKET_ASYM}" || return $?

  RunCmdViaExpect
    Command volume_key --restore "${_VOLUME}" "${_PACKET_ASYM}" -d "${_NSSDB}"
    Input --certpass "${_CERT_PASS}"
    Input --lukspass "${_NEW_LUKS_PASS_ASYM}"
  FinishRun || return $?

  RunCmdViaExpect
    Command cryptsetup luksOpen "${_VOLUME}" "${_IMAGE}"
    Input --password "${_NEW_LUKS_PASS_ASYM}"
  FinishRun || return $?

  RunCmd ls -la /dev/mapper
  rlAssertExists "/dev/mapper/${_IMAGE}"

  RunCmd cryptsetup luksClose "${_IMAGE}"
}
AddTest TestVolumeKeyRestoreAsymmetric "restore asymmetric"

function TestVolumeKeySetupVolumeAsymmetric() {
  rlAssertExists "${_PACKET_ASYM}" || return $?

  RunCmdViaExpect
    Command volume_key
    Command   --setup-volume "${_VOLUME}" "${_PACKET_ASYM}" "${_IMAGE}"
    Command   -d "${_NSSDB}"
    Input --certpass "${_CERT_PASS}"
  FinishRun || return $?

  RunCmd ls -la /dev/mapper
  rlAssertExists "/dev/mapper/${_IMAGE}"

  RunCmd cryptsetup luksClose "${_IMAGE}"
}
AddTest TestVolumeKeySetupVolumeAsymmetric "setup-volume asymmetric"

function TestVolumeKeyReencryptAsymmetric() {
  rlAssertExists "${_PACKET_ASYM}" || return $?

  ClearGpgAgentsCache
  RunCmdViaExpect
    Command volume_key --reencrypt
    Command   -d "${_NSSDB}" "${_PACKET_ASYM}" -o "${_NEW_PACKET_ASYM}"
    Input --certpass "${_CERT_PASS}"
    Input --newpacketpass "${_NEW_PACKET_PASS}"
    Input ${USING_PINENTRY:+--pinentry}
  FinishRun || return $?

  ClearGpgAgentsCache
  RunCmdViaExpect
    Command volume_key
    Command   --setup-volume "${_VOLUME}" "${_NEW_PACKET_ASYM}" "${_IMAGE}"
    Input --packetpass "${_NEW_PACKET_PASS}"
    Input ${USING_PINENTRY:+--pinentry}
  FinishRun || return $?

  RunCmd ls -la /dev/mapper
  rlAssertExists "/dev/mapper/${_IMAGE}"

  RunCmd cryptsetup luksClose "${_IMAGE}"
}
AddTest TestVolumeKeyReencryptAsymmetric "reencrypt asymmetric"

function TestVolumeKeyDumpAsymmetric() {
  local __uuid=""

  rlAssertExists "${_PACKET_ASYM}" || return $?

  RunCmdViaExpect
    rlRunOptions -s
    Command volume_key --dump "${_PACKET_ASYM}" -d "${_NSSDB}"
    Input --certpass "${_CERT_PASS}"
  FinishRun || return $?

  __uuid="$(blkid -o value -s UUID "${_VOLUME}")"

  rlAssertGrep '^Packet format:\W+Public key-encrypted' "${rlRun_LOG}" -E
  rlAssertGrep '^Volume format:\W+crypt_LUKS' "${rlRun_LOG}" -E
  rlAssertGrep "^Volume UUID:\W+${__uuid}" "${rlRun_LOG}" -E
  rlAssertGrep "^Volume path:\W+${_VOLUME}" "${rlRun_LOG}" -E
}
AddTest TestVolumeKeyDumpAsymmetric "dump asymmetric"

function TestVolumeKeySecretsAsymmetric() {
  rlAssertExists "${_PACKET_ASYM}" || return $?

  RunCmdViaExpect
    rlRunOptions -s
    Command volume_key --secrets "${_PACKET_ASYM}" -d "${_NSSDB}"
    Input --certpass "${_CERT_PASS}"
  FinishRun || return $?

  rlAssertGrep 'Data encryption key:\W+[0-9A-F]+' "${rlRun_LOG}" -E
}
AddTest TestVolumeKeySecretsAsymmetric "secrets asymmetric"

RunTest
