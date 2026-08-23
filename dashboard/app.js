const API_BASE = window.location.origin;
const WS_ALERTS = API_BASE.replace(/^http/, 'ws') + '/ws/alerts';
const WS_TXNS = API_BASE.replace(/^http/, 'ws') + '/ws/transactions';

let reconnectDelay = 1000;
let txnCount = 0;

function setStatus(text, colorClass) {
    const el = document.getElementById('connection-status');
    el.textContent = text;
    el.className = `inline-block px-2 py-1 rounded text-xs mt-2 ${colorClass}`;
}

function badge(predicted, actual) {
    if (predicted && actual) return '<span class="text-green-400 font-bold">TP</span>';
    if (predicted && !actual) return '<span class="text-yellow-400 font-bold">FP</span>';
    if (!predicted && actual) return '<span class="text-red-400 font-bold">FN</span>';
    return '<span class="text-gray-500">TN</span>';
}

function prependTxn(t) {
    const tbody = document.getElementById('txn-table');
    const tr = document.createElement('tr');
    const rowClass = t.is_fraud_actual ? 'bg-red-900/30' : (t.predicted_fraud ? 'bg-yellow-900/20' : '');
    tr.className = `border-b border-gray-700/50 ${rowClass}`;
    tr.innerHTML = `
        <td class="py-1 text-gray-400">${new Date(t.timestamp * 1000).toLocaleTimeString()}</td>
        <td class="text-right font-mono">€${t.amount.toFixed(2)}</td>
        <td class="text-center">${t.predicted_fraud ? '🚨 fraud' : '—'}</td>
        <td class="text-center">${badge(t.predicted_fraud, t.is_fraud_actual)}</td>
    `;
    tbody.prepend(tr);
    if (tbody.children.length > 100) tbody.lastChild.remove();
    txnCount++;
    document.getElementById('txn-count').textContent = `(${txnCount})`;
}

function prependAlert(alert) {
    const container = document.getElementById('alerts-container');
    if (container.children[0]?.textContent === 'Waiting for alerts...') {
        container.innerHTML = '';
    }

    const severityColors = { high: 'bg-red-600', medium: 'bg-yellow-600', low: 'bg-blue-600' };
    const truthBadge = alert.is_true_fraud
        ? '<span class="text-green-400 text-xs">✓ true fraud</span>'
        : '<span class="text-yellow-400 text-xs">⚠ false positive</span>';
    const amount = alert.amount !== undefined ? `€${alert.amount.toFixed(2)}` : '';
    const div = document.createElement('div');
    div.className = 'p-3 rounded bg-gray-700 border-l-4 ' + (severityColors[alert.severity] || 'bg-gray-600');
    div.innerHTML = `
        <div class="flex justify-between items-start">
            <div>
                <span class="font-mono text-xs">${alert.txn_ids?.[0] || ''}</span>
                <span class="text-xs text-gray-400 ml-2">${new Date(alert.timestamp * 1000).toLocaleTimeString()}</span>
            </div>
            <span class="text-xs px-2 py-0.5 rounded ${severityColors[alert.severity] || 'bg-gray-600'}">${alert.severity.toUpperCase()}</span>
        </div>
        <div class="text-sm mt-1">Score: ${alert.anomaly_score.toFixed(3)} ${amount} ${truthBadge}</div>
    `;
    container.prepend(div);
    if (container.children.length > 50) container.lastChild.remove();
}

function connectAlerts() {
    const ws = new WebSocket(WS_ALERTS);
    ws.onopen = () => { setStatus('Live', 'bg-green-600'); reconnectDelay = 1000; };
    ws.onmessage = (e) => { prependAlert(JSON.parse(e.data)); updateMetrics(); };
    ws.onclose = () => {
        setStatus('Disconnected — reconnecting...', 'bg-red-600');
        setTimeout(connectAlerts, reconnectDelay);
        reconnectDelay = Math.min(reconnectDelay * 2, 30000);
    };
    ws.onerror = () => setStatus('Error', 'bg-red-600');
}

function connectTxns() {
    const ws = new WebSocket(WS_TXNS);
    ws.onmessage = (e) => {
        prependTxn(JSON.parse(e.data));
        if (txnCount % 50 === 0) updateMetrics();
    };
    ws.onclose = () => setTimeout(connectTxns, 3000);
}

async function updateMetrics() {
    try {
        const res = await fetch(API_BASE + '/metrics');
        const data = await res.json();
        document.getElementById('precision').textContent = data.precision.toFixed(3);
        document.getElementById('recall').textContent = data.recall.toFixed(3);
        document.getElementById('f1').textContent = data.f1.toFixed(3);
        document.getElementById('total-alerts').textContent = data.total_alerts;
    } catch (e) {
        console.error('Metrics fetch failed:', e);
    }
}

async function loadBackfill() {
    try {
        const [alerts, txns] = await Promise.all([
            fetch(API_BASE + '/alerts?limit=20').then(r => r.json()),
            fetch(API_BASE + '/transactions/recent?limit=50').then(r => r.json()),
        ]);
        alerts.reverse().forEach(prependAlert);
        txns.reverse().forEach(t => { prependTxn(t); });
    } catch (e) {
        console.error('Backfill failed:', e);
    }
}

// Init
connectAlerts();
connectTxns();
updateMetrics();
loadBackfill();
setInterval(updateMetrics, 5000);
