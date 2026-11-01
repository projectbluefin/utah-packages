#!/bin/bash

set -eux

ls -la
uname -a
rpm -qi criu || true
criu --version

echo "Start container"
podman --log-level debug run -d quay.io/adrianreber/counter

echo "See which containers are running"
podman ps

echo "Connect to the container"
curl `podman inspect -l | jq -r '.[0].NetworkSettings.IPAddress'`:8088

echo "Checkpoint container"
podman --log-level debug container checkpoint -l

podman ps -a
echo "Restore container"
podman --log-level debug container restore -l

podman ps -a
echo "Check if we can connect to the restored container"
curl `podman inspect -l | jq -r '.[0].NetworkSettings.IPAddress'`:8088

ls -la
