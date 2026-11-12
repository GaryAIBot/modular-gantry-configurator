# GantryLab — Modular Gantry Configurator POC

A full-stack, physics-motivated XYZ gantry configurator. It combines 12 module groups, deterministic load/deflection calculations, three optimization strategies, an interactive Three.js model, engineering charts, manual overrides, JSON export/import, and an optional OpenAI assistant.

All component data and results are synthetic demonstration data. This is not a verified engineering calculation tool.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.index:app --reload
```

Open `http://127.0.0.1:8000`.

## Test

```bash
pytest -q
```

The application remains fully functional without `OPENAI_API_KEY`; the chat then uses a deterministic local configuration assistant.

