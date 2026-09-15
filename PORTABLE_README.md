# CellX Workflow Portable

This folder runs the CellX Workflow Designer locally on a Windows computer.

## Requirements

- Windows 10 or newer
- Python 3 installed and available as `python`
- Chrome or Edge for microphone-based voice input

## Start

Double-click:

```text
run_cellx_portable.bat
```

It opens:

```text
http://127.0.0.1:3001/agent/
```

## Enable AI Voice Builder

Set an OpenAI API key before launching:

```powershell
$env:OPENAI_API_KEY="your-key-here"
.\run_cellx_portable.ps1
```

Open AI Voice Builder and click Connect Voice. Allow microphone access. The assistant can converse, draft workflows, and apply a reviewed draft when asked. Disconnect ends the call and releases the microphone. Closing the panel also disconnects. Voice requires internet access and OpenAI API billing; it does not require Codex.

The standard OpenAI key stays on the backend. The browser receives only a short-lived Realtime session credential. Set `WORKFLOW_VOICE_MODEL` to override the default `gpt-realtime-2.1` model if needed for your account.

Local same-origin requests use the portable server directly. On the hosted website, enter your workflow management access token in the voice panel; this is not your OpenAI API key. A missing backend key or unavailable model is reported in the panel.

Workflow changes appear as a pending draft. Apply it with the draft button or by asking the assistant. Applying saves the design in this browser; it does not run orders, enable a schedule, or deploy a workflow. Updates are rejected if the active workflow has changed since drafting.

## Notes For Customers

### Instagram Browse, Like and Comment

Run `install_browser_dependencies.bat` once, then launch the portable edition. In Browse Templates, import **Instagram Browse, Like and Comment**. Microsoft Edge must be installed. This template cannot execute in AWS; use the local edition on the computer whose browser you want to operate.

Select the Instagram node and click Test Selected for configuration validation only. Run Workflow opens a separate visible Edge profile. Log in manually the first time; it waits up to five minutes, including browsing time. The runner processes a randomly chosen count of 5-8 eligible posts, likes unliked posts, and submits the public comment `hello, I like your image`. Posts without comment controls are reported and skipped for commenting. Ads without a normal post link are skipped.

Click Stop Instagram to cancel remaining work, or close the controlled browser window. Already submitted likes/comments are not undone. The runner records attempted comments before submission and does not retry uncertain submissions. A failed verification stops the run for inspection. Browser state and the deduplication journal stay under the current Windows user's local application-data folder, outside the portable distribution.

Browser selectors may change when Instagram changes its interface. The independent runner needs its own login; it does not copy cookies from Codex or other browser profiles.

- Workflow templates and scripts are stored inside this folder.
- Database workflows need a reachable MySQL database and the usual `DB_NAME`, `DB_USER`, and `DB_PASSWORD` environment variables.
- Secrets should be configured as environment variables, not saved inside workflow JSON.
