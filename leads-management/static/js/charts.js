// Training Center CRM — Dynamic Charts (all data fetched from live API)
'use strict';

const _PALETTE = ['#2563eb','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#ec4899','#84cc16'];
const _fmt = v => 'AED ' + Number(v).toLocaleString('en-AE', {minimumFractionDigits:0, maximumFractionDigits:0});

let pipelineChart, revenueChart, conversionChart;

// ── Shared chart defaults ────────────────────────────────────────
function _baseOptions(title) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            title: title ? { display: true, text: title, font: { size: 14, weight: '600' }, color: '#1e293b', padding: { bottom: 16 } } : { display: false }
        }
    };
}

// ── Pipeline Funnel (bar) ────────────────────────────────────────
function initializePipelineChart() {
    const ctx = document.getElementById('pipelineChart');
    if (!ctx) return;

    fetch('/api/pipeline/data')
        .then(r => r.json())
        .then(data => {
            const statuses = ['New', 'Contacted', 'Interested', 'Quoted', 'Converted'];
            const colors   = ['#3b82f6','#f59e0b','#f97316','#8b5cf6','#10b981'];
            const counts   = statuses.map(s => data[s]?.count || 0);
            const values   = statuses.map(s => data[s]?.total_value || 0);

            if (pipelineChart) { pipelineChart.destroy(); }
            pipelineChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: statuses,
                    datasets: [{
                        label: 'Leads',
                        data: counts,
                        backgroundColor: colors,
                        borderWidth: 0,
                        borderRadius: 8,
                        borderSkipped: false
                    }]
                },
                options: {
                    ..._baseOptions('Pipeline Overview'),
                    plugins: {
                        ..._baseOptions('Pipeline Overview').plugins,
                        legend: { display: false },
                        tooltip: {
                            callbacks: {
                                label: ctx2 => ` ${ctx2.parsed.y} leads`,
                                afterLabel: ctx2 => values[ctx2.dataIndex] > 0 ? ` Value: ${_fmt(values[ctx2.dataIndex])}` : ''
                            }
                        }
                    },
                    scales: {
                        y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,.06)' }, ticks: { stepSize: 1, color: '#64748b', font: { size: 11 } } },
                        x: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 12 } } }
                    },
                    animation: { duration: 900, easing: 'easeInOutQuart' }
                }
            });
        })
        .catch(e => console.warn('Pipeline chart:', e));
}

// ── Monthly Revenue (line) ───────────────────────────────────────
function initializeRevenueChart() {
    const ctx = document.getElementById('revenueChart');
    if (!ctx) return;

    fetch('/api/charts/revenue')
        .then(r => r.json())
        .then(data => {
            const labels  = data.map(d => d.month);
            const values  = data.map(d => d.revenue);
            const hasData = values.some(v => v > 0);

            if (revenueChart) { revenueChart.destroy(); }
            revenueChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels,
                    datasets: [{
                        label: 'Revenue (AED)',
                        data: values,
                        borderColor: '#2563eb',
                        backgroundColor: 'rgba(37,99,235,.08)',
                        borderWidth: 2.5,
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#2563eb',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        pointRadius: 5
                    }]
                },
                options: {
                    ..._baseOptions('Revenue Trend (Last 6 Months)'),
                    plugins: {
                        ..._baseOptions('Revenue Trend (Last 6 Months)').plugins,
                        legend: { display: false },
                        tooltip: {
                            callbacks: { label: ctx2 => ' ' + _fmt(ctx2.parsed.y) }
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(0,0,0,.06)' },
                            ticks: { callback: v => _fmt(v), color: '#64748b', font: { size: 11 }, maxTicksLimit: 5 }
                        },
                        x: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 11 } } }
                    },
                    animation: { duration: 1200, easing: 'easeInOutQuart' }
                }
            });

            if (!hasData) {
                const wrapper = ctx.closest('.chart-container') || ctx.parentElement;
                if (wrapper && !wrapper.querySelector('.no-data-msg')) {
                    const msg = document.createElement('div');
                    msg.className = 'no-data-msg';
                    msg.style.cssText = 'position:absolute;inset:0;display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:13px;pointer-events:none;';
                    msg.textContent = 'No invoice data yet';
                    wrapper.style.position = 'relative';
                    wrapper.appendChild(msg);
                }
            }
        })
        .catch(e => console.warn('Revenue chart:', e));
}

// ── Conversion by Source (doughnut) ─────────────────────────────
function initializeConversionChart() {
    const ctx = document.getElementById('conversionChart');
    if (!ctx) return;

    fetch('/api/charts/conversion')
        .then(r => r.json())
        .then(data => {
            if (!data.length) { data = [{ source: 'No Data', rate: 100, total: 0, converted: 0 }]; }
            const labels = data.map(d => d.source);
            const rates  = data.map(d => d.rate);

            if (conversionChart) { conversionChart.destroy(); }
            conversionChart = new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels,
                    datasets: [{
                        data: rates,
                        backgroundColor: _PALETTE.slice(0, labels.length),
                        borderWidth: 0,
                        hoverOffset: 8
                    }]
                },
                options: {
                    ..._baseOptions('Conversion Rate by Source'),
                    cutout: '65%',
                    plugins: {
                        ..._baseOptions('Conversion Rate by Source').plugins,
                        legend: { display: true, position: 'bottom', labels: { padding: 16, usePointStyle: true, font: { size: 11 } } },
                        tooltip: {
                            callbacks: {
                                label: ctx2 => {
                                    const d = data[ctx2.dataIndex];
                                    return ` ${d.source}: ${d.rate}% (${d.converted}/${d.total})`;
                                }
                            }
                        }
                    },
                    animation: { duration: 1000, easing: 'easeInOutQuart' }
                }
            });
        })
        .catch(e => console.warn('Conversion chart:', e));
}

// ── Monthly Leads Trend (bar+line) ──────────────────────────────
function initializeLeadsTrendChart() {
    const ctx = document.getElementById('leadsTrendChart');
    if (!ctx) return;

    fetch('/api/charts/leads-trend')
        .then(r => r.json())
        .then(data => {
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.map(d => d.month),
                    datasets: [
                        {
                            label: 'Total Leads',
                            data: data.map(d => d.leads),
                            backgroundColor: 'rgba(37,99,235,.7)',
                            borderRadius: 6,
                            borderSkipped: false
                        },
                        {
                            label: 'Converted',
                            data: data.map(d => d.converted),
                            backgroundColor: 'rgba(16,185,129,.75)',
                            borderRadius: 6,
                            borderSkipped: false
                        }
                    ]
                },
                options: {
                    ..._baseOptions('Monthly Lead Generation & Conversion'),
                    plugins: {
                        ..._baseOptions('Monthly Lead Generation & Conversion').plugins,
                        legend: { display: true, position: 'top', labels: { usePointStyle: true, font: { size: 11 } } }
                    },
                    scales: {
                        y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,.06)' }, ticks: { stepSize: 1, color: '#64748b', font: { size: 11 } } },
                        x: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 11 } } }
                    },
                    animation: { duration: 1000 }
                }
            });
        })
        .catch(e => console.warn('Leads trend chart:', e));
}

// ── Reports page charts ─────────────────────────────────────────
function initializeReportsCharts() {
    initializeLeadsTrendChart();

    // Source performance (radar) — uses live conversion data
    const srcCtx = document.getElementById('sourcePerformanceChart');
    if (srcCtx) {
        fetch('/api/charts/conversion')
            .then(r => r.json())
            .then(data => {
                if (!data.length) return;
                new Chart(srcCtx, {
                    type: 'radar',
                    data: {
                        labels: data.map(d => d.source),
                        datasets: [{
                            label: 'Conversion Rate (%)',
                            data: data.map(d => d.rate),
                            borderColor: '#2563eb',
                            backgroundColor: 'rgba(37,99,235,.15)',
                            borderWidth: 2,
                            pointBackgroundColor: '#2563eb',
                            pointRadius: 4
                        }]
                    },
                    options: {
                        ..._baseOptions('Lead Source Conversion Rate'),
                        plugins: { ..._baseOptions('Lead Source Conversion Rate').plugins, legend: { display: false } },
                        scales: { r: { beginAtZero: true, grid: { color: 'rgba(0,0,0,.08)' }, ticks: { font: { size: 10 } } } }
                    }
                });
            });
    }

    // Revenue breakdown (pie) — uses live revenue data
    const revCtx = document.getElementById('revenueBreakdownChart');
    if (revCtx) {
        fetch('/api/charts/revenue')
            .then(r => r.json())
            .then(data => {
                new Chart(revCtx, {
                    type: 'pie',
                    data: {
                        labels: data.map(d => d.month),
                        datasets: [{
                            data: data.map(d => d.revenue),
                            backgroundColor: _PALETTE,
                            borderWidth: 0,
                            hoverOffset: 12
                        }]
                    },
                    options: {
                        ..._baseOptions('Revenue by Month'),
                        plugins: {
                            ..._baseOptions('Revenue by Month').plugins,
                            legend: { display: true, position: 'bottom', labels: { usePointStyle: true, font: { size: 11 } } },
                            tooltip: { callbacks: { label: ctx2 => ' ' + _fmt(ctx2.parsed) } }
                        }
                    }
                });
            });
    }

    const monthCtx = document.getElementById('monthlyLeadsChart');
    if (monthCtx) { initializeLeadsTrendChart(); }
}

// ── Live pipeline refresh (30s) ──────────────────────────────────
function updateCharts() {
    if (pipelineChart) {
        fetch('/api/pipeline/data')
            .then(r => r.json())
            .then(data => {
                const statuses = ['New', 'Contacted', 'Interested', 'Quoted', 'Converted'];
                pipelineChart.data.datasets[0].data = statuses.map(s => data[s]?.count || 0);
                pipelineChart.update('none');
            });
    }
    if (revenueChart) {
        fetch('/api/charts/revenue')
            .then(r => r.json())
            .then(data => {
                revenueChart.data.labels = data.map(d => d.month);
                revenueChart.data.datasets[0].data = data.map(d => d.revenue);
                revenueChart.update('none');
            });
    }
}

// ── Dashboard init ───────────────────────────────────────────────
function initializeDashboardCharts() {
    initializePipelineChart();
    initializeRevenueChart();
    initializeConversionChart();
}

setInterval(updateCharts, 60000); // refresh every 60s

document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
        if (typeof Chart === 'undefined') return;
        initializeDashboardCharts();
        if (window.location.pathname.includes('/reports')) {
            initializeReportsCharts();
        }
    }, 300);
});
