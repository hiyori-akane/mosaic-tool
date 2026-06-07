#!/bin/bash
set -e

echo "=== Auto-Mosaic Setup ==="
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Create models directory
mkdir -p models

# 2. Virtual environment setup
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
else
    echo "Virtual environment already exists."
fi

source .venv/bin/activate
echo "Upgrading pip..."
pip install --upgrade pip

echo "Installing requirements..."
pip install -r requirements.txt

# 3. Model setup
MODEL_DEST="models/ntd11_anime_nsfw_segm_v5.pt"
if [ ! -f "$MODEL_DEST" ]; then
    echo "Searching for the model in ~/ComfyUI/..."
    COMFY_MODEL="$HOME/ComfyUI/models/yolov8/ntd11_anime_nsfw_segm_v5.pt"
    if [ -f "$COMFY_MODEL" ]; then
        echo "Found ComfyUI model. Copying to models/..."
        cp "$COMFY_MODEL" "$MODEL_DEST"
    else
        echo "WARNING: Model not found at '$COMFY_MODEL' or locally at '$MODEL_DEST'."
        echo "Please copy your 'ntd11_anime_nsfw_segm_v5.pt' to: $SCRIPT_DIR/models/"
        echo "Alternatively, you can download it from Civitai (look for 'Anime NSFW Detection / ADetailer All-in-One')."
    fi
else
    echo "Model already exists at '$MODEL_DEST'."
fi

echo "Setup complete! Run 'source .venv/bin/activate' to activate the environment."
