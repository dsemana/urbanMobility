const API='http://127.0.0.1:5000/api';
const money=n=>'$'+Number(n||0).toFixed(2);
async function get(path){const r=await fetch(API+path);return await r.json();}
function makeChart(id,type,labels,data,label){new Chart(document.getElementById(id),{type,data:{labels,datasets:[{label,data}]},options:{responsive:true}});}
async function load(){
 const [summary,hourly,boroughs,zones,routes]=await Promise.all([get('/summary'),get('/hourly'),get('/boroughs'),get('/top-zones'),get('/ranked-routes')]);
 document.getElementById('cards').innerHTML=`<div class='card'>Trips<strong>${summary.trips}</strong></div><div class='card'>Avg distance<strong>${summary.avg_distance} mi</strong></div><div class='card'>Avg duration<strong>${summary.avg_duration} min</strong></div><div class='card'>Revenue<strong>${money(summary.revenue)}</strong></div><div class='card'>Suspicious<strong>${summary.suspicious_count}</strong></div>`;
 const sel=document.getElementById('borough'); boroughs.forEach(b=>sel.insertAdjacentHTML('beforeend',`<option>${b.borough}</option>`));
 makeChart('hourlyChart','bar',hourly.map(x=>x.hour),hourly.map(x=>x.trips),'Trips');
 makeChart('boroughChart','pie',boroughs.map(x=>x.borough),boroughs.map(x=>x.trips),'Trips');
 document.getElementById('zones').innerHTML=zones.map(z=>`<li>${z.zone}, ${z.borough}: ${z.pickups} pickups, avg ${money(z.avg_fare)}</li>`).join('');
 document.getElementById('routes').innerHTML=routes.map(r=>`<li>${r.route}: score ${r.score}, ${r.trip_count} trips, ${money(r.total_revenue)}</li>`).join('');
 await loadTrips();
}
async function loadTrips(){const b=document.getElementById('borough').value;const d=document.getElementById('distance').value||0;const trips=await get(`/trips?limit=50&min_distance=${d}&borough=${encodeURIComponent(b)}`);document.getElementById('trips').innerHTML=trips.map(t=>`<tr><td>${t.pickup_datetime}</td><td>${t.pickup_zone} -> ${t.dropoff_zone}</td><td>${Number(t.trip_distance).toFixed(2)} mi</td><td>${Number(t.duration_min).toFixed(1)} min</td><td>${money(t.total_amount)}</td></tr>`).join('');}
document.getElementById('apply').onclick=loadTrips;load();
