# Deployment Plan

This document outlines the deployment strategy for the PPFAS Mutual Fund FAQ RAG Assistant.

## Architecture Overview

```
┌─────────────────┐
│  GitHub Actions │ (Scheduler - Daily Cron)
│                 │
│  - Scraping     │
│  - Chunking     │
│  - Embedding    │
│  - Upsert       │
└────────┬────────┘
         │
         │ Updates Chroma Cloud
         ↓
┌─────────────────┐
│   Chroma Cloud  │ (Vector Database)
│                 │
│  - Embeddings   │
│  - Chunks       │
└────────┬────────┘
         │
         │ Queried by Backend
         ↓
┌─────────────────┐
│     Render      │ (Backend API)
│                 │
│  - FastAPI      │
│  - Retrieval    │
│  - Generation   │
│  - Safety       │
└────────┬────────┘
         │
         │ Serves API
         ↓
┌─────────────────┐
│     Vercel      │ (Frontend - Next.js)
│                 │
│  - Next.js 14   │
│  - React        │
│  - TypeScript   │
│  - Tailwind CSS │
└─────────────────┘
```

## 1. GitHub Actions - Scheduler

### Purpose
Run the ingestion pipeline (Phase 4.0-4.3) daily to keep the vector database updated with the latest fund information.

### Configuration

**File:** `.github/workflows/scheduler.yml`

```yaml
name: Daily Ingestion Scheduler

on:
  schedule:
    # Run daily at 09:15 IST (03:45 UTC)
    - cron: '45 3 * * *'
  workflow_dispatch: # Allow manual trigger from GitHub UI

jobs:
  ingest:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      
      - name: Install dependencies
        run: |
          pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Run ingestion pipeline
        env:
          CHROMA_API_KEY: ${{ secrets.CHROMA_API_KEY }}
          CHROMA_TENANT: ${{ secrets.CHROMA_TENANT }}
          CHROMA_DATABASE: ${{ secrets.CHROMA_DATABASE }}
        run: |
          python -m src.ingestion.run_pipeline
      
      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: ingestion-logs
          path: logs/
          retention-days: 30
```

### Required GitHub Secrets

Set these in **Repository Settings → Secrets and variables → Actions**:

| Secret Name | Description |
|-------------|-------------|
| `CHROMA_API_KEY` | Chroma Cloud API key |
| `CHROMA_TENANT` | Chroma Cloud tenant ID |
| `CHROMA_DATABASE` | Chroma Cloud database name |

### Monitoring

- **Success/Failure**: GitHub Actions will send notifications based on repository settings
- **Logs**: Uploaded as artifacts for 30 days
- **Manual Trigger**: Can be triggered from GitHub Actions tab for immediate updates

## 2. Render - Backend API

### Purpose
Host the FastAPI backend that handles retrieval, generation, and safety orchestration.

### Configuration

**File:** `render.yaml` (optional, for Blueprint deployments)

```yaml
services:
  - type: web
    name: ppfas-rag-backend
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn src.api.app:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PORT
        value: 8000
      - key: CHROMA_API_KEY
        sync: false # Set in Render dashboard
      - key: CHROMA_TENANT
        sync: false
      - key: CHROMA_DATABASE
        sync: false
      - key: GROQ_API_KEY
        sync: false
```

### Deployment Steps

1. **Create Render Account**
   - Sign up at [render.com](https://render.com)
   - Connect GitHub repository

2. **Create New Web Service**
   - Select "Web Service"
   - Connect the repository
   - Configure:
     - **Name**: `ppfas-rag-backend`
     - **Environment**: Python 3
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `uvicorn src.api.app:app --host 0.0.0.0 --port $PORT`

3. **Set Environment Variables**
   - Go to Environment tab
   - Add the following:
     ```
     PORT=8000
     CHROMA_API_KEY=your_chroma_api_key
     CHROMA_TENANT=your_chroma_tenant_id
     CHROMA_DATABASE=your_chroma_database_name
     GROQ_API_KEY=your_groq_api_key
     GROQ_MODEL=llama-3.1-8b-instant
     GROQ_TEMPERATURE=0.1
     GROQ_MAX_TOKENS=300
     ```

4. **Deploy**
   - Render will automatically deploy on push to main branch
   - Or click "Manual Deploy" for immediate deployment

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `PORT` | Render-assigned port | `8000` |
| `CHROMA_API_KEY` | Chroma Cloud API key | `sk-...` |
| `CHROMA_TENANT` | Chroma Cloud tenant ID | `f24bea7d-e864-4010-a391-12b7c735a180` |
| `CHROMA_DATABASE` | Chroma Cloud database name | `grow-rag-test` |
| `GROQ_API_KEY` | Groq API key | `gsk-...` |
| `GROQ_MODEL` | Groq model name | `llama-3.1-8b-instant` |
| `GROQ_TEMPERATURE` | Generation temperature | `0.1` |
| `GROQ_MAX_TOKENS` | Max tokens for generation | `300` |

### Monitoring

- **Logs**: Available in Render dashboard
- **Metrics**: CPU, memory, response time
- **Health Check**: `GET /health` endpoint
- **Auto-scaling**: Can be configured based on traffic

## 3. Vercel - Frontend (Next.js)

### Purpose
Host the Next.js frontend with the Fintech Clarity design system.

### Configuration

**File:** `vercel.json` (optional, for custom configuration)

```json
{
  "buildCommand": "cd frontend && npm run build",
  "outputDirectory": "frontend/.next",
  "installCommand": "cd frontend && npm install",
  "framework": "nextjs"
}
```

### Deployment Steps

1. **Create Vercel Account**
   - Sign up at [vercel.com](https://vercel.com)
   - Connect GitHub repository

2. **Import Project**
   - Select the repository
   - Configure:
     - **Framework Preset**: Next.js
     - **Root Directory**: `frontend`
     - **Build Command**: `npm run build`
     - **Output Directory**: `.next`

3. **Set Environment Variables**
   - In Vercel dashboard, add:
     ```
     NEXT_PUBLIC_API_URL=https://your-backend-url.onrender.com
     ```

4. **Deploy**
   - Vercel will automatically deploy on push to main branch
   - Or click "Deploy" for immediate deployment

### Required Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `NEXT_PUBLIC_API_URL` | Render backend URL | `https://ppfas-rag-backend.onrender.com` |

### Architecture Notes

- **Backend**: FastAPI on Render (port 8000) - serves API only
- **Frontend**: Next.js on Vercel (separate deployment) - official UI
- **Communication**: Frontend fetches from backend API via CORS
- **Old Static HTML**: Removed - Next.js is now the official UI
- **Static file serving**: Removed from FastAPI - no longer serves HTML

### Monitoring

- **Logs**: Available in Vercel dashboard
- **Analytics**: Page views, unique visitors
- **Performance**: Core Web Vitals

## 4. Environment Variables Summary

### GitHub Actions Secrets
- `CHROMA_API_KEY`
- `CHROMA_TENANT`
- `CHROMA_DATABASE`

### Render Environment Variables
- `PORT`
- `CHROMA_API_KEY`
- `CHROMA_TENANT`
- `CHROMA_DATABASE`
- `GROQ_API_KEY`
- `GROQ_MODEL`
- `GROQ_TEMPERATURE`
- `GROQ_MAX_TOKENS`

### Vercel Environment Variables
- `BACKEND_URL` (if using proxy)

## 5. Deployment Checklist

### Pre-deployment
- [ ] All environment variables configured
- [ ] `.env.example` updated with all required variables
- [ ] Requirements.txt includes all dependencies
- [ ] GitHub Actions workflow file created
- [ ] Render configuration ready
- [ ] Vercel configuration ready

### GitHub Actions (Scheduler)
- [ ] Repository connected to GitHub Actions
- [ ] Secrets configured in GitHub
- [ ] Workflow file pushed to `.github/workflows/`
- [ ] Test manual trigger
- [ ] Verify cron schedule (09:15 IST)

### Render (Backend)
- [ ] Render account created
- [ ] Repository connected
- [ ] Environment variables set
- [ ] Build and start commands configured
- [ ] Deployed successfully
- [ ] Health check endpoint accessible
- [ ] API endpoints tested

### Vercel (Frontend)
- [ ] Vercel account created
- [ ] Repository connected
- [ ] Output directory configured
- [ ] API base URL updated
- [ ] Deployed successfully
- [ ] Frontend accessible
- [ ] API calls working

### Post-deployment
- [ ] End-to-end testing
- [ ] Monitor logs for errors
- [ ] Set up alerts for failures
- [ ] Document API endpoints
- [ ] Update documentation

## 6. Security Considerations

1. **API Keys**: Never commit to repository, use environment variables/secrets
2. **CORS**: Configure Render to allow requests from Vercel domain
3. **Rate Limiting**: Implement rate limiting on backend endpoints
4. **Authentication**: Consider adding authentication if needed
5. **HTTPS**: All platforms (Render, Vercel) provide HTTPS by default

## 7. Cost Estimation

### GitHub Actions
- Free tier: 2000 free minutes/month
- Estimated usage: ~5 minutes/day = 150 minutes/month
- **Cost: Free**

### Render
- Free tier: 750 hours/month (enough for 24/7)
- **Cost: Free** (with limitations)
- Paid tier: $7/month for better performance

### Vercel
- Free tier: 100GB bandwidth/month
- **Cost: Free** (with limitations)
- Pro tier: $20/month for better performance

**Total Estimated Cost: Free** (using free tiers)

## 8. Disaster Recovery

### Backup Strategy
- **Chroma Cloud**: Already handles data persistence
- **GitHub**: Code repository backup
- **Logs**: Retain for 30 days via GitHub Actions artifacts

### Rollback Plan
- **Backend**: Render supports deployment rollback
- **Frontend**: Vercel supports deployment rollback
- **Scheduler**: GitHub Actions can be disabled or modified

### Monitoring & Alerts
- **GitHub Actions**: Email notifications on failure
- **Render**: Email alerts on deployment failures
- **Vercel**: Email alerts on deployment failures

## 9. Maintenance

### Regular Tasks
- Monitor GitHub Actions scheduler runs
- Review Render logs for errors
- Update dependencies regularly
- Rotate API keys periodically
- Review and update documentation

### Updates
- **Backend**: Push to main branch triggers auto-deploy
- **Frontend**: Push to main branch triggers auto-deploy
- **Scheduler**: Modify workflow file and push

## 10. Troubleshooting

### Scheduler Not Running
- Check GitHub Actions logs
- Verify secrets are set correctly
- Check cron schedule syntax
- Try manual workflow dispatch

### Backend Not Responding
- Check Render logs
- Verify environment variables
- Check if service is running
- Test health endpoint

### Frontend API Errors
- Check browser console for errors
- Verify API base URL is correct
- Check CORS configuration
- Verify backend is accessible

### Data Not Updating
- Check scheduler logs
- Verify Chroma Cloud credentials
- Check if scraping is working
- Manually trigger scheduler
