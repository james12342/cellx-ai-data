# Cell AI Data Marketplace Real Trading Setup

This marketplace implementation has four production-facing parts:

- Marketplace user registration/login with server-issued session tokens.
- Template submission with `pending_review` status.
- Admin review with `MARKETPLACE_ADMIN_TOKEN`.
- Stripe Checkout and Stripe Connect payouts when Stripe secrets are configured.

## Backend Environment

Set these environment variables on the AWS `cellx-extension-api` service:

```bash
STRIPE_SECRET_KEY=sk_live_or_test_key
MARKETPLACE_ADMIN_TOKEN=long-random-review-token
PLATFORM_COMMISSION_RATE=0.25
STRIPE_SUCCESS_URL=https://app.cellaidata.com/workflow/?checkout=success&session_id={CHECKOUT_SESSION_ID}
STRIPE_CANCEL_URL=https://app.cellaidata.com/workflow/?checkout=cancel
STRIPE_CONNECT_RETURN_URL=https://app.cellaidata.com/workflow/?connect=return
STRIPE_CONNECT_REFRESH_URL=https://app.cellaidata.com/workflow/?connect=refresh
```

Without `STRIPE_SECRET_KEY`, Checkout and Connect return a setup-required message instead of creating real Stripe objects.

Without `MARKETPLACE_ADMIN_TOKEN`, templates can be submitted but cannot be approved from the UI.

## Workflow

1. Developer registers or logs in from the marketplace panel.
2. Developer clicks `Connect Stripe Payout`.
3. Developer submits a workflow template.
4. Admin reviews the template and enters the admin review token to list it.
5. Buyer clicks `Checkout`; if Stripe is configured, the backend creates a Checkout Session and opens Stripe's hosted payment page.
6. The backend records purchase and payout intent metadata. A production webhook should be added before relying on paid status.

## Production Hardening Still Needed

- Move marketplace users from the JSON store into the real CellX user table.
- Add cookie or JWT sessions instead of localStorage tokens.
- Add Stripe webhooks to mark purchases paid only after payment confirmation.
- Add a true admin UI for review instead of a prompt-based token.
- Add developer payout reporting and refund/dispute handling.
