---
cbd:
  target: apps/api/plane/bgtasks/webhook_task.py
  kind: file
---

# Webhook delivery retries

Webhook delivery failures must not change the administrator-controlled `is_active` setting. A transient endpoint outage therefore never disables a webhook subscription.

Network failures and HTTP `408`, `425`, `429`, and `5xx` responses are retried with exponential backoff. Retries start after roughly one minute, are capped at one hour between attempts, and stop after twelve retries for an individual event. Jitter is enabled to avoid many deliveries reconnecting simultaneously.

If an individual event exhausts its retry window, that delivery is marked failed but the webhook stays active. The next matching Plane event attempts delivery normally, allowing the endpoint to recover without manual intervention.

Other `4xx` responses are treated as permanent request errors: they are recorded in webhook logs but are not retried. SSRF validation failures retain their existing behavior and are also logged without disabling the webhook.
