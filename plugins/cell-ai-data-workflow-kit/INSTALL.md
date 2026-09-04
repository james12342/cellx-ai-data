# Install Cell AI Data Workflow Kit

This plugin is designed to be distributed from the `cellx-ai-data` repository.

## Option A: Install From This Repo Marketplace

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
