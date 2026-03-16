# ResumeRank — Deployment Guide

## Run Locally
```
pip install -r require.txt
python final.py
```
Open: http://localhost:5000

## Deploy on Render.com
1. Push this folder to GitHub
2. Go to render.com → New Web Service
3. Connect your GitHub repo
4. Build Command: `pip install -r require.txt`
5. Start Command: `gunicorn final:app`
6. Click Deploy!
