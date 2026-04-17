# Running Connector

This repo now has three main parts:

- the original floorplan pipeline at the repo root
- the Django backend in `backend/`
- the Expo React Native mobile app in `mobile/`

## 1. Backend setup

From `C:\Users\yashj\Desktop\connector\backend`:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-pipeline.txt
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Install PyTorch separately before real pipeline runs:

CPU:

```powershell
pip install torch==2.6.0
```

NVIDIA CUDA 12.4:

```powershell
pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cu124
```

Optional demo data:

```powershell
python manage.py seed_demo_jobs --count 2
```

Useful API endpoints:

```text
GET  /api/health/
GET  /api/jobs/
POST /api/jobs/
POST /api/jobs/demo/
POST /api/jobs/<id>/start/
```

## 2. Mobile setup

From `C:\Users\yashj\Desktop\connector\mobile`:

```powershell
npm install
npx expo start
```

If you want Android:

```powershell
npx expo run:android
```

The mobile app points at:

```text
http://10.0.2.2:8000/api
```

That is the correct Android emulator alias for your local Django server.

## 3. Typical development flow

1. Start Django in `backend/`
2. Start Expo in `mobile/`
3. Open the Android emulator
4. Create a demo job or upload a sketch
5. Start the uploaded job from the results screen

## 4. Important note about real processing

Real processing uses the existing repo pipeline:

- `wall_pipeline`
- `opening_pipeline`
- `utils.floorplan_fusion`
- `utils.combined_overlay`

So the Python environment used for Django also needs the pipeline dependencies installed, including the ML/image stack already used by the repo.
