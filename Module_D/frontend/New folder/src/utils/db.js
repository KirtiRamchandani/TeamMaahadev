const BACKEDN_HOST = 'http://localhost:3000';

async function storeLog(message) {
    const logData = {
        timestamp: new Date().toISOString(),
        message: message,
    };
    try {
        await fetch(`${BACKEDN_HOST}/store-log`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(logData),
        });
    } catch (error) {
        console.error('Error during log submission:', error);
    }
}

async function fetchLogs() {
    try {
      const response = await fetch(`${BACKEDN_HOST}/logs`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const logs = await response.json();
      console.log(logs)
      return logs;
    } catch (error) {
      console.error("Failed to fetch logs:", error);
    }
  }

module.exports = {
    storeLog,
    fetchLogs
}