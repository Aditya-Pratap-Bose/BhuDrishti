// =================================================================
// js/export.js — GeoJSON, KML, PDF export. Sab client-side hai —
// koi extra backend load nahi, koi naya Python dependency nahi.
// Isliye demo din ye sabse reliable feature rahega.
// =================================================================

function downloadBlob(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

function exportGeoJSON(features) {
  if (!features || !features.length) { showToast('Export karne ke liye pehle parcels detect/save karein.', 'error'); return; }
  downloadBlob(JSON.stringify({ type: 'FeatureCollection', features }, null, 2), `bhudrishti-parcels-${Date.now()}.geojson`, 'application/geo+json');
}

// Sirf Polygon geometries handle karta hai — humara poora pipeline
// hamesha Polygon hi return karta hai.
function geojsonToKML(features) {
  const placemarks = features.map((f) => {
    const p = f.properties;
    if (f.geometry.type !== 'Polygon') return '';
    const coords = f.geometry.coordinates[0].map(([lon, lat]) => `${lon},${lat},0`).join(' ');
    return `
    <Placemark>
      <name>${p.ulpin}</name>
      <description>Area: ${p.area_sqm.toFixed(1)} sqm | Perimeter: ${p.perimeter_m.toFixed(1)} m | Land use: ${p.land_use || 'Unclassified'}${p.owner_name ? ' | Owner: ' + p.owner_name : ''}</description>
      <Polygon><outerBoundaryIs><LinearRing><coordinates>${coords}</coordinates></LinearRing></outerBoundaryIs></Polygon>
    </Placemark>`;
  }).join('');

  return `<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>BhuDrishti Parcels</name>
    ${placemarks}
  </Document>
</kml>`;
}

function exportKML(features) {
  if (!features || !features.length) { showToast('Export karne ke liye pehle parcels detect/save karein.', 'error'); return; }
  downloadBlob(geojsonToKML(features), `bhudrishti-parcels-${Date.now()}.kml`, 'application/vnd.google-earth.kml+xml');
  showToast('KML exported successfully.', 'success');
}

function exportParcelPDF(feature) {
  if (!feature) {
    showToast('Koi parcel selected nahi hai.', 'error');
    return;
  }
  const p = feature.properties || {};
  const printWindow = window.open('', '_blank', 'width=800,height=900');
  if (!printWindow) {
    showToast('Popup blocker ko allow karein PDF certificate generate karne ke liye.', 'error');
    return;
  }

  const coords = (feature.geometry && feature.geometry.coordinates && feature.geometry.coordinates[0])
    ? feature.geometry.coordinates[0].map(c => `[${Number(c[0]).toFixed(6)}, ${Number(c[1]).toFixed(6)}]`).join(', ')
    : 'N/A';

  const html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Cadastral Parcel Certificate - ${p.ulpin || 'BhuDrishti'}</title>
  <style>
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 40px; color: #111; background: #fff; line-height: 1.5; }
    .header { border-bottom: 2px solid #10B981; padding-bottom: 16px; margin-bottom: 24px; display: flex; justify-content: space-between; align-items: center; }
    .title { font-size: 22px; font-weight: bold; color: #064E3B; margin: 0; }
    .sub { font-size: 11px; color: #666; margin-top: 4px; }
    .badge { background: #ECFDF5; color: #065F46; border: 1px solid #A7F3D0; padding: 4px 10px; border-radius: 999px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 24px; }
    .card { background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; padding: 12px; }
    .card-label { font-size: 10px; text-transform: uppercase; color: #6B7280; font-weight: 600; margin-bottom: 4px; }
    .card-value { font-size: 14px; font-weight: 600; color: #111827; font-family: monospace; }
    .section-title { font-size: 12px; font-weight: 700; text-transform: uppercase; color: #374151; margin-bottom: 8px; }
    .coords-box { background: #F3F4F6; border: 1px solid #E5E7EB; border-radius: 8px; padding: 12px; font-family: monospace; font-size: 11px; word-break: break-all; color: #4B5563; max-height: 120px; overflow-y: auto; margin-bottom: 24px; }
    .footer { border-top: 1px solid #E5E7EB; padding-top: 14px; display: flex; justify-content: space-between; font-size: 11px; color: #9CA3AF; }
    @media print {
      body { margin: 20px; }
      .no-print { display: none; }
    }
  </style>
</head>
<body>
  <div class="header">
    <div>
      <h1 class="title">BhuDrishti AI &mdash; Land Parcel Record</h1>
      <div class="sub">National Geospatial Automated Cadastral Registry &bull; Verified Record</div>
    </div>
    <div class="badge">Official Record</div>
  </div>

  <div class="grid">
    <div class="card">
      <div class="card-label">Unique Land Parcel Identifier (ULPIN)</div>
      <div class="card-value" style="color: #059669;">${p.ulpin || 'N/A'}</div>
    </div>
    <div class="card">
      <div class="card-label">Legal Owner Name</div>
      <div class="card-value" style="font-family: inherit;">${p.owner_name || 'Not Assigned / Unregistered'}</div>
    </div>
    <div class="card">
      <div class="card-label">Calculated Area</div>
      <div class="card-value">${p.area_sqm ? Number(p.area_sqm).toFixed(2) + ' sq. meters' : 'N/A'}</div>
    </div>
    <div class="card">
      <div class="card-label">Boundary Perimeter</div>
      <div class="card-value">${p.perimeter_m ? Number(p.perimeter_m).toFixed(2) + ' meters' : 'N/A'}</div>
    </div>
    <div class="card">
      <div class="card-label">Land Use Classification</div>
      <div class="card-value" style="font-family: inherit;">${p.land_use || 'Unclassified'}</div>
    </div>
    <div class="card">
      <div class="card-label">Extraction Timestamp</div>
      <div class="card-value" style="font-size: 12px;">${p.created_at ? new Date(p.created_at).toLocaleString() : new Date().toLocaleString()}</div>
    </div>
  </div>

  <div class="section-title">Polygon Boundary Coordinates (WGS84)</div>
  <div class="coords-box">${coords}</div>

  <div class="footer">
    <span>Generated by BhuDrishti AI Cadastral Engine</span>
    <span>Verification Hash: ${p.ulpin ? p.ulpin.split('-').pop() : 'OK'}</span>
  </div>

  <script>
    window.onload = function() {
      setTimeout(() => { window.print(); }, 350);
    };
  </script>
</body>
</html>`;

  printWindow.document.write(html);
  printWindow.document.close();
}
