# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
#
#   File:   ./tests/utils/rlwrap.sh
#   Author: Jiri Kucera <jkucera@redhat.com>
#   Brief:  Wrapper around beakerlib (rlX) functions
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
# Result, ResultA, ResultB
#
# If a function has an output, it is stored inside these variables.
Result=""
ResultA=""
ResultB=""

# Internal variables used by RunCmdViaExpect family of functions.
_rlwrap_expect_script_path=""
declare -ag _rlwrap_rlRun_options=()
declare -ag _rlwrap_expect_options=()
_rlwrap_expect_script=""
_rlwrap_expect_script_scommand=""
declare -ag _rlwrap_expect_script_command_args=()
declare -ag _rlwrap_expect_script_input_args=()
_rlwrap_rlRun_status="0"
_rlwrap_rlRun_comment=""

# Internal variables used by RunTest family of functions.
declare -ag _CleanupActions=()
declare -ag _Tests=()

##
# errmsg ERRMSG
#
#   ERRMSG
#     error message
#
# Print ERRMSG to standard error output.
function errmsg() {
  echo "$1" >&2
}

##
# required_options OPTION_LIST
#
#   OPTION_LIST
#     a list of option names (without --)
#
# For every X from OPTION_LIST, test if --$X was specified by checking that
# __${X//-/_} is not empty.
function required_options() {
  local __optvar=""

  while [[ $# -gt 0 ]]; do
    __optvar="__${1//-/_}"
    if [[ -z "${!__optvar}" ]]; then
      errmsg "${FUNCTION[1]}: Missing required option: --$1"
      return 1
    fi
    shift
  done
}

##
# invalid_argument ARG_NAME
#
#   ARG_NAME
#     argument name
#
# Report to standard error output that ARG_NAME is not a valid argument and
# return 1.
function invalid_argument() {
  errmsg "${FUNCTION[1]}: Invalid argument '$1'."
  return 1
}

##
# Concat ARGS
#
#   ARGS
#     list of arguments
#
# Make a string by concatenating all arguments from ARGS. Useful for creating
# long comments for rlRun.
function Concat() {
  echo "$*"
}

##
# RunCmd COMMAND [COMMAND_ARGS]
#
#   COMMAND
#     command that should be run
#   COMMAND_ARGS
#     command arguments
#
# Shorthand for RunCmdX -- COMMAND COMMAND_ARGS.
function RunCmd() {
  RunCmdX -- "$@"
}

##
# RunCmdX [-t] [-l] [-c] [-s] [STATUS] [COMMENT] [--] COMMAND [COMMAND_ARGS]
#
#   -t, -l, -c, -s
#     see rlRun
#   STATUS
#     see rlRun
#   COMMENT
#     see rlRun
#   --
#     options-command delimiter
#   COMMAND
#     command that should be run
#   COMMAND_ARGS
#     command arguments
#
# Wrapper around beakerlib's rlRun that allows COMMAND and its arguments to be
# passed separately and not as one long string.
function RunCmdX() {
  local __tflag=""
  local __lflag=""
  local __cflag=""
  local __sflag=""
  local __command=""
  local __status="0"
  local __comment=""

  # Handle short options:
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -t) __tflag="$1" ;;
      -l) __lflag="$1" ;;
      -c) __cflag="$1" ;;
      -s) __sflag="$1" ;;
      *) break ;;
    esac
    shift
  done

  # First positional argument before -- is expected status code:
  if [[ -n "${1:-}" ]] && [[ "$1" != "--" ]]; then
    __status="$1"
    shift
  fi

  # Second positional argument before -- is comment:
  if [[ -n "${1:-}" ]] && [[ "$1" != "--" ]]; then
    __comment="$1"
    shift
  fi

  # Consume options-command delimiter:
  if [[ "${1:-}" == "--" ]]; then
    shift
  fi

  # Command name is required:
  if [[ -z "${1:-}" ]]; then
    errmsg "Expected command."
    return 1
  fi
  __command="$1"; shift

  # The rest of options are command arguments:
  while [[ $# -gt 0 ]]; do
    __command="${__command} $1"
    shift
  done

  # Let the game begin:
  rlRun ${__tflag} ${__lflag} ${__cflag} ${__sflag} \
    "${__command}" "${__status}" "${__comment}"
}

##
# RunCmdViaExpect
#
# Starts a specification of command that should be run via expect. This is
# handy for interactive commands. General usage is
#
#   RunCmdViaExpect
#     Path ${ScriptsDir}
#     rlRunOptions -s
#     ExpectOptions -f
#     Command cryptsetup luksFormat ${VOLUME}
#     Input --password ${PASSWD}
#     Status 0
#     Comment "Format ${VOLUME}"
#   FinishRun || return $?
#
# In the example above, Path specifies the directory where the expect script
# is located. If it is omitted, EXPECT_SCRIPTS_PATH environment variable is
# read. If EXPECT_SCRIPTS_PATH is not set, `.` is used.
#
# rlRunOptions are options for rlRun, like -s and -t (see beakerlib manual).
#
# ExpectOptions are options for expect tool or Tcl interpreter, not for the
# script.
#
# Command is a command together with its arguments that will be run via expect.
# The first command argument, the command itself, is used as a name of expect
# script so in the example above the name of expect script will be
# cryptsetup.exp. This script must exist in directory specified by Path. The
# rest of Command arguments will be passed to the end of this script's command
# line and it is up to script's implementation what happen to them.
#
# Input gather arguments that specify input data that are feed to command by
# expect tool when they are asked for.
#
# Input, Command, ExpectOptions, and rlRunOptions work in accumulative way.
# That is, you can write `Command cryptsetup luksFormat ${VOLUME}` as a two
# Command calls, e.g. `Command cryptsetup` and `luksFormat ${VOLUME}`. This
# allow to split long commands accross multiple lines without using backslash
# character, which has the benefit of writing comments for particular command
# options.
#
# Status is the expected status/return code (default is 0).
#
# Comment is the comment as described in rlRun documentation. The default
# comment is a string made from arguments of Command separated by spaces.
#
# FinishRun makes a final arguments for rlRun and execute it. In our case, the
# rlRun call will look like this
#
#   rlRun -s "${ScriptsDir}/cryptsetup.exp -f -- --password ${PASSWD} --
#             luksFormat ${VOLUME}" 0 "Format ${VOLUME}"
#
# The return code of rlRun is the return code of FinishRun. To parse its
# command line, cryptsetup.exp uses cmdline package from tcllib.
function RunCmdViaExpect() {
  _rlwrap_expect_script_path="${EXPECT_SCRIPTS_PATH:-.}"
  _rlwrap_rlRun_options=()
  _rlwrap_expect_options=()
  _rlwrap_expect_script=""
  _rlwrap_expect_script_scommand=""
  _rlwrap_expect_script_command_args=()
  _rlwrap_expect_script_input_args=()
  _rlwrap_rlRun_status="0"
  _rlwrap_rlRun_comment=""

  alias Path=_rlwrap_Path
  alias rlRunOptions=_rlwrap_rlRunOptions
  alias ExpectOptions=_rlwrap_ExpectOptions
  alias Command=_rlwrap_Command
  alias Input=_rlwrap_Input
  alias Status=_rlwrap_Status
  alias Comment=_rlwrap_Comment
}

##
# _rlwrap_Path [PATH]
#
#   PATH
#     PATH to script directory
#
# See Path in RunCmdViaExpect.
function _rlwrap_Path() {
  if [[ $# -gt 0 ]]; then
    _rlwrap_expect_script_path="${1}"
  fi
}

##
# _rlwrap_rlRunOptions [OPTIONS]
#
#   OPTIONS
#     options for rlRun
#
# See rlRunOptions in RunCmdViaExpect.
function _rlwrap_rlRunOptions() {
  _rlwrap_rlRun_options+=( "$@" )
}

##
# _rlwrap_ExpectOptions [OPTIONS]
#
#   OPTIONS
#     options for expect tool
#
# See ExpectOptions in RunCmdViaExpect.
function _rlwrap_ExpectOptions() {
  _rlwrap_expect_options+=( "$@" )
}

##
# _rlwrap_Command [COMMAND_OR_OPTION] [COMMAND_OPTIONS]
#
#   COMMAND_OR_OPTION
#     command name or option (depending on a number of Command invocations)
#   COMMAND_OPTIONS
#     command options
#
# See Command in RunCmdViaExpect.
function _rlwrap_Command() {
  if [[ -z "${_rlwrap_expect_script}" ]]; then
    if [[ -n "${1:-}" ]]; then
      _rlwrap_expect_script="${1}.exp"
      _rlwrap_expect_script_scommand="${1}"
      shift
    fi
  fi

  if [[ $# -gt 0 ]]; then
    _rlwrap_expect_script_command_args+=( "$@" )
    _rlwrap_expect_script_scommand="${_rlwrap_expect_script_scommand} $*"
  fi
}

##
# _rlwrap_Input [OPTIONS]
#
#   OPTIONS
#     options for expect script that are used for passing input values to
#     commands that are run from within the script
#
# See Input in RunCmdViaExpect.
function _rlwrap_Input() {
  _rlwrap_expect_script_input_args+=( "$@" )
}

##
# _rlwrap_Status [STATUS_CODE]
#
#   STATUS_CODE
#     expected status/return code of expect script
#
# See Status in RunCmdViaExpect.
function _rlwrap_Status() {
  if [[ $# -gt 0 ]]; then
    _rlwrap_rlRun_status="${1}"
  fi
}

##
# _rlwrap_Comment [COMMENT]
#
#   COMMENT
#     comment to be passed to rlRun
#
# See Comment in RunCmdViaExpect.
function _rlwrap_Comment() {
  if [[ $# -gt 0 ]]; then
    _rlwrap_rlRun_comment="${1}"
  fi
}

##
# FinishRun
#
# See RunCmdViaExpect.
function FinishRun() {
  local __command=""

  unalias Path
  unalias rlRunOptions
  unalias ExpectOptions
  unalias Command
  unalias Input
  unalias Status
  unalias Comment

  if [[ -z "${_rlwrap_expect_script}" ]]; then
    errmsg "RunCmdViaExpect: Missing name of expect script!"
    errmsg "| The name of expect script is deduced from the first"
    errmsg "| argument given to Command."
    return 1
  fi

  if [[ -z "${_rlwrap_rlRun_comment}" ]]; then
    _rlwrap_rlRun_comment="${_rlwrap_expect_script_scommand}"
  fi

  __command="${_rlwrap_expect_script_path}/${_rlwrap_expect_script}"
  __command="${__command} ${_rlwrap_expect_options[*]} --"
  __command="${__command} ${_rlwrap_expect_script_input_args[*]} --"
  __command="${__command} ${_rlwrap_expect_script_command_args[*]}"

  rlRun "${_rlwrap_rlRun_options[@]}" "${__command}" \
    "${_rlwrap_rlRun_status}" "${_rlwrap_rlRun_comment}"
}

##
# CreateTemporaryDirectory
#
# Create a temporary directory and store its path to Result.
function CreateTemporaryDirectory() {
  Result="$(mktemp -d)"
}

##
# PushDir DIRECTORY
#
#   DIRECTORY
#     path to directory
#
# Perform `rlRun pushd DIRECTORY`.
function PushDir() {
  RunCmd pushd "\"$1\""
}

##
# PopDir
#
# Perform `rlRun popd`.
function PopDir() {
  RunCmd popd
}

##
# AtCleanup COMMAND
#
#   COMMAND
#     cleanup action as a command
#
# Insert COMMAND to the beginning of the list of cleanup actions.
function AtCleanup() {
  _CleanupActions=( "$1" "${_CleanupActions[@]}" )
}

##
# AddTest TESTFUNC [DESCRIPTION]
#
#   TESTFUNC
#     function that performs the test
#   DESCRIPTION
#     test description
#
# Add test to the list of tests.
function AddTest() {
  _Tests+=( "$1=${2:-}" )
}

##
# DoSetup
#
# Invoke Setup function and return its status code. Setup must be defined
# before.
function DoSetup() {
  local __status=0

  rlPhaseStartSetup
  if [[ "$(LC_ALL=C type -t Setup)" != "function" ]]; then
    rlFail "Function 'Setup' is not defined. Please, define it."
  else
    Setup
  fi
  __status=$?
  rlPhaseEnd
  return ${__status}
}

##
# DoTests
#
# Run all tests from the tests list.
function DoTests() {
  for __testspec in "${_Tests[@]}"; do
    # __testspec has the format 'testfunc=test description':
    rlPhaseStartTest "${__testspec#*=}"
      "${__testspec%%=*}" || :
    rlPhaseEnd
  done
}

##
# DoCleanup
#
# Run all registered cleanup actions in the reverse order than they were
# registered by AtCleanup.
function DoCleanup() {
  rlPhaseStartCleanup
  for __action in "${_CleanupActions[@]}"; do
    "${__action}" || :
  done
  rlPhaseEnd
}

##
# RunTest
#
# Test runner entry point. Perform setup, run all tests, and perform cleanup.
function RunTest() {
  rlJournalStart

  DoSetup && DoTests
  DoCleanup

  rlJournalPrintText
  rlJournalEnd
}
