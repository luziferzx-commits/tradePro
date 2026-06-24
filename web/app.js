const API_BASE = "http://localhost:8000/api";

// Chart Instances
let chartMlDist, chartSessions, chartRejectStages;

async function fetchAPI(endpoint) {
    try {
        const res = await fetch(`${API_BASE}${endpoint}`);
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        return await res.json();
    } catch (e) {
        console.error(`Fetch failed for ${endpoint}:`, e);
        return null;
    }
}

function initCharts() {
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.borderColor = 'rgba(255,255,255,0.05)';
    Chart.defaults.font.family = 'Inter';

    const ctxMl = document.getElementById('chartMlDist').getContext('2d');
    chartMlDist = new Chart(ctxMl, {
        type: 'bar',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                x: { grid: { display: false } }
            }
        }
    });

    const ctxSessions = document.getElementById('chartSessions').getContext('2d');
    chartSessions = new Chart(ctxSessions, {
        type: 'doughnut',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
            cutout: '70%',
            borderWidth: 0
        }
    });

    const ctxRejects = document.getElementById('chartRejectStages').getContext('2d');
    chartRejectStages = new Chart(ctxRejects, {
        type: 'doughnut',
        data: { labels: [], datasets: [] },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
            cutout: '70%',
            borderWidth: 0
        }
    });
}

async function updateDashboard() {
    // 1. Summary
    const summary = await fetchAPI('/summary');
    if (summary) {
        document.getElementById('valCoverage').innerText = `${summary.coverage_pct}%`;
        document.getElementById('valAcceptance').innerText = `${summary.acceptance_pct}%`;
        document.getElementById('valTotalSignals').innerText = `Total Scans: ${summary.total_signals}`;
    }

    // 2. Health
    const health = await fetchAPI('/health');
    if (health) {
        document.getElementById('valDaysChange').innerText = health.days_since_change;
        const badge = document.getElementById('healthBadge');
        const text = document.getElementById('healthText');
        text.innerText = `${health.state} (Dynamic: ${health.dynamic})`;
        
        if (health.state === "HEALTHY") {
            badge.style.borderColor = "rgba(16, 185, 129, 0.5)";
            badge.querySelector('.pulse').style.background = "var(--success)";
        } else if (health.state === "DISABLED") {
            badge.style.borderColor = "rgba(239, 68, 68, 0.5)";
            badge.querySelector('.pulse').style.background = "var(--danger)";
        } else {
            badge.style.borderColor = "rgba(245, 158, 11, 0.5)";
            badge.querySelector('.pulse').style.background = "var(--warning)";
        }
    }

    // 3. Gap Stats
    const gap = await fetchAPI('/probability-gap');
    if (gap) {
        document.getElementById('valGapAbs').innerText = gap.avg_abs_gap !== null ? gap.avg_abs_gap.toFixed(4) : "0.000";
        document.getElementById('valGapSigned').innerText = gap.avg_signed_gap !== null ? gap.avg_signed_gap.toFixed(4) : "0.000";
        document.getElementById('valGapMin').innerText = gap.min_signed_gap !== null ? gap.min_signed_gap.toFixed(4) : "0.000";
        document.getElementById('valGapMax').innerText = gap.max_signed_gap !== null ? gap.max_signed_gap.toFixed(4) : "0.000";
        
        const signedGap = document.getElementById('valGapSigned');
        if (gap.avg_signed_gap > 0) signedGap.style.color = 'var(--success)';
        else if (gap.avg_signed_gap < 0) signedGap.style.color = 'var(--danger)';
    }

    // 4. ML Distribution
    const mlDist = await fetchAPI('/ml-distribution');
    if (mlDist) {
        chartMlDist.data = {
            labels: mlDist.map(d => d.prob_bucket),
            datasets: [{
                label: 'Signals',
                data: mlDist.map(d => d.count),
                backgroundColor: 'rgba(59, 130, 246, 0.8)',
                borderRadius: 4
            }]
        };
        chartMlDist.update();
    }

    // 5. Sessions
    const sessions = await fetchAPI('/sessions');
    if (sessions) {
        chartSessions.data = {
            labels: sessions.map(d => d.session),
            datasets: [{
                data: sessions.map(d => d.count),
                backgroundColor: ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6'],
                borderWidth: 0
            }]
        };
        chartSessions.update();
    }

    // 6. Rejects
    const rejects = await fetchAPI('/rejects');
    if (rejects) {
        chartRejectStages.data = {
            labels: rejects.stages.map(d => d.stage),
            datasets: [{
                data: rejects.stages.map(d => d.count),
                backgroundColor: ['#ef4444', '#f59e0b', '#3b82f6', '#8b5cf6', '#64748b'],
                borderWidth: 0
            }]
        };
        chartRejectStages.update();

        const list = document.getElementById('listRejectReasons');
        list.innerHTML = '';
        rejects.reasons.forEach(r => {
            let reasonText = "N/A";
            try {
                const parsed = JSON.parse(r.reason);
                reasonText = Array.isArray(parsed) ? parsed[0] : parsed;
            } catch(e) {
                reasonText = r.reason;
            }
            
            const li = document.createElement('li');
            li.innerHTML = `<span>${reasonText}</span> <span class="reason-count">${r.count}</span>`;
            list.appendChild(li);
        });
    }

    // 7. Latest Signals
    const latest = await fetchAPI('/latest-signals');
    if (latest) {
        const tbody = document.querySelector('#tableSignals tbody');
        tbody.innerHTML = '';
        latest.forEach(sig => {
            const isAccept = sig.decision === 'ACCEPT';
            const badgeClass = isAccept ? 'badge-accept' : 'badge-reject';
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${sig.timestamp}</td>
                <td><strong>${sig.symbol}</strong></td>
                <td>${sig.session}</td>
                <td>${sig.regime}</td>
                <td>${sig.ml_probability.toFixed(3)}</td>
                <td>${sig.decision_stage}</td>
                <td><span class="badge ${badgeClass}">${sig.decision}</span></td>
            `;
            tbody.appendChild(tr);
        });
    }
    // 8. Market Memory
    const memory = await fetchAPI('/latest-memory');
    if (memory) {
        document.getElementById('memContext').innerText = `${memory.session} + ${memory.regime}`;
        document.getElementById('memMatches').innerText = memory.memory_matches;
        document.getElementById('memPf').innerText = memory.memory_pf.toFixed(2);
        
        const confBadge = document.getElementById('memConf');
        confBadge.innerText = memory.memory_confidence;
        
        if (memory.memory_confidence === 'HIGH') {
            confBadge.className = "value badge badge-accept";
        } else if (memory.memory_confidence === 'MEDIUM') {
            confBadge.className = "value badge";
            confBadge.style.background = "rgba(245, 158, 11, 0.1)";
            confBadge.style.color = "var(--warning)";
            confBadge.style.border = "1px solid rgba(245, 158, 11, 0.2)";
        } else if (memory.memory_confidence === 'LOW') {
            confBadge.className = "value badge badge-reject";
        } else {
            confBadge.className = "value badge";
            confBadge.style.background = "rgba(100, 116, 139, 0.1)";
            confBadge.style.color = "var(--text-muted)";
            confBadge.style.border = "1px solid rgba(100, 116, 139, 0.2)";
        }
    }
}

// Init
initCharts();
updateDashboard();

// Auto refresh every 5 seconds
setInterval(updateDashboard, 5000);
