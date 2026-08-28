const https = require('https');

const host = 'pixel-to-path.com';
const key = '54d9a2b7f36940acb116347c87c2c1a8';
const keyLocation = `https://${host}/${key}.txt`;

const args = process.argv.slice(2);
const urls = new Set();

args.forEach(filePath => {
  if (!filePath.endsWith('.html')) return;
  if (filePath.endsWith('404.html')) return;

  const docsIndex = filePath.indexOf('docs/');
  if (docsIndex === -1) return;

  let urlPath = filePath.substring(docsIndex + 'docs/'.length);
  
  if (urlPath.endsWith('index.html')) {
    urlPath = urlPath.slice(0, -'index.html'.length);
  }

  const fullUrl = `https://${host}/${urlPath}`;
  urls.add(fullUrl);
});

const urlList = Array.from(urls);

if (urlList.length === 0) {
  console.log('Aucune URL modifiée à soumettre à IndexNow.');
  process.exit(0);
}

console.log(`Soumission de ${urlList.length} URLs modifiées à IndexNow :`);
urlList.forEach(u => console.log(' - ' + u));

const payload = JSON.stringify({
  host: host,
  key: key,
  keyLocation: keyLocation,
  urlList: urlList
});

const options = {
  hostname: 'api.indexnow.org',
  port: 443,
  path: '/indexnow',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(payload)
  }
};

const req = https.request(options, (res) => {
  let responseData = '';
  res.on('data', (chunk) => { responseData += chunk; });
  res.on('end', () => {
    if (res.statusCode === 200 || res.statusCode === 202) {
      console.log('✅ Soumission à IndexNow réussie !');
    } else {
      console.error(`❌ Échec de la soumission. Code HTTP: ${res.statusCode}`);
      if (responseData) console.error('Réponse:', responseData);
    }
  });
});

req.on('error', (e) => {
  console.error(`Erreur de requête: ${e.message}`);
});
req.write(payload);
req.end();
