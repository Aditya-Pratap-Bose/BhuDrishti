const V2_MAP_DEFAULT_CENTER = [22.5, 79];
const V2_MAP_DEFAULT_ZOOM = 5;

const V2_LAYER_STYLES = {
	parcel:           { color: '#0f766e', fill: '#14b8a6', label: 'Parcels' },
	building:         { color: '#4338ca', fill: '#818cf8', label: 'Buildings' },
	road:             { color: '#b45309', fill: '#fbbf24', label: 'Roads' },
	access_corridor:  { color: '#c2410c', fill: '#fb923c', label: 'Access corridors' },
	land_use:         { color: '#047857', fill: '#34d399', label: 'Land use' },
	_default:         { color: '#0f766e', fill: '#14b8a6', label: 'AI features' },
};

function layerStyle(layerName) {
	return V2_LAYER_STYLES[layerName] || V2_LAYER_STYLES._default;
}

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
	const featureLayer = properties.layer || 'parcel';
	const style = layerStyle(featureLayer);
	const item = (window.v2ReconciliationItems || []).find(result => String(result.ai_parcel_id) === String(parcelId));
	const value = candidate => candidate === undefined || candidate === null ? 'N/A' : String(candidate);
	let html = `<strong>AI · ${escapeHtml(style.label)}</strong><br>ID: ${escapeHtml(String(parcelId))}`;
	html += `<br>Layer: ${escapeHtml(featureLayer)}`;
	html += `<br>Confidence: ${escapeHtml(value(properties.confidence || properties.confidence_score))}`;
	if (properties.area !== undefined && properties.area !== null) html += `<br>Area: ${escapeHtml(String(Number(properties.area).toFixed(2)))} sq m`;
	html += `<br>Status: ${escapeHtml(value(item?.status))}`;
	html += `<br>IoU: ${escapeHtml(value(item?.iou))}`;
	html += `<br>Area difference: ${escapeHtml(value(item?.area_difference_sqm))}`;
	html += `<br>Topology: ${escapeHtml(value(properties.topology_status))}`;
	if (feature.geometry && (feature.geometry.type === 'Polygon' || feature.geometry.type === 'MultiPolygon')) {
		html += `<br><button class="btn btn-primary" type="button" style="margin-top:6px;padding:3px 8px;font-size:11px" onclick="startEditingFeature('${escapeHtml(String(parcelId))}')">Edit Geometry</button>`;
	}
	return html;
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
	const allFeatures = Array.isArray(window.v2FeatureGeoJSON) ? window.v2FeatureGeoJSON : [];
	if (allFeatures.length) {
		const groups = {};
		allFeatures.forEach(feature => {
			const layerName = (feature.properties && feature.properties.layer) || 'parcel';
			if (!groups[layerName]) groups[layerName] = [];
			groups[layerName].push(feature);
		});
		Object.entries(groups).forEach(([layerName, features]) => {
			const style = layerStyle(layerName);
			const group = L.geoJSON({ type: 'FeatureCollection', features }, {
				style: { color: style.color, weight: 2, fillColor: style.fill, fillOpacity: 0.28 },
				onEachFeature: (feature, layer) => {
					layer.bindPopup(parcelInspectorPopup(feature));
				},
			});
			group.addTo(map);
			overlays[`AI · ${style.label}`] = group;
		});
	}
	addV2RasterOverlays(map, overlays);
	addV2ReferenceOverlay(overlays);
	addV2DifferenceOverlay(overlays);
	addV2ValidationOverlay(overlays);
	L.control.layers({ 'Street map': street, 'Satellite imagery': satellite }, overlays, {
		collapsed: false,
	}).addTo(map);
	addV2MapLegend(map, allFeatures);
	window.setTimeout(() => map.invalidateSize(), 0);
}

function addV2MapLegend(map, features) {
	const legend = L.control({ position: 'bottomright' });
	legend.onAdd = function () {
		const div = L.DomUtil.create('div', 'v2-map-legend');
		const layers = new Set((features || []).map(f => (f.properties && f.properties.layer) || 'parcel'));
		let html = '<strong>Legend</strong>';
		layers.forEach(name => {
			const s = layerStyle(name);
			html += `<div><span class="legend-swatch" style="background:${s.fill};border-color:${s.color}"></span>${escapeHtml(s.label)}</div>`;
		});
		if (window.v2ReferenceGeoJSON && window.v2ReferenceGeoJSON.features && window.v2ReferenceGeoJSON.features.length) {
			html += '<div><span class="legend-swatch" style="background:#f59e0b;border-color:#b45309"></span>Reference parcels</div>';
		}
		if (window.v2DifferenceGeoJSON && window.v2DifferenceGeoJSON.features && window.v2DifferenceGeoJSON.features.length) {
			html += '<div><span class="legend-swatch" style="background:#dc2626;border-color:#dc2626"></span>AI-only</div>';
			html += '<div><span class="legend-swatch" style="background:#2563eb;border-color:#2563eb"></span>Ref-only</div>';
			html += '<div><span class="legend-swatch" style="background:#16a34a;border-color:#16a34a"></span>Intersection</div>';
		}
		div.innerHTML = html;
		return div;
	};
	legend.addTo(map);
}

let activeEditFeatureId = null;
let activeEditMarkers = [];
let activeEditPolygon = null;

function startEditingFeature(featureId) {
	if (!window.v2Map || !Array.isArray(window.v2FeatureGeoJSON)) return;
	const feature = window.v2FeatureGeoJSON.find(f => {
		const props = f.properties || {};
		return String(props.id || props.ulpin || props.feature_id) === String(featureId);
	});
	if (!feature || !feature.geometry) {
		if (typeof notify === 'function') notify('Feature geometry not found.', 'error');
		return;
	}
	cancelEditingFeature();

	let coords = [];
	if (feature.geometry.type === 'Polygon') {
		coords = feature.geometry.coordinates[0] || [];
	} else if (feature.geometry.type === 'MultiPolygon') {
		coords = (feature.geometry.coordinates[0] && feature.geometry.coordinates[0][0]) || [];
	}
	if (!coords.length) return;

	activeEditFeatureId = featureId;
	const latLngs = coords.slice(0, -1).map(c => L.latLng(c[1], c[0]));
	activeEditPolygon = L.polygon(latLngs, { color: '#dc2626', weight: 3, dashArray: '6, 6', fillOpacity: 0.15 }).addTo(window.v2Map);

	activeEditMarkers = latLngs.map((latlng, idx) => {
		const marker = L.circleMarker(latlng, {
			radius: 6,
			color: '#dc2626',
			fillColor: '#ffffff',
			fillOpacity: 1.0,
			weight: 2
		}).addTo(window.v2Map);

		let isDragging = false;
		marker.on('mousedown', () => {
			isDragging = true;
			window.v2Map.dragging.disable();
			const onMove = e => {
				if (!isDragging) return;
				marker.setLatLng(e.latlng);
				latLngs[idx] = e.latlng;
				activeEditPolygon.setLatLngs(latLngs);
			};
			const onUp = () => {
				isDragging = false;
				window.v2Map.dragging.enable();
				window.v2Map.off('mousemove', onMove);
				window.v2Map.off('mouseup', onUp);
			};
			window.v2Map.on('mousemove', onMove);
			window.v2Map.on('mouseup', onUp);
		});
		return marker;
	});

	const status = document.getElementById('aoiStatus');
	if (status) {
		status.innerHTML = `Editing feature <b>${escapeHtml(String(featureId))}</b>. Drag vertex markers to reshape. <button class="btn btn-primary" type="button" style="padding:2px 6px;font-size:10px" onclick="finishEditingFeature()">Save</button> <button class="btn" type="button" style="padding:2px 6px;font-size:10px" onclick="cancelEditingFeature()">Cancel</button>`;
	}
	if (typeof notify === 'function') notify(`Editing vertices for ${featureId}. Drag white markers.`, 'info');
	window.v2Map.closePopup();
}

function finishEditingFeature() {
	if (!activeEditFeatureId || !activeEditPolygon) return;
	const latLngs = activeEditPolygon.getLatLngs()[0] || activeEditPolygon.getLatLngs();
	if (latLngs.length < 3) {
		if (typeof notify === 'function') notify('A polygon requires at least 3 vertices.', 'error');
		return;
	}
	const ring = latLngs.map(p => [Number(p.lng.toFixed(7)), Number(p.lat.toFixed(7))]);
	ring.push([...ring[0]]);

	const feature = (window.v2FeatureGeoJSON || []).find(f => {
		const props = f.properties || {};
		return String(props.id || props.ulpin || props.feature_id) === String(activeEditFeatureId);
	});
	if (feature) {
		feature.geometry = { type: 'Polygon', coordinates: [ring] };
		feature.properties = feature.properties || {};
		feature.properties.edited_manually = true;
		feature.properties.topology_status = 'PENDING_REVALIDATION';
	}
	cancelEditingFeature();
	if (typeof notify === 'function') notify('Geometry updated in session. Run validation or comparison to test updated shape.', 'success');
	if (typeof renderView === 'function') renderView('features');
}

function cancelEditingFeature() {
	if (activeEditPolygon && window.v2Map) window.v2Map.removeLayer(activeEditPolygon);
	activeEditPolygon = null;
	(activeEditMarkers || []).forEach(m => {
		if (window.v2Map) window.v2Map.removeLayer(m);
	});
	activeEditMarkers = [];
	activeEditFeatureId = null;
	const status = document.getElementById('aoiStatus');
	if (status) status.textContent = 'Select an AOI or use current map bounds.';
}