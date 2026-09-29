export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname !== "/approve") {
      return new Response("Not found", { status: 404 });
    }

    const params = url.searchParams;
    const required = [
      "symbol",
      "strategy",
      "direction",
      "entry",
      "stop",
      "target",
      "risk_dollars",
      "submit_paper",
    ];
    for (const key of required) {
      if (!params.get(key)) {
        return new Response(`Missing ${key}`, { status: 400 });
      }
    }

    const body = {
      ref: "main",
      inputs: {
        symbol: params.get("symbol"),
        strategy: params.get("strategy"),
        direction: params.get("direction"),
        entry: params.get("entry"),
        stop: params.get("stop"),
        target: params.get("target"),
        risk_dollars: params.get("risk_dollars"),
        target_r: "2.0",
        submit_paper: params.get("submit_paper") === "true" ? "true" : "false",
      },
    };

    const response = await fetch(
      `https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/approved-paper-trade.yml/dispatches`,
      {
        method: "POST",
        headers: {
          "Accept": "application/vnd.github+json",
          "Authorization": `Bearer ${env.GITHUB_TOKEN}`,
          "Content-Type": "application/json",
          "User-Agent": "trading-bot-approval-worker",
          "X-GitHub-Api-Version": "2022-11-28",
        },
        body: JSON.stringify(body),
      },
    );

    if (response.status !== 204) {
      const text = await response.text();
      return new Response(`GitHub dispatch failed: ${response.status}\n${text}`, {
        status: 502,
      });
    }

    const mode = body.inputs.submit_paper === "true" ? "paper submit" : "dry-run";
    return new Response(
      `Approved ${mode} workflow for ${body.inputs.symbol}. You can close this page.`,
      { status: 200 },
    );
  },
};
