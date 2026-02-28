/**
 * Minimal HTTP server for testing the extension.
 * Accepts POST /v1/safety/report and prints the JSON body.
 * Run: node test-server.js   (listens on http://localhost:8000)
 */
const http = require('http');

const PORT = 8000;

const server = http.createServer((req, res) => {
  if (req.method === 'POST' && req.url === '/v1/safety/report') {
    let body = '';
    req.on('data', (chunk) => { body += chunk; });
    req.on('end', () => {
      try {
        const data = JSON.parse(body);
        console.log('\n--- Report received ---');
        console.log(JSON.stringify(data, null, 2));
        console.log('------------------------\n');
      } catch (e) {
        console.error('Parse error:', e.message);
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ ok: true }));
    });
    return;
  }
  res.writeHead(404);
  res.end('Not found');
});

server.listen(PORT, () => {
  console.log(`Test server: http://localhost:${PORT}`);
  console.log('POST /v1/safety/report will log extension reports here.');
  console.log('Load the extension, browse to a page, wait ~2s – then check this terminal.\n');
});
