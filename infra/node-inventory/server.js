/**
 * faskins-inventory — Steam inventory microservice
 * Port: 8081 (localhost only)
 *
 * Uses steam-inventory-api-ng to fetch CS2 inventories with retry support.
 * Proxies can be added via INVENTORY_PROXIES env var (newline or comma separated).
 *
 * GET /inventory?steamid=76561198...
 * GET /health
 */

'use strict';

const http = require('http');
const { URL } = require('url');
const InventoryAPI = require('steam-inventory-api-ng');

const PORT = parseInt(process.env.INVENTORY_PORT || '8081', 10);
const HOST = process.env.INVENTORY_HOST || '127.0.0.1';

// Parse proxies from env: "socks5://..." or "http://..." — comma or newline separated
function parseProxies() {
    const raw = process.env.INVENTORY_PROXIES || '';
    if (!raw.trim()) return undefined;
    return raw.split(/[\n,]+/).map(p => p.trim()).filter(Boolean);
}

const proxies = parseProxies();

const apiOptions = {
    requestOptions: {
        timeout: 15000,
    },
    retryDelay: 3000,
};

if (proxies && proxies.length > 0) {
    apiOptions.proxies = proxies;
    console.log(`[inventory] Loaded ${proxies.length} proxy(ies)`);
}

const inventoryApi = new InventoryAPI(apiOptions);

inventoryApi.on('log', (type, message, steamid) => {
    if (type === 'debug') return; // suppress debug noise
    console.log(`[${new Date().toISOString()}] [${type}] ${steamid || ''} ${message}`);
});

/**
 * Convert CEconItem array into {assets, descriptions} format
 * compatible with the Python inventory endpoint.
 */
function toAssetsDescriptions(items) {
    const assets = [];
    const descMap = {};

    for (const item of items) {
        assets.push({
            assetid: item.assetid,
            classid: item.classid,
            instanceid: item.instanceid,
            appid: item.appid,
            contextid: String(item.contextid),
            amount: '1',
        });

        const key = `${item.classid}_${item.instanceid}`;
        if (!descMap[key]) {
            descMap[key] = {
                classid: item.classid,
                instanceid: item.instanceid,
                name: item.name || '',
                market_hash_name: item.market_hash_name || item.name || '',
                icon_url: item.icon_url || '',
                tradable: item.tradable ? 1 : 0,
                marketable: item.marketable ? 1 : 0,
                type: item.type || '',
                tags: item.tags || [],
            };
        }
    }

    return {
        assets,
        descriptions: Object.values(descMap),
    };
}

function sendJson(res, statusCode, data) {
    const body = JSON.stringify(data);
    res.writeHead(statusCode, {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body),
    });
    res.end(body);
}

async function handleInventory(req, res, steamid) {
    if (!steamid) {
        return sendJson(res, 400, { error: 'Missing steamid parameter' });
    }

    try {
        const result = await inventoryApi.get(steamid, 730, 2, false, 2, 'english');
        const { assets, descriptions } = toAssetsDescriptions(result.inventory);

        sendJson(res, 200, {
            success: 1,
            assets,
            descriptions,
            total_inventory_count: result.total_inventory_count,
        });
    } catch (err) {
        const msg = err.message || String(err);
        console.error(`[inventory] Error for ${steamid}: ${msg}`);

        if (msg.toLowerCase().includes('private') || msg.includes('403')) {
            return sendJson(res, 403, { error: 'Steam inventory is private' });
        }
        if (msg.toLowerCase().includes('not found') || msg.includes('404')) {
            return sendJson(res, 404, { error: 'Steam profile not found' });
        }

        sendJson(res, 502, { error: `Steam API error: ${msg}` });
    }
}

const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, `http://${HOST}:${PORT}`);

    if (req.method === 'GET' && url.pathname === '/health') {
        return sendJson(res, 200, { status: 'ok' });
    }

    if (req.method === 'GET' && url.pathname === '/inventory') {
        const steamid = url.searchParams.get('steamid');
        return handleInventory(req, res, steamid);
    }

    sendJson(res, 404, { error: 'Not found' });
});

server.listen(PORT, HOST, () => {
    console.log(`[inventory] Listening on ${HOST}:${PORT}`);
    if (proxies) {
        console.log(`[inventory] Proxies: ${proxies.length} configured`);
    }
});

server.on('error', (err) => {
    console.error('[inventory] Server error:', err);
    process.exit(1);
});
