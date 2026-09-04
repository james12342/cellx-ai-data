---
name: cell-ai-data-workflows
description: Build, customize, and deploy Cell AI Data workflow demos, including real estate listing alerts, AI property recommendations, Gmail delivery, Amazon bestseller research, Yahoo Finance analysis, website crawlers, and property promo videos.
---

# Cell AI Data Workflows

Use this skill when the user wants to create, import, edit, explain, or deploy Cell AI Data / CellX workflow demos.

## What This Plugin Contains

- Workflow JSON templates under `workflow-templates/`
- Reusable scripts under `scripts/`
- Guidance for connecting CellX workflow nodes, backend secrets, and AWS deployment

## Available Workflow Templates

- `rentcast-irvine-ai-property-recommendations-email.json`: Fetch Irvine sale listings, analyze them with OpenAI, write AI fields into `cx_property`, query client records, and send Gmail recommendations.
- `rentcast-irvine-active-listings-email.json`: Fetch active Irvine sale listings and email a customer-ready summary.
- `zillow-irvine-price-cut-lead-alert.json`: Demo template for price-cut lead alerts. Treat this as a demo pattern; use authorized listing APIs for production.
- `amazon-bestseller-chatgpt-supplier-email.json`: Research Amazon bestseller products, hand data to ChatGPT, transform results, and send an email report.
- `amazon-bestsellers-script-demo.json`: Simple custom script runner demo for Amazon Best Sellers rows.
- `yahoo-most-active-stocks.json`: Fetch Yahoo most-active stocks and send the data to an AI analysis step.
- `tarbut-site-crawler.json`: Public website information extraction demo for TVT/Tarbut.
- `valorant-agents-crawler.json`: Public page extraction demo for VALORANT agents.

## Available Scripts

- `property_promo_video.py`: Generate a 20-second real estate promo MP4 from listing photos and property JSON.
- `deploy_cellx_aws.ps1`: Deploy Cell AI Data extension files to an AWS Lightsail host when the user provides the host and SSH key.

## Recommended CellX Workflow Patterns

For real estate AI recommendations:

```text
Schedule
-> RentCast Irvine Sale Listings
-> OpenAI GPT-5 Property Analyst
-> CellX Bulk Import AI Properties
-> CellX Query Property Clients
-> JSON Transform
-> Gmail
-> Write History Log
```

For property video generation:

```text
CellX Query Property
-> Upload or select property images
-> OpenAI Listing Script Writer
-> Generate Promo Video
-> Gmail or Export MP4
```

## Backend Secrets

Never put secrets directly in workflow templates, GitHub, screenshots, or plugin files. Use backend environment variables such as:

- `OPENAI_API_KEY`
- `RENTCAST_API_KEY`
- `GMAIL_APP_PASSWORD`
- `ATTOM_API_KEY`
- `BRIDGE_API_KEY`

Workflow templates should reference secret names only, for example `platformSecretName: OPENAI_API_KEY`.

## Data and Compliance Notes

- Prefer authorized APIs such as RentCast, MLS/IDX, Bridge, ATTOM, or Estated for real estate data.
- Do not automate bulk scraping of sites whose terms prohibit crawling or scraping.
- Treat AI real estate output as screening guidance, not legal, tax, mortgage, appraisal, or investment advice.
- Avoid storing customer PII in templates. Use sample addresses and placeholder emails in distributable files.

## How To Help The User

When the user asks for a Cell AI Data workflow:

1. Pick the closest JSON template from `workflow-templates/`.
2. Adjust node names, positions, field mappings, and settings to the user's current CellX table names.
3. Keep secrets as backend secret references.
4. If requested, deploy changed UI/API files to AWS using the user's explicit SSH host and key.
5. If requested, commit and push changes to GitHub after scanning for secrets.

