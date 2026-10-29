#!/bin/sh
set -e
# Apply database migrations before the API starts (the worker skips this).
if [ "$RUN_MIGRATIONS" = "true" ]; then
  alembic upgrade head
fi
exec "$@"
