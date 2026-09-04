# Install Cell AI Data Workflow Kit

This plugin is designed to be distributed from the `cellx-ai-data` repository.

## Option A: Install From GitHub Repo Marketplace

Clone the repository:

```powershell
git clone https://github.com/james12342/cellx-ai-data.git
cd cellx-ai-data
```

From the repository root, add the marketplace folder in Codex:

```powershell
codex plugin marketplace add .agents/plugins
codex plugin add cell-ai-data-workflow-kit@cell-ai-data
```

After installation, open a new Codex task so the plugin skill is loaded.

Try:

```text
Use Cell AI Data Workflow Kit to create a real estate AI recommendation workflow.
```

## Option B: Copy Plugin Folder Locally

Copy `plugins/cell-ai-data-workflow-kit` into your local Codex plugins folder, then create or update your personal marketplace entry to point at:

```text
./plugins/cell-ai-data-workflow-kit
```

## What To Configure

The plugin never stores live secrets. Configure these on your backend or AWS host:

```text
OPENAI_API_KEY
RENTCAST_API_KEY
GMAIL_APP_PASSWORD
ATTOM_API_KEY
BRIDGE_API_KEY
```

## Validate

From the repository root:

```powershell
python <path-to-plugin-creator>\scripts\validate_plugin.py plugins\cell-ai-data-workflow-kit
```

When working inside Codex, use the bundled `plugin-creator` validation script if available.

## Sharing

This plugin can be shared in two practical ways:

- Share the GitHub repository and ask users to install from `.agents/plugins`.
- Run `.\scripts\package_cell_ai_data_plugin.ps1` from the repository root and attach the zip in `dist/` to a release.

An official Codex marketplace listing, if available, should use this repository as the source and must not include live secrets.
