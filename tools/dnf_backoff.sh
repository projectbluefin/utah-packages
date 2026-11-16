# Sourced, not run: defines with_backoff for container-lane scripts that
# install from the Hummingbird repository (build_container.sh).
#
# The Hummingbird repository is one host with no mirrors, so a bad
# minute there is a failed build. retries=10 and timeout=120 in
# dnf.conf cover a slow transfer, which is what Curl error 28 was,
# but not a refusal: snowball died on the S3 backend answering
#
#   Status code: 503 for .../python3-setuptools-83.0.0-2.1.hum1.rpm
#   No more mirrors to try - All mirrors were already tried
#
# after four attempts inside one second. librepo retries with no
# backoff, so all four hit the same bad moment. Waiting between
# attempts is the part that was missing. It retries downloads and
# resolution only, never the build, and an unsatisfiable graph still
# fails every attempt and then fails the job.
#
# A last attempt that failed on a download leaves
# $REPORT_DIR/infra-failure (default /work/reports), so the bump gate
# does not hold a version that never got a build (#1179). The marker
# lives here, in the one shared helper, so every call that goes through
# with_backoff marks an outage the same way.
with_backoff() {
  delay=5
  log=$(mktemp)
  for attempt in 1 2 3 4; do
    status=0
    ( set -o pipefail; "$@" 2>&1 | tee "$log" ) || status=$?
    if [ "$status" -eq 0 ]; then
      rm -f "$log"
      return 0
    fi
    if [ "$attempt" -eq 4 ]; then
      echo "$1 failed after 4 attempts" >&2
      if grep -qE 'All mirrors were tried|No more mirrors to try|Curl error|Cannot download|Status code: 5[0-9][0-9]' "$log"; then
        mkdir -p "${REPORT_DIR:-/work/reports}"
        echo "$1" > "${REPORT_DIR:-/work/reports}/infra-failure"
      fi
      rm -f "$log"
      return "$status"
    fi
    echo "::warning title=dnf retry::$1 attempt $attempt failed, waiting ${delay}s" >&2
    sleep "$delay"
    delay=$((delay * 3))
  done
}
