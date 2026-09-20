# Automatic Web Collector

Deployed automatic Selenium mode alongside Chrome helper mode.

## Usage
Refresh Agent Builder, select Web Collector, choose Automatic Chrome (no extension), enter Website URL and Fields. Maximum list pages: 1–5. Detail pages: 0–10, one level, same host. A detail-link CSS selector is required for detail collection. Default pagination recognizes rel=next or Next aria-label; other sites need the next-page CSS selector. Collect or Test Selected uses the configured mode. Voice collection uses the selected node settings. Stop retains completed results. Check last automatic task retrieves a job after page refresh; in-memory jobs expire after one hour or service restart. Completed local results remain in the browser.

## Verified test
URL: https://books.toscrape.com/
Fields: Title, Price, URL
Maximum list pages: 2
Next selector: li.next a
Maximum detail pages: 1
Detail selector: h3 a
Result: 3 source pages, 41 records, no warnings.

AoPS AMC 10 currently blocks server access (HTTP 403 / Cloudflare). The job reports paused, not success. Use legacy Chrome helper for this site. No challenge bypass is implemented.

## Runtime and operations
Service: cellx-collector, non-root user cellxcollector, loopback port 3002.
Code and isolated Selenium environment: /opt/cellx-collector.
Chrome sandbox enabled using a narrowly scoped AppArmor userns profile for the root-owned Chrome binary. One active job, 900 MB memory limit, 10-minute cooperative job deadline. Request/page timeouts bound individual operations. Stop waits for the current browser or extraction request. Service interruption loses in-memory job state.
Public URLs only; validated outbound proxy blocks private/reserved/multicast addresses including redirect/subresource destinations. Only standard HTTP(S) ports. New browser profile per job, downloads disabled. API requires existing workflow management credentials; internal service uses a separate key. Keys are not shipped to the browser.
LLM extraction still bills OpenAI. Selenium/Chrome run on current AWS CPU, no GPU required.

Verification: 8 backend unit tests; local browser UI test for controls, start payload, polling, output, stop and legacy mode; live public API authorization/private URL rejection/stop; live pagination/detail collection; AoPS paused state.
Deployment backup: /tmp/cellx-before-selenium-hxjg__cl
Staging and verification scripts: outputs/selenium-collector.
