#!/bin/bash
set -e
podman-compose up -d --build
podman-compose exec ubuntu1804 bash
podman-compose down 
