# CellX AWS Sync

Use this when you want to open this project from another computer with Codex and deploy changes to AWS.

## One-time setup on another computer

1. Install Git, Python, Node.js, and Codex.
2. Clone or copy this project to the new computer.
3. Put the Lightsail SSH key on that computer, for example:

```powershell
C:\Users\<you>\Downloads\LightsailDefaultKey-us-west-2.pem
```

4. Do not commit `.pem` files. They are ignored by `.gitignore`.

If Git says `dubious ownership`, run this once with the actual project path:

```powershell
git config --global --add safe.directory "C:/Users/<you>/Documents/New project"
```

## Deploy to AWS

From the project root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy_cellx_aws.ps1
```

If the key is in a different place:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy_cellx_aws.ps1 -KeyPath "C:\path\to\LightsailDefaultKey-us-west-2.pem"
```

This updates:

- Workflow UI: `https://app.cellaidata.com/workflow/`
- Extension API: `https://app.cellaidata.com/ext-api/`
- Marketing homepage: `https://cellaidata.com/`

The script restarts `cellx-extension-api` after uploading backend changes.

## Recommended workflow

```powershell
git pull
# edit with Codex
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\deploy_cellx_aws.ps1
git status
git add .
git commit -m "Update CellX workflow"
git push
```

Use GitHub or another Git remote as the source of truth. OneDrive is okay for backup, but Git is safer for multi-computer development because it tracks exactly what changed.
