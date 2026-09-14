async function requestQualityReport() {
	const confidences = state.features
		.map(f => Number(f.properties?.confidence ?? f.properties?.confidence_score))
		.filter(Number.isFinite);
	const issues = window.v2ValidationIssues?.features || [];
	const summary = state.reconciliation?.summary || null;
	const payload = {
		total_features: state.features.length,
		invalid_geometry_count: issues.filter(i => i.properties?.issue_type === 'INVALID_GEOMETRY').length,
		overlap_count: issues.filter(i => i.properties?.issue_type === 'PARCEL_OVERLAP').length,
		duplicate_count: issues.filter(i => i.properties?.issue_type === 'DUPLICATE').length,
		sliver_count: issues.filter(i => i.properties?.issue_type === 'SLIVER').length,
		reconciliation_summary: summary
	};
	if (confidences.length) {
		payload.mean_ai_confidence = confidences.reduce((sum, v) => sum + v, 0) / confidences.length;
	}
	try {
		const report = await apiFetch('/quality/report', {
			method: 'POST',
			body: JSON.stringify(payload)
		}, 'v2');
		state.quality = report;
		notify('Quality report generated from current loaded data.', 'success');
		await renderView('quality');
	} catch (err) {
		notify(`Quality report error: ${err.message}`, 'error');
	}
}

async function runReferenceAccuracyBenchmark() {
	if (!state.projectId) {
		notify('Select a project first.', 'error');
		return;
	}
	const reference = window.v2ReferenceGeoJSON?.features || [];
	if (!reference.length) {
		notify('No authoritative reference parcels loaded. Load Telangana reference or register an existing dataset first.', 'error');
		return;
	}
	if (!state.features.length) {
		notify('No AI feature candidates loaded. Run feature extraction first.', 'error');
		return;
	}
	try {
		const benchmark = await apiFetch('/reference/benchmark', {
			method: 'POST',
			body: JSON.stringify({
				project_id: state.projectId,
				ai_features: state.features,
				reference_features: reference,
				match_iou_threshold: 0.85,
				minor_iou_threshold: 0.60
			})
		}, 'v2');
		state.benchmarkResult = benchmark;
		state.quality = benchmark.quality_evaluation;
		notify(`Accuracy benchmark evaluated across ${benchmark.reference_count} reference parcels!`, 'success');
		await renderView('quality');
	} catch (err) {
		notify(`Benchmark failed: ${err.message}`, 'error');
	}
}