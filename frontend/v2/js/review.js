async function loadReviewState() {
	if (!state.projectId) return;
	try {
		const res = await apiFetch(`/review/state?project_id=${encodeURIComponent(state.projectId)}`, {}, 'v2');
		state.reviewState = res.current_state;
		state.availableTransitions = res.available_transitions || [];
		localStorage.setItem('bhudrishti_v2_review_state', res.current_state);
		const decisions = await apiFetch(`/review/decisions?project_id=${encodeURIComponent(state.projectId)}`, {}, 'v2');
		state.reviewDecisions = decisions || [];
	} catch (err) {
		console.warn('Failed to load review state:', err);
	}
}

async function transitionReviewState(toState) {
	if (!state.projectId) {
		notify('Select a project first.', 'error');
		return;
	}
	const note = window.prompt(`Enter note/reason for transitioning to ${toState}:`) || '';
	try {
		const res = await apiFetch(`/review/transition?project_id=${encodeURIComponent(state.projectId)}`, {
			method: 'POST',
			body: JSON.stringify({ to_state: toState, note: note.trim() || null })
		}, 'v2');
		notify(`Review state updated to ${res.to_state}.`, 'success');
		await loadReviewState();
		await renderView('review');
	} catch (err) {
		notify(`Transition failed: ${err.message}`, 'error');
	}
}