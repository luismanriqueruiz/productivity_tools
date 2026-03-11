#!/bin/bash
# ─────────────────────────────────────────────
# Ollama Chat — launcher
# ─────────────────────────────────────────────

CONDA_ENV="ollamaapp"
APP_DIR="$HOME/Documents/research/local_llm/"

# Find conda installation
CONDA_BASE=$(conda info --base 2>/dev/null)
if [ -z "$CONDA_BASE" ]; then
    for candidate in "$HOME/miniconda3" "$HOME/anaconda3" "/opt/conda" "/usr/local/anaconda3"; do
        if [ -f "$candidate/etc/profile.d/conda.sh" ]; then
            CONDA_BASE="$candidate"
            break
        fi
    done
fi

if [ -z "$CONDA_BASE" ]; then
    echo "ERROR: Could not find conda installation." >&2
    exit 1
fi

source "$CONDA_BASE/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"

cd "$APP_DIR"

# Open browser after Flask has time to start
(sleep 2 && xdg-open http://localhost:5000) &

python app.py
