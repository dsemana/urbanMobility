const API   = '/api';                                         
const money = n => '$' + Number(n || 0).toFixed(2);
const num   = n => Number(n || 0).toLocaleString();

async function get(path) {
    const r = await fetch(API + path);
    if (!r.ok) throw new Error(`${r.status} ${r.statusText} — ${API + path}`);
    return r.json();
}

function makeChart(id, type, labels, data, label, color) {
    const ctx = document.getElementById(id);
    if (!ctx) return;
    // Destroy old instance if re-rendering
    const existing = Chart.getChart(ctx);
    if (existing) existing.destroy();

    const isBar  = type === 'bar';
    const isPie  = type === 'pie' || type === 'doughnut';
    const colors = isPie
        ? ['#f7c948','#e8a020','#4a90c4','#e05a2b','#3da86e','#7c5cbf','#8a8880']
        : (color || '#f7c948');

    new Chart(ctx, {
        type,
        data: {
            labels,
            datasets: [{
                label,
                data,
                backgroundColor: colors,
                borderColor:     isPie ? '#fff' : (color || '#e8a020'),
                borderWidth:     isPie ? 2 : 0,
                borderRadius:    isBar ? 4 : 0,
                tension:         0.4,
                fill:            type === 'line',
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: isPie, position: 'right',
                          labels: { font: { size: 11 }, padding: 10, boxWidth: 12 } },
                tooltip: {
                    backgroundColor: '#111827',
                    titleColor: '#fff',
                    bodyColor: 'rgba(255,255,255,0.8)',
                    padding: 10,
                    cornerRadius: 6,
                }
            },
            scales: isPie ? {} : {
                x: { grid: { color: 'rgba(0,0,0,0.04)' }, ticks: { font: { size: 11 } } },
                y: { grid: { color: 'rgba(0,0,0,0.04)' }, ticks: { font: { size: 11 } } }
            }
        }
    });
}

let currentPage  = 1;
let totalTrips   = 0;

async function load() {
    try {
        const [summary, hourly, boroughs, zones, routes, daily, congestion] =
            await Promise.all([
                get('/summary'),
                get('/hourly'),
                get('/boroughs'),
                get('/top-zones?limit=10'),
                get('/ranked-routes?limit=10'),
                get('/daily'),
                get('/congestion'),
            ]);

        renderCards(summary);
        populateBoroughFilter(boroughs);
        renderHourlyChart(hourly);
        renderBoroughChart(boroughs);
        renderSpeedChart(congestion);
        renderDailyChart(daily);
        renderZones(zones);
        renderRoutes(routes);
        await loadTrips(1);

    } catch (err) {
        document.getElementById('cards').innerHTML =
            `<div class="card" style="grid-column:1/-1;border-top-color:#e05a2b">
               <div class="label">Error</div>
               <strong style="font-size:1rem;color:#e05a2b">Could not reach API</strong>
               <p style="margin-top:4px;font-size:0.8rem;color:#6b7280">${err.message}</p>
             </div>`;
    }
}

function renderCards(s) {
    document.getElementById('cards').innerHTML = `
      <div class="card">
        <div class="label">Total trips</div>
        <strong>${num(s.trips)}</strong>
      </div>
      <div class="card accent">
        <div class="label">Total revenue</div>
        <strong>${money(s.revenue)}</strong>
      </div>
      <div class="card">
        <div class="label">Avg fare</div>
        <strong>${money(s.avg_fare)}</strong>
      </div>
      <div class="card sky">
        <div class="label">Avg distance</div>
        <strong>${s.avg_distance} mi</strong>
      </div>
      <div class="card">
        <div class="label">Avg duration</div>
        <strong>${s.avg_duration} min</strong>
      </div>
      <div class="card">
        <div class="label">Avg speed</div>
        <strong>${s.avg_speed} mph</strong>
      </div>
      <div class="card accent">
        <div class="label">Excluded rows</div>
        <strong>${num(s.suspicious_count)}</strong>
      </div>
    `;
}

function populateBoroughFilter(boroughs) {
    const sel = document.getElementById('borough');
    boroughs.forEach(b => {
        const opt = document.createElement('option');
        opt.value = b.borough;
        opt.textContent = b.borough;
        sel.appendChild(opt);
    });
}

function renderHourlyChart(hourly) {
    const labels = hourly.map(h => h.hour + ':00');
    const data   = hourly.map(h => h.trips);
    // Colour rush hours differently
    const colors = hourly.map(h =>
        [7,8,9,16,17,18].includes(h.hour) ? '#e05a2b' : '#f7c948'
    );
    const ctx = document.getElementById('hourlyChart');
    if (Chart.getChart(ctx)) Chart.getChart(ctx).destroy();
    new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets: [{ label: 'Trips', data, backgroundColor: colors, borderRadius: 3 }] },
        options: {
            responsive: true,
            plugins: { legend: { display: false },
                       tooltip: { backgroundColor:'#111827', callbacks:{
                           label: c => ` ${c.parsed.y.toLocaleString()} trips`
                       }}}
        }
    });
}

function renderBoroughChart(boroughs) {
    makeChart('boroughChart', 'doughnut',
        boroughs.map(b => b.borough),
        boroughs.map(b => b.trips),
        'Trips'
    );
}

function renderSpeedChart(congestion) {
    makeChart('speedChart', 'line',
        congestion.map(h => h.hour + ':00'),
        congestion.map(h => h.avg_speed),
        'Avg speed (mph)',
        '#4a90c4'
    );
}

function renderDailyChart(daily) {
    const ctx = document.getElementById('dailyChart');
    if (Chart.getChart(ctx)) Chart.getChart(ctx).destroy();
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: daily.map(d => 'Jan ' + d.day),
            datasets: [{
                label: 'Trips',
                data:  daily.map(d => d.trip_count),
                backgroundColor: daily.map(d => d.is_weekend ? '#e8a020' : '#f7c948'),
                borderRadius: 3,
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false },
                       tooltip: { backgroundColor:'#111827', callbacks:{
                           label: c => ` ${c.parsed.y.toLocaleString()} trips`
                       }}}
        }
    });
}

function renderZones(zones) {
    document.getElementById('zones').innerHTML = zones.map(z => `
      <li>
        <strong>${z.zone}</strong>, ${z.borough}
        <span class="route-score">${num(z.pickups)} pickups · ${money(z.avg_fare)}</span>
      </li>
    `).join('');
}

function renderRoutes(routes) {
    document.getElementById('routes').innerHTML = routes.map(r => `
      <li>
        ${r.route}
        <span class="route-score">score ${r.score} · ${num(r.trip_count)} trips · ${money(r.total_revenue)}</span>
      </li>
    `).join('');
}

async function loadTrips(page) {
    currentPage = page || 1;
    const borough  = document.getElementById('borough').value;
    const distance = document.getElementById('distance').value || 0;
    const payment  = document.getElementById('payment').value;

    const params = new URLSearchParams({
        limit:        50,
        min_distance: distance,
        page:         currentPage,
    });
    if (borough) params.set('borough', borough);
    if (payment) params.set('payment', payment);

    try {
        const data = await get('/trips?' + params.toString());
        totalTrips = data.total;

        document.getElementById('trip-count').textContent =
            `${num(data.total)} trips · page ${data.page} of ${data.pages}`;

        if (!data.trips.length) {
            document.getElementById('trips').innerHTML =
                '<tr><td colspan="9" class="empty">No trips match these filters.</td></tr>';
            document.getElementById('pagination').innerHTML = '';
            return;
        }

        document.getElementById('trips').innerHTML = data.trips.map(t => `
          <tr>
            <td>${(t.pickup_datetime || '').slice(0, 16)}</td>
            <td>${t.pickup_zone} → ${t.dropoff_zone}</td>
            <td class="num">${Number(t.trip_distance).toFixed(2)} mi</td>
            <td class="num">${Number(t.duration_min).toFixed(1)} min</td>
            <td class="num">${Number(t.speed_mph || 0).toFixed(1)} mph</td>
            <td class="num">${money(t.fare_amount)}</td>
            <td class="num">${money(t.tip_amount)}</td>
            <td class="num">${money(t.total_amount)}</td>
            <td>${t.payment_label}</td>
          </tr>
        `).join('');

        renderPagination(data.page, data.pages);

    } catch (err) {
        document.getElementById('trips').innerHTML =
            `<tr><td colspan="9" class="empty" style="color:#e05a2b">${err.message}</td></tr>`;
    }
}

function renderPagination(current, total) {
    const el = document.getElementById('pagination');
    if (total <= 1) { el.innerHTML = ''; return; }

    const pages = [];
    for (let i = Math.max(1, current - 2); i <= Math.min(total, current + 2); i++) {
        pages.push(i);
    }

    el.innerHTML = `
      <button class="pg-btn" onclick="loadTrips(1)"             ${current===1    ?'disabled':''}>«</button>
      <button class="pg-btn" onclick="loadTrips(${current-1})"  ${current===1    ?'disabled':''}>‹</button>
      ${pages.map(p => `
        <button class="pg-btn${p===current?' active':''}" onclick="loadTrips(${p})">${p}</button>
      `).join('')}
      <button class="pg-btn" onclick="loadTrips(${current+1})"  ${current===total?'disabled':''}>›</button>
      <button class="pg-btn" onclick="loadTrips(${total})"      ${current===total?'disabled':''}>»</button>
      <span class="pg-info">${totalTrips.toLocaleString()} total trips</span>
    `;
}

document.getElementById('apply').addEventListener('click', () => loadTrips(1));

load();
