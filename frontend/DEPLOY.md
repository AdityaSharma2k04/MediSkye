# Deploy MediSkye Frontend to Cloudflare Pages

## Prerequisites
- GitHub repo with code pushed to `main`
- Cloudflare account (free tier)

## Steps

1. Go to https://dash.cloudflare.com → Workers & Pages → Create → Pages
2. Connect Git → select the MediSkye repo
3. Build settings:
   - Framework preset: **Vite**
   - Build command: `cd frontend && npm install && npm run build`
   - Build output directory: `frontend/dist`
   - Root directory: *(leave blank)*
4. Environment variables:
   - `VITE_API_URL` = `VITE_API_URL = https://mediskye-backend.onrender.com`
     (set AFTER HF Space is deployed)
5. Click **Save and Deploy**

## After Deploy

1. Copy the resulting URL (e.g. `https://mediskye.pages.dev`)
2. Go to HF Space settings → add secret `ALLOWED_ORIGINS` = that URL
3. Redeploy or restart the HF Space
4. Test: register → upload → query

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| CORS error | `ALLOWED_ORIGINS` on HF Space must match frontend URL exactly |
| 404 on API | `VITE_API_URL` wrong |
| Blank page | Check browser console |
