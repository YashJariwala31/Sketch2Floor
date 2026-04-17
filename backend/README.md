# Connector Backend

This Django backend is the API layer for the mobile app.

## What it already includes

- `FloorplanJob` model for uploaded sketch-processing jobs
- API endpoints for health, list/create jobs, and retrieve/update jobs
- media storage for uploaded sketches
- output-path planning for wall masks, geometry, overlays, and fused floorplan files

## Planned next step

Hook these jobs into the existing Python floorplan pipeline in the repo root:

- `wall_pipeline`
- `opening_pipeline`
- `utils.floorplan_fusion`

## Run

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```
