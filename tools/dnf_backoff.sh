# Sourced, not run: defines with_backoff for every container-lane script
# that installs from the Hummingbird repository (build_container.sh and
# the cache-key step in build-stage.yml).
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
# attempts is the part that was missing. Every dnf call that must
# succeed goes through this: vulkan-headers lost a libxml2 upgrade
# and libical its @buildsys-build install (conmon) to the same 503
# (issue #1160). It retries downloads and resolution only, never the
# build, and an unsatisfiable graph still fails every attempt and
# then fails the job.
with_backoff() {
  delay=5
  for attempt in 1 2 3 4; do
    status=0
    "$@" || status=$?
    if [ "$status" -eq 0 ]; then
      return 0
    fi
    if [ "$attempt" -eq 4 ]; then
      echo "$1 failed after 4 attempts" >&2
      return "$status"
    fi
    echo "::warning title=dnf retry::$1 attempt $attempt failed, waiting ${delay}s" >&2
    sleep "$delay"
    delay=$((delay * 3))
  done
}
