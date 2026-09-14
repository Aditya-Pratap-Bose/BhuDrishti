const V2_MAP_DEFAULT_CENTER = [22.5, 79];
const V2_MAP_DEFAULT_ZOOM = 5;

function fitV2MapToBounds(bounds) {
	if (!window.v2Map || !Array.isArray(bounds) || bounds.length !== 4) return;
	const [minLon, minLat, maxLon, maxLat] = bounds.map(Number);
	if (![minLon, minLat, maxLon, maxLat].every(Number.isFinite) || minLon >= maxLon || minLat >= maxLat) return;
	window.v2Map.fitBounds([[minLat, minLon], [maxLat, maxLon]], { padding: [24, 24] });
}

function enableV2RectangleAoi() {
	if (!window.v2Map) return;
	const map = window.v2Map;
	let firstPoint = null;
	if (window.v2AoiRectangle) map.removeLayer(window.v2AoiRectangle);
	map.getContainer().classList.add('v2-map-drawing');
	const finish = event => {
		if (!firstPoint) {
			firstPoint = event.latlng;
			return;
		}
		const bounds = L.latLngBounds(firstPoint, event.latlng);
		if (bounds.getNorth() === bounds.getSouth() || bounds.getEast() === bounds.getWest()) return;
		window.v2AoiRectangle = L.rectangle(bounds, { color: '#0f766e', weight: 2, fillOpacity: 0.12 }).addTo(map);
		window.v2AoiBounds = [bounds.getWest(), bounds.getSouth(), bounds.getEast(), bounds.getNorth()];
		map.getContainer().classList.remove('v2-map-drawing');
		map.off('click', finish);
		const status = document.getElementById('aoiStatus');
		if (status) status.textContent = 'Rectangle selected. Save AOI to persist it.';
	};
	map.off('click').on('click', finish);
	const status = document.getElementById('aoiStatus');
	if (status) status.textContent = 'Click two opposite corners on the map.';
}

function enableV2PolygonAoi() {
	if (!window.v2Map) return;
	const map = window.v2Map;
	const points = [];
	if (window.v2AoiPolygon) map.removeLayer(window.v2AoiPolygon);
	map.getContainer().classList.add('v2-map-drawing');
	const finish = () => {
		if (points.length < 3) return;
		const ring = points.map(point => [point.lng, point.lat]);
		ring.push(ring[0]);
		window.v2AoiPolygon = L.polygon(points, { color: '#0f766e', weight: 2, fillOpacity: 0.12 }).addTo(map);
		window.v2AoiGeometry = { type: 'Polygon', coordinates: [ring] };
		map.getContainer().classList.remove('v2-map-drawing');
		map.off('click', addPoint);
		const status = document.getElementById('aoiStatus');
		if (status) status.textContent = 'Polygon selected. Save AOI to persist it.';
	};
	const addPoint = event => {
		points.push(event.latlng);
		if (window.v2AoiPolygon) map.removeLayer(window.v2AoiPolygon);
		if (points.length > 1) window.v2AoiPolygon = L.polyline(points, { color: '#0f766e', weight: 2 }).addTo(map);
		const status = document.getElementById('aoiStatus');
		if (status) status.textContent = `${points.length} polygon point(s). Add at least 3, then finish.`;
	};
	map.off('click').on('click', addPoint);
	const finishButton = document.getElementById('finishPolygonAoi');
	if (finishButton) {
		finishButton.hidden = false;
		finishButton.onclick = finish;
	}
	const status = document.getElementById('aoiStatus');
	if (status) status.textContent = 'Click polygon points, then finish polygon.';
}

const AuthenticatedTileLayer = L.TileLayer.extend({
	createTile(coords, done) {
		const tile = document.createElement('img');
		tile.alt = '';
		tile.setAttribute('role', 'presentation');
		const url = this.getTileUrl(coords);
		const token = typeof getAuthToken === 'function' ? getAuthToken() : null;
		fetch(url, token ? { headers: { Authorization: `Bearer ${token}` } } : {})
			.then(response => {
				if (!response.ok) throw new Error(`Raster tile request failed (${response.status})`);
				return response.blob();
			})
			.then(blob => {
				tile.onload = () => { URL.revokeObjectURL(tile.src); done(null, tile); };
				tile.onerror = () => done(new Error('Raster tile could not be rendered'), tile);
				tile.src = URL.createObjectURL(blob);
			})
			.catch(error => done(error, tile));
		return tile;
	},
});

function addV2RasterOverlays(map, overlays) {
	const datasets = Array.isArray(window.v2RasterDatasets) ? window.v2RasterDatasets : [];
	datasets.forEach(dataset => {
		const storageUri = String(dataset.storage_uri || '');
		const assetId = storageUri.split('/').pop();
		if (!assetId || !/\.(tif|tiff)$/i.test(assetId) || dataset.validation_status !== 'valid') return;
		const layer = new AuthenticatedTileLayer(`${getApiUrl(`/tiles/${encodeURIComponent(assetId)}/{z}/{x}/{y}.png`, 'v2')}`, {
			attribution: 'BhuDrishti raster asset',
			opacity: 0.75,
			maxZoom: 22,
		});
		overlays[`${dataset.dataset_type} · ${dataset.name}`] = layer;
	});
}

function addV2ReferenceOverlay(overlays) {
	const featureCollection = window.v2ReferenceGeoJSON;
	if (!featureCollection || !Array.isArray(featureCollection.features) || !featureCollection.features.length) return;
	const reference = L.geoJSON(featureCollection, {
		style: { color: '#b45309', weight: 2, fillColor: '#f59e0b', fillOpacity: 0.16 },
		onEachFeature: (feature, layer) => {
			const properties = feature.properties || {};
			const label = properties.parcel_number || properties.survey_number || properties.reference_id;
			if (label) layer.bindPopup(`<strong>Reference parcel</strong><br>${escapeHtml(String(label))}`);
		},
	});
	reference.addTo(window.v2Map);
	overlays['Reference parcels'] = reference;
}

function parcelInspectorPopup(feature) {
	const properties = feature.properties || {};
	const parcelId = properties.id || properties.ulpin || properties.feature_id || 'N/A';
	const item = (window.v2ReconciliationItems || []).find(result => String(result.ai_parcel_id) === String(parcelId));
	const value = candidate => candidate === undefined || candidate === null ? 'N/A' : String(candidate);
	return `<strong>AI parcel</strong><br>Parcel: ${escapeHtml(String(parcelId))}<br>Confidence: ${escapeHtml(value(properties.confidence || properties.confidence_score))}<br>Status: ${escapeHtml(value(item?.status))}<br>IoU: ${escapeHtml(value(item?.iou))}<br>Area difference: ${escapeHtml(value(item?.area_difference_sqm))}<br>Topology: ${escapeHtml(value(properties.topology_status))}`;
}

function addV2DifferenceOverlay(overlays) {
	const featureCollection = window.v2DifferenceGeoJSON;
	if (!featureCollection || !Array.isArray(featureCollection.features) || !featureCollection.features.length) return;
	const colors = { ai_only: '#dc2626', reference_only: '#2563eb', intersection: '#16a34a' };
	const differences = L.geoJSON(featureCollection, {
		style: feature => ({
			color: colors[feature.properties?.difference_type] || '#52525b',
			weight: 2,
			fillColor: colors[feature.properties?.difference_type] || '#52525b',
			fillOpacity: 0.3,
		}),
	});
	differences.addTo(window.v2Map);
	overlays['Reference vs AI difference'] = differences;
}

function addV2ValidationOverlay(overlays) {
	const featureCollection = window.v2ValidationIssues;
	if (!featureCollection || !Array.isArray(featureCollection.features) || !featureCollection.features.length) return;
	const colors = { CRITICAL: '#991b1b', ERROR: '#dc2626', WARNING: '#d97706', INFO: '#2563eb' };
	const issues = L.geoJSON(featureCollection, {
		pointToLayer: (feature, latlng) => L.circleMarker(latlng, { radius: 7, color: colors[feature.properties?.severity] || '#52525b', fillColor: colors[feature.properties?.severity] || '#52525b', fillOpacity: 0.8 }),
		style: feature => ({ color: colors[feature.properties?.severity] || '#52525b', weight: 3, fillOpacity: 0.25 }),
		onEachFeature: (feature, layer) => {
			const properties = feature.properties || {};
			const resolveAction = properties.id ? `<br><button class="btn" type="button" onclick="resolveTopologyIssue('${escapeHtml(String(properties.id))}')">Resolve issue</button>` : '';
			layer.bindPopup(`<strong>${escapeHtml(String(properties.issue_type || 'Validation issue'))}</strong><br>Severity: ${escapeHtml(String(properties.severity || 'N/A'))}<br>${escapeHtml(String(properties.description || 'N/A'))}${resolveAction}`);
		},
	});
	issues.addTo(window.v2Map);
	overlays['Validation issues'] = issues;
}

function renderV2Map(target = 'mapPanel', label = 'Web GIS map') {
	const el = document.getElementById(target);
	if (!el) return;

	el.innerHTML = `<div class="v2-map"><div class="map-copy"><span>${escapeHtml(label)}</span><button class="btn" type="button" onclick="enableV2RectangleAoi()">Draw rectangle</button><button class="btn" type="button" onclick="enableV2PolygonAoi()">Draw polygon</button><button class="btn" id="finishPolygonAoi" type="button" hidden>Finish polygon</button><small id="aoiStatus">Select an AOI or use current map bounds.</small></div><div class="v2-leaflet"></div></div>`;
	if (typeof L === 'undefined') return;

	const map = L.map(el.querySelector('.v2-leaflet'), {
		center: V2_MAP_DEFAULT_CENTER,
		zoom: V2_MAP_DEFAULT_ZOOM,
		zoomControl: true,
	});
	window.v2Map = map;
	const street = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
		attribution: '&copy; OpenStreetMap contributors',
		maxZoom: 19,
	});
	const satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
		attribution: 'Tiles &copy; Esri',
		maxZoom: 19,
	});

	street.addTo(map);
	const overlays = {};
	const featureCollection = {
		type: 'FeatureCollection',
		features: Array.isArray(window.v2FeatureGeoJSON) ? window.v2FeatureGeoJSON : [],
	};
	if (featureCollection.features.length) {
		const aiFeatures = L.geoJSON(featureCollection, {
			style: { color: '#0f766e', weight: 2, fillColor: '#14b8a6', fillOpacity: 0.28 },
			onEachFeature: (feature, layer) => {
				const properties = feature.properties || {};
				const label = properties.id || properties.ulpin || properties.feature_id;
				layer.bindPopup(parcelInspectorPopup(feature));
			},
		});
		aiFeatures.addTo(map);
		overlays['AI features'] = aiFeatures;
	}
	addV2RasterOverlays(map, overlays);
	addV2ReferenceOverlay(overlays);
	addV2DifferenceOverlay(overlays);
	addV2ValidationOverlay(overlays);
	L.control.layers({ 'Street map': street, 'Satellite imagery': satellite }, overlays, {
		collapsed: false,
	}).addTo(map);
	window.setTimeout(() => map.invalidateSize(), 0);
}