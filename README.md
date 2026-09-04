# Cell AI Data

Cell AI Data is a CellX workflow automation demo project for building AI-assisted business workflows, custom data pipelines, and customer-facing automation experiences.

The project includes:

- A browser-based Workflow Designer
- A Python backend for workflow testing and integration previews
- Customer script runners for approved automation scripts
- CellX database query/import/export workflow nodes
- OpenAI, Gmail, RentCast, Amazon, Yahoo Finance, and website crawler demo workflows
- A Codex plugin package for sharing the workflow kit with other Codex users

## Live Demo

- Workflow app: https://app.cellaidata.com/workflow/
- Website: https://cellaidata.com

## Main Project Structure

```text
cellx-extension-ui/
  index.html
  app.js
  styles.css
  workflow-templates/

cellx-extension-api/
  server.py
  customer-scripts/

workflow-templates/
  *.json

plugins/cell-ai-data-workflow-kit/
  .codex-plugin/plugin.json
  skills/
  scripts/
  workflow-templates/

scripts/
  deploy_cellx_aws.ps1
  package_cell_ai_data_plugin.ps1
  property_promo_video.py
```

## Workflow Templates

The workflow page includes a template browser for quickly importing generated JSON workflows.

Included templates:

- RentCast Irvine AI Property Recommendations Email
- RentCast Irvine Active Listings Email
- Amazon Bestseller Supplier Research to ChatGPT and Email
- Amazon Best Sellers Script Demo
- Yahoo Finance Most Active Stocks
- TVT Tarbut Website Crawler
- VALORANT Agents Crawler
- Zillow Irvine Price Cut Lead Alert

## Codex Plugin

This repository includes a Codex plugin:

```text
plugins/cell-ai-data-workflow-kit/
```

It packages workflow templates, reusable scripts, and a Codex skill for creating Cell AI Data workflows.

Install from the repo-local marketplace:

```powershell
git clone https://github.com/james12342/cellx-ai-data.git
cd cellx-ai-data
codex plugin marketplace add .agents/plugins
codex plugin add cell-ai-data-workflow-kit@cell-ai-data
```

Open a new Codex task after installation so the plugin skill is loaded.

For publishing and sharing instructions, see `PUBLISHING.md`.

## Backend Secrets

Do not store live credentials in GitHub or workflow templates. Configure them on the backend or AWS host:

```text
OPENAI_API_KEY
RENTCAST_API_KEY
GMAIL_APP_PASSWORD
ATTOM_API_KEY
BRIDGE_API_KEY
```

Templates should reference backend secret names only.

## AWS Deployment

The current AWS layout is:

```text
/opt/cellx-extension-api/
  server.py
  customer-scripts/

/var/www/cellx-extension-ui/
  index.html
  app.js
  styles.css
  workflow-templates/
```

Deployment helper:

```powershell
.\scripts\deploy_cellx_aws.ps1
```

## Safety

This repository intentionally avoids committing API keys, Gmail app passwords, AWS private keys, real customer contact lists, and generated output files.
