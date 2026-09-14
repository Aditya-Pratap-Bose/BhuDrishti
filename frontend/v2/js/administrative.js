const administrativeState = {
  states: [],
  districts: [],
  selectedState: null,
};

async function loadAdministrativeStates() {
  const response = await apiFetch('/administrative/states', {}, 'v2');
  administrativeState.states = response.items || [];
  const list = document.getElementById('projectStateOptions');
  if (list) {
    list.innerHTML = administrativeState.states
      .map(item => `<option value="${escapeHtml(item.name)}"></option>`)
      .join('');
  }
}

async function loadProjectDistricts(event) {
  const input = event.target;
  const selected = administrativeState.states.find(item => item.name === input.value);
  administrativeState.selectedState = selected || null;
  administrativeState.districts = [];
  const districtInput = document.getElementById('projectDistrictInput');
  const list = document.getElementById('projectDistrictOptions');
  if (!districtInput || !list) return;
  districtInput.value = '';
  districtInput.disabled = !selected;
  if (!selected) {
    list.innerHTML = '';
    return;
  }
  districtInput.placeholder = 'Loading districts...';
  const response = await apiFetch(`/administrative/states/${encodeURIComponent(selected.id)}/districts`, {}, 'v2');
  administrativeState.districts = response.items || [];
  list.innerHTML = administrativeState.districts
    .map(item => `<option value="${escapeHtml(item.name)}"></option>`)
    .join('');
  districtInput.placeholder = 'Search district';
}
