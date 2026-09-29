# Approval Worker

This optional Cloudflare Worker powers Discord approval link buttons.

It receives an approval link from Discord and triggers the GitHub
`Approved Paper Trade` workflow.

Required Worker secrets:

```text
GITHUB_TOKEN
GITHUB_REPO=bilalhadii/trading-bot
```

After deployment, add this GitHub Actions repository secret:

```text
APPROVAL_BASE_URL=https://your-worker.your-subdomain.workers.dev
```

The alert workflow will then include:

```text
Dry-run $100
Approve Paper $100
```

Keep the workflow dry-run first. Use `Approve Paper $100` only after
you are comfortable with the alert and risk sizing.
