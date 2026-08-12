const { diagnose } = require('../t02_core');

module.exports = (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ error: 'method_not_allowed' });
  try {
    return res.status(200).json(diagnose((req.body || {}).features || {}));
  } catch (error) {
    return res.status(500).json({
      diagnostic: 'unknown',
      abstained: true,
      automatic_control_allowed: false,
      error: 't02_runtime_error'
    });
  }
};
