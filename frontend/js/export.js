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
}
