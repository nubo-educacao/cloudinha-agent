# Deploying Cloudinha Agent to Google Cloud Run

This agent is configured to run on Google Cloud Run, which is a low-cost, serverless container platform perfect for this type of application.

## Prerequisites

1.  **Google Cloud SDK (gcloud)** installed and authenticated. [Download and Install Here](https://cloud.google.com/sdk/docs/install)
2.  **Docker** installed (optional, but good for local testing).
3.  **Project ID**: You need your Google Cloud Project ID.

## Steps

### 1. Authenticate with Google Cloud

```powershell
gcloud auth login
gcloud config set project gen-lang-client-0831624563
```

### 2. Enable Required Services

```powershell
gcloud services enable cloudbuild.googleapis.com run.googleapis.com containerregistry.googleapis.com
```

### 3. Deploy

Run the following command in the `cloudinha-agent` directory. Replace `YOUR_SERVICE_NAME` (e.g., `cloudinha-agent`) and `YOUR_REGION` (e.g., `us-central1` or `southamerica-east1` for Sao Paulo).

**Important**: You must pass your environment variables (API Keys) here.

```powershell
gcloud run deploy cloudinha-agent `
  --source . `
  --platform managed `
  --region southamerica-east1 `
  --allow-unauthenticated `
  --set-env-vars SUPABASE_URL="your_supabase_url",SUPABASE_SERVICE_KEY="your_supabase_key",OPENAI_API_KEY="your_openai_key",GOOGLE_API_KEY="your_google_key"
```

*Note: For production, consider using Secret Manager for secrets.*

### 4. Verify

After deployment, gcloud will output a Service URL (e.g., `https://cloudinha-agent-xyz-uc.a.run.app`).
Visit that URL (or add `/docs` to the end) to verify it's running.

## Local Testing (Docker)

```bash
docker build -t cloudinha-agent .
docker run -p 8080:8080 -e PORT=8080 cloudinha-agent
```
