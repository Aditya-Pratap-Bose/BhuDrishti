async function generateExport(format) {
	if (!state.features.length) {
		notify('Run feature extraction or load a feature set first.', 'error');
		return;
	}
	const endpoint = format === 'csv' ? '/exports/csv' : '/exports/geojson';
	const data = await apiFetch(endpoint, {
		method: 'POST',
		body: JSON.stringify({ features: state.features, metadata: { project_id: state.projectId } })
	}, 'v2');
	if (format === 'geojson') {
		const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/geo+json' });
		const link = document.createElement('a');
		link.href = URL.createObjectURL(blob);
		link.download = 'bhudrishti-v2-features.geojson';
		link.click();
	} else if (format === 'csv') {
		const blob = new Blob([data], { type: 'text/csv' });
		const link = document.createElement('a');
		link.href = URL.createObjectURL(blob);
		link.download = 'bhudrishti-v2-features.csv';
		link.click();
	}
	notify(`${format.toUpperCase()} export generated.`, 'success');
}

async function generateCadastralPackage() {
	if (!state.projectId) {
		notify('Select a project first.', 'error');
		return;
	}
	if (!state.features.length) {
		notify('No validated features available for packaging.', 'error');
		return;
	}
	const project = state.projects.find(p => p.id === state.projectId);
	const unresolvedErrors = (window.v2ValidationIssues?.features || [])
		.filter(i => i.properties?.severity === 'CRITICAL' || i.properties?.severity === 'ERROR').length;
	const payload = {
		project_metadata: {
			id: project?.id,
			name: project?.name,
			state: project?.state,
			district: project?.district,
			ulb: project?.ulb
		},
		survey_unit: state.surveyId ? `SU-${String(state.surveyId).slice(0, 8)}` : 'SU-DEFAULT',
		features: state.features,
		crs: 'EPSG:32643',
		unresolved_topology_errors: unresolvedErrors,
		model_version: '2.0.0'
	};
	try {
		const res = await apiFetch('/exports/package', {
			method: 'POST',
			body: JSON.stringify(payload)
		}, 'v2');
		state.lastPackageResult = res;
		if (res.status === 'READY') {
			notify(`Cadastral package READY: ${res.package_id}`, 'success');
		} else {
			notify(`Package BLOCKED: ${(res.audit_reasons || []).join(', ')}`, 'error');
		}
		await renderView('exports');
	} catch (err) {
		notify(`Package generation failed: ${err.message}`, 'error');
	}
}