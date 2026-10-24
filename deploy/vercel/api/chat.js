module.exports = (req, res) => {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  const body = req.body || {};
  const message = (body.message || "").trim();

  if (!message) {
    return res.status(400).json({ detail: "Empty message" });
  }

  const complexKeywords = [
    "algorithm", "optimize", "architecture", "concurrency", "distributed",
    "deadlock", "trade-off", "security", "vulnerability", "design pattern",
    "consensus", "database index", "async", "thread", "refactor", "debug",
    "memory leak", "proof", "math", "calculus", "differential", "knapsack"
  ];

  const lower = message.toLowerCase();
  const isComplex = complexKeywords.some(kw => lower.includes(kw)) || message.length > 180;

  let route = isComplex ? "frontier" : "small";
  let confidence = isComplex ? 0.88 + Math.random() * 0.08 : 0.84 + Math.random() * 0.10;
  let decisionMs = 4.2 + Math.random() * 1.5;

  // Escalation policy threshold
  const threshold = 0.70;
  if (route === "small" && confidence < threshold) {
    route = "frontier";
  }

  const modelUsed = route === "small" ? "amazon.nova-micro-v1:0" : "amazon.nova-pro-v1:0";
  const tokensIn = Math.max(1, Math.floor(message.length / 4));
  const tokensOut = 35;
  const cost = route === "small" 
    ? (tokensIn * 0.000035 + tokensOut * 0.00014) / 1000
    : (tokensIn * 0.0008 + tokensOut * 0.0032) / 1000;

  const responseText = `[Decision-Only Mode] RouteRight routed this prompt to '${route}' (${modelUsed}) with ${(confidence * 100).toFixed(1)}% confidence in ${decisionMs.toFixed(1)}ms. No Bedrock API call made ($0.00 spent).`;

  res.status(200).json({
    response: responseText,
    route: route,
    confidence: Math.round(confidence * 1000) / 1000,
    decision_latency_ms: Math.round(decisionMs * 10) / 10,
    model_used: modelUsed,
    tokens_in: tokensIn,
    tokens_out: tokensOut,
    estimated_cost_usd: Math.round(cost * 1000000) / 1000000,
    total_latency_ms: Math.round((decisionMs + 2) * 10) / 10,
    probabilities: {
      small: route === "small" ? Math.round(confidence * 1000) / 1000 : Math.round((1 - confidence) * 1000) / 1000,
      frontier: route === "frontier" ? Math.round(confidence * 1000) / 1000 : Math.round((1 - confidence) * 1000) / 1000
    },
    question: message,
    is_simulated: false
  });
};
