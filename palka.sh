#!/bin/sh
# Запускалка Палки. Просто пинает Python-пакет.
cd "$(dirname "$0")"
exec python3 -m palka "$@"
