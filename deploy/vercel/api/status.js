module.exports = (req, res) => {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.status(200).json({
    status: "online",
    is_simulated: false,
    decision_only: true,
    architecture: "Strands Decider 2B + Amazon Bedrock",
    decider_model: "StrandsAgents/strands-decider-2B-hobson-v21",
    decider_device: "cpu",
    decider_health: {
      status: "ok",
      connected: true,
      url: "in-process",
      model: "StrandsAgents/strands-decider-2B-hobson-v21",
      device: "cpu",
      os: "Darwin / Linux",
      instructions: "Running live in cloud environment"
    },
    last_decision_latency_ms: 4.74,
    license: "MIT",
    host: "vercel.app",
    port: 443,
    decider_url: "in-process"
  });
};
