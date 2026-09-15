# Runway product-ad video

The video dialog supports Photo Slideshow (existing local FFmpeg renderer) and
AI Product Ad (Runway). Select Create Video, choose AI Product Ad, enter product
details, select a style and confirm the paid request. Upload different angles of
the same product. Review product accuracy before publishing. Social publishing
remains paused after video generation.

## Developer account

1. Open https://dev.runwayml.com/ and create an organization.
2. Open API Keys and create a key named `cellaidata`.
3. Store the key in a password manager. Never paste it into chat, screenshots,
   workflow JSON, source code, or browser storage.
4. Add developer credits in Billing. The documented starting minimum is $10.

Official setup: https://docs.dev.runwayml.com/guides/setup/
Pricing: https://docs.dev.runwayml.com/guides/pricing/

As checked on 2026-09-14, the 720p Product Ad recipe is 200 credits for four
seconds plus 36 per additional second. A ten-second video is 416 credits ($4.16
before tax). Prices may change. This integration fixes recipe version 2026-07,
supports 4-15 seconds and 9:16, 16:9 or 1:1. The confirmation is an estimate,
not a provider-enforced spending cap.

## Backend dependency

The backend integration uses the official Python SDK, per the current Runway
Dev guidance. Install it wherever `cellx-extension-api` runs:

```sh
python3 -m pip install -r /opt/cellx-extension-api/requirements-runway.txt
```

The feature deploy helper installs this file before restarting the service.

## Configure the AWS service securely

Have the administrator add `RUNWAYML_API_SECRET` to the backend's protected
environment/secret store and restart `cellx-extension-api` when no job is running.
Do not put the actual key in a shell command (shell history can retain it).

For an additional systemd environment file, an administrator can use:

```sh
sudo install -d -m 700 /etc/cellaidata
sudo touch /etc/cellaidata/runway.env
sudo chmod 600 /etc/cellaidata/runway.env
sudoedit /etc/cellaidata/runway.env
```

In the editor, enter `RUNWAYML_API_SECRET=` followed by the actual key. Then use
`sudo systemctl edit cellx-extension-api` to add:

```ini
[Service]
EnvironmentFile=/etc/cellaidata/runway.env
```

Preserve any existing overrides. Then run:

```sh
sudo systemctl daemon-reload
sudo systemctl restart cellx-extension-api
```

The authenticated `/ext-api/promo-videos/providers` route returns only whether
the key is configured, never its value. The video dialog also shows this status.
Configuration presence does not validate account credits or recipe access.

## Job behavior

- Product images are sent as data URIs to Runway after explicit confirmation;
  originals remain private on the Cell AI Data server.
- API authentication uses the backend environment only.
- A durable request ID prevents a retried submission from creating a second job.
- Resume / Check Status polls the existing task, including after page reload.
- Provider POST requests are never automatically retried. Ambiguous submissions
  require inspection of Runway task history before another generation.
- Status polling also downloads the completed MP4 into private storage. Keep
  the page open or resume within the provider output-link lifetime (24-48 hours).
- Missing credentials, provider failures and failed downloads are not reported
  as successful videos. No live paid generation has been tested without a key.
- One pending AI job is allowed at a time; downloaded videos have an 80 MB cap.
