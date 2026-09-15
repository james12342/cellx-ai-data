#!/usr/bin/env bash
set -euo pipefail

ENV_LINE="$(systemctl show cellx-extension-api --property=Environment --value || true)"
for pair in ${ENV_LINE}; do
  export "${pair}"
done

exec /usr/bin/python3 /opt/cellx-extension-api/customer-scripts/orderdesk_daily_sync.py \
  --max-records "${ORDERDESK_SYNC_MAX_RECORDS:-5000}" \
  --page-size "${ORDERDESK_SYNC_PAGE_SIZE:-500}" \
  --order-by "${ORDERDESK_SYNC_ORDER_BY:-date_added}" \
  --order "${ORDERDESK_SYNC_ORDER:-desc}"
