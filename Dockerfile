# Same Python as local training, so the pickled model loads identically.
FROM python:3.14-slim

# Hugging Face Spaces runs containers as a non-root user with uid 1000.
# Running as non-root is also good practice anywhere.
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib
WORKDIR /home/user/app

# Copy requirements first: Docker caches each step, so code edits don't
# trigger a slow reinstall of every library.
COPY --chown=user requirements-api.txt .
RUN pip install --no-cache-dir --user -r requirements-api.txt

COPY --chown=user src/ src/
COPY --chown=user models/claim_model.joblib models/claim_model.joblib

# Hosts tell the app which port to listen on through $PORT (Render sets it);
# fall back to 7860, the Hugging Face Spaces default. The shell form of CMD
# is needed so ${PORT} gets expanded.
EXPOSE 7860
CMD uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-7860}
