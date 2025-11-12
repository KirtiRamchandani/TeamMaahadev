const express = require('express');
const fs = require('fs');
const app = express();
const swaggerUI = require('swagger-ui-express');
const swaggerSpec = require('../swagger');
const cors = require('cors');
const PORT = 3000;
const LOG_FILE = 'logs.txt';

app.use(express.json());
app.use(cors());

app.use('/api-docs', swaggerUI.serve, swaggerUI.setup(swaggerSpec));

/**
 * @swagger
 * /store-log:
 *   post:
 *     description: Stores a log in the server
 *     requestBody:
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             properties:
 *               message:
 *                 type: string
 *                 description: Log message
 *               timestamp:
 *                 type: string
 *                 description: Log timestamp
 *                 example: "2024-09-23T08:45:25.558Z"
 *     responses:
 *       201:
 *         description: Log saved successfully
 */
app.post('/store-log', (req, res) => {
    const logData = req.body;
    if (!logData || typeof logData !== 'string' || !logData.trim()) {
        return res.status(400).json({ error: 'Invalid log data' });
    }
    try {
        fs.appendFileSync(LOG_FILE, `${logData.trim()}\n`);
        res.status(201).json({ message: 'Log saved successfully' });
    } catch (err) {
        console.error('Error writing log:', err);
        res.status(500).json({ error: 'Failed to write log' });
    }
});

/**
 * @swagger
 * /logs:
 *   get:
 *     description: Returns a list of logs
 *     responses:
 *       200:
 *         description: A list of logs
 *         content:
 *           application/json:
 *             schema:
 *               type: array
 */
app.get('/logs', (req, res) => {
    if (fs.existsSync(LOG_FILE)) {
        try {
            const data = fs.readFileSync(LOG_FILE, 'utf-8');
            // Split by newline, remove empty lines, and return as array
            const logs = data
                .split(/\r?\n/)
                .map(line => line.trim())
                .filter(line => line.length > 0);
            
            res.json(logs);
        } catch (err) {
            console.error('Error reading log file:', err);
            res.status(500).json({ error: 'Error reading log file' });
        }
    } else {
        res.json([]);
    }
});

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});