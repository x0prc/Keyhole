const API_BASE = window.location.origin;
const WS_ALERTS = API_BASE.replace(/^http/, 'ws') + '/ws/alerts';
const WS_TXNS = API_BASE.replace(/^http/, 'ws') + '/ws/transactions';

let reconnectDelay = 1000;
let txnCount = 0;

const SEV_DOT = { high: 'bg-red-500', medium: 'bg-amber-500', low: 'bg-sky-500' };

function setStatus(live) {
    const el = document.getElementById('connection-status');
    if (live) {
        el.innerHTML = '<span class="w-2 h-2 rounded-full bg-emerald-500 live-dot"></span> live';
    } else {
        el.innerHTML = '<span class="w-2 h-2 rounded-full bg-red-500"></span> reconnecting';
    }
}

function verdictBadge(predicted, actual) {
    if (predicted && actual)  return '<span class="text-emerald-400">TP</span>';
    if (predicted && !actual) return '<span class="text-amber-400">FP</span>';
    if (!predicted && actual) return '<span class="text-red-400">FN</span>';
    return '<span class="text-neutral-700">·</span>';
}

function prependTxn(t) {
    const tbody = document.getElementById('txn-table');
    const tr = document.createElement('tr');
    const highlight = t.is_fraud_actual ? 'bg-red-500/5' : (t.predicted_fraud ? 'bg-amber-500/5' : '');
    tr.className = `border-b border-neutral-800/50 ${highlight}`;
    tr.innerHTML = `
        <td class="py-1.5 text-neutral-500">${new Date(t.timestamp * 1000).toLocaleTimeString()}</td>
        <td class="text-right text-neutral-200">€${t.amount.toFixed(2)}</td>
        <td class="text-center">${t.predicted_fraud ? '<span class="text-red-400">fraud</span>' : '<span class="text-neutral-700">–</span>'}</td>
        <td class="text-center">${verdictBadge(t.predicted_fraud, t.is_fraud_actual)}</td>
    `;
    tbody.prepend(tr);
    if (tbody.children.length > 200) tbody.lastChild.remove();
    txnCount++;
    document.getElementById('txn-count').textContent = txnCount.toLocaleString();
}

function prependAlert(alert) {
    const container = document.getElementById('alerts-container');
    if (container.children[0]?.textContent === 'Waiting for alerts…') container.innerHTML = '';

    const truth = alert.is_true_fraud
        ? '<span class="text-emerald-400">true fraud</span>'
        : '<span class="text-amber-400">false positive</span>';
    const amount = alert.amount !== undefined ? ` · €${alert.amount.toFixed(2)}` : '';

    const div = document.createElement('div');
    div.className = 'flex items-start gap-3 p-3 rounded-xl bg-neutral-900/60 border border-neutral-800/60';
    div.innerHTML = `
        <span class="w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${SEV_DOT[alert.severity] || 'bg-neutral-600'}"></span>
        <div class="min-w-0 flex-1">
            <div class="flex justify-between items-baseline gap-2">
                <span class="text-xs text-neutral-400 truncate font-mono">${alert.txn_ids?.[0] || ''}</span>
                <span class="text-[10px] text-neutral-600 shrink-0">${new Date(alert.timestamp * 1000).toLocaleTimeString()}</span>
            </div>
            <div class="text-xs mt-1 text-neutral-500">score ${alert.anomaly_score.toFixed(3)}${amount} · ${truth}</div>
        </div>
    `;
    container.prepend(div);
    if (container.children.length > 100) container.lastChild.remove();
}

function connectAlerts() {
    const ws = new WebSocket(WS_ALERTS);
    ws.onopen = () => { setStatus(true); reconnectDelay = 1000; };
    ws.onmessage = (e) => { prependAlert(JSON.parse(e.data)); updateMetrics(); };
    ws.onclose = () => {
        setStatus(false);
        setTimeout(connectAlerts, reconnectDelay);
        reconnectDelay = Math.min(reconnectDelay * 2, 30000);
    };
    ws.onerror = () => setStatus(false);
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
        const d = await res.json();
        document.getElementById('precision').textContent = d.precision.toFixed(3);
        document.getElementById('recall').textContent = d.recall.toFixed(3);
        document.getElementById('f1').textContent = d.f1.toFixed(3);
        document.getElementById('total-alerts').textContent = d.total_alerts;
    } catch (e) { /* keep stale values */ }
}

async function loadBackfill() {
    try {
        const [alerts, txns] = await Promise.all([
            fetch(API_BASE + '/alerts?limit=50').then(r => r.json()),
            fetch(API_BASE + '/transactions/recent?limit=100').then(r => r.json()),
        ]);
        alerts.reverse().forEach(prependAlert);
        txns.reverse().forEach(prependTxn);
    } catch (e) { /* first load before data exists is fine */ }
}

connectAlerts();
connectTxns();
updateMetrics();
loadBackfill();
setInterval(updateMetrics, 5000);
