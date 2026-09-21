# VINYRD SMS Production Runbook

## Current production-safe state

VINYRD uses Africa's Talking with two isolated credential paths:

- Sandbox: `PARISHCONNECT_SMS_USERNAME` + `PARISHCONNECT_SMS_API_KEY`
- Live: `PARISHCONNECT_SMS_LIVE_USERNAME` + `PARISHCONNECT_SMS_LIVE_API_KEY`

The application must remain in `PARISHCONNECT_SMS_MODE=sandbox` until the Live checklist is complete.

## Live checklist

1. Create/open the Africa's Talking Live application for VINYRD.
2. Copy the Live application username into `PARISHCONNECT_SMS_LIVE_USERNAME`.
3. Generate a Live API key and place it in `PARISHCONNECT_SMS_LIVE_API_KEY`.
4. Apply for the Tanzania Sender ID `VINYRD`.
   - Africa's Talking currently requires the Tanzania consent/request letter to be printed on official company letterhead, signed and stamped.
5. Keep `PARISHCONNECT_SMS_LIVE_SENDER_ID=VINYRD`.
6. After Africa's Talking confirms approval, set:
   `PARISHCONNECT_SMS_LIVE_SENDER_ID_APPROVED=true`
7. Configure the same VINYRD delivery-report callback URL in the Africa's Talking Live application.
8. Confirm VINYRD's Messaging production-readiness panel shows every item complete.
9. Only then switch:
   `PARISHCONNECT_SMS_MODE=live`
10. Redeploy and send a single controlled Live test before enabling church-wide broadcasts.

## Rollback

If any Live issue appears, set:

`PARISHCONNECT_SMS_MODE=sandbox`

The Sandbox credentials remain stored separately and do not need to be re-entered.

## Security

Never expose API keys in the frontend, logs, screenshots, or chat. Keep provider credentials only in Railway environment variables.
