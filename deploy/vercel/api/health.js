const { health } = require('../t02_core');
module.exports = (req, res) => res.status(200).json(health());
