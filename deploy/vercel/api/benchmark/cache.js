const fs = require('fs');
const path = require('path');

module.exports = (req, res) => {
  res.setHeader('Content-Type', 'application/json');
  res.setHeader('Access-Control-Allow-Origin', '*');
  try {
    const filePath = path.join(process.cwd(), 'public', 'results.json');
    if (fs.existsSync(filePath)) {
      const data = fs.readFileSync(filePath, 'utf8');
      return res.status(200).send(data);
    }
  } catch (err) {
    // fallback
  }
  res.status(200).json({ status: "ok" });
};
