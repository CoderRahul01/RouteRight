module.exports = (req, res) => {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.status(200).json({
    total_decisions: 50,
    routed_to_small: 20,
    routed_to_frontier: 30,
    escalated_due_to_confidence: 5,
    actual_cost_usd: 0.137797,
    always_frontier_cost_usd: 0.218481,
    always_small_cost_usd: 0.003593,
    saved_usd: 0.080684,
    percent_saved: 36.9,
    average_decision_latency_ms: 4.74,
    percent_small: 40.0
  });
};
