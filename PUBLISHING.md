# Publishing The Cell AI Data Codex Plugin

This repository is ready to act as a public Codex plugin marketplace source.

## What Is Already Included

- Plugin manifest: `plugins/cell-ai-data-workflow-kit/.codex-plugin/plugin.json`
- Repo marketplace: `.agents/plugins/marketplace.json`
- Install guide: `plugins/cell-ai-data-workflow-kit/INSTALL.md`
- Shareable package script: `scripts/package_cell_ai_data_plugin.ps1`

## Publish Through GitHub

1. Push the latest repository changes to GitHub.

```powershell
git status
git add README.md PUBLISHING.md plugins/cell-ai-data-workflow-kit
git commit -m "Document public Codex plugin publishing"
git push origin main
```

2. Share this repository URL with users:

```text
https://github.com/james12342/cellx-ai-data
```

3. Tell users to install from the repo-local marketplace:

```powershell
git clone https://github.com/james12342/cellx-ai-data.git
cd cellx-ai-data
codex plugin marketplace add .agents/plugins
codex plugin add cell-ai-data-workflow-kit@cell-ai-data
```

4. Users should open a new Codex task after installing the plugin.

## Share As A Zip

For direct file sharing, package only the plugin folder:

```powershell
.\scripts\package_cell_ai_data_plugin.ps1
```

The generated zip is written to `dist/` and can be attached to a release.

## Official Marketplace

The repo marketplace above makes the plugin installable by people who have the repository.
If Codex offers an official public marketplace submission flow, use this repository as the
source package and submit:

- Plugin name: `cell-ai-data-workflow-kit`
- Marketplace name: `cell-ai-data`
- Repository: `https://github.com/james12342/cellx-ai-data`
- Plugin folder: `plugins/cell-ai-data-workflow-kit`
- Marketplace folder: `.agents/plugins`

Do not submit API keys, Gmail app passwords, AWS PEM files, or real customer data.
