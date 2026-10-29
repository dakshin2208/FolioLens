FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app
# Install dependencies first (cached layer), then copy the source.
COPY pyproject.toml ./
RUN python -c "import tomllib; d = tomllib.load(open('pyproject.toml', 'rb')); \
print('\\n'.join(d['project']['dependencies']))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt

COPY . .
# Make the code readable by the non-root user, whatever permissions the files had on the host.
RUN useradd --create-home --uid 10001 foliolens \
    && chmod -R a+rX /app && chmod 755 /app/docker-entrypoint.sh \
    && mkdir -p /app/data/uploads && chown -R foliolens /app/data
USER foliolens

EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
