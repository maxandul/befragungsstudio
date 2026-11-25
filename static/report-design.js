(() => {
  const form = document.getElementById('report-design');
  const branches = [...form.querySelectorAll('[data-branch]')];
  const boxes = [...form.querySelectorAll('[name="report_oe"]')];
  const count = document.getElementById('package-count');
  function updateCount() {
    const n = boxes.filter(box => box.checked && !box.disabled).length;
    count.textContent = n ? ` · ${n} ausgewählt` : '';
  }
  const search = document.getElementById('oe-search');
  const openBeforeSearch = new Map();
  function showBranch() {
    const scope = branches.find(li => li.dataset.branch === form.elements.oe.value);
    const query = search.value.trim().toLocaleLowerCase();
    const matched = query ? branches.filter(li => (!scope || scope.contains(li)) &&
      li.dataset.unit.toLocaleLowerCase().includes(query)) : [];
    document.getElementById('no-oe-match').hidden = !query || matched.length > 0;
    for (const li of branches) {
      const allowed = !scope || scope.contains(li);
      const matchingBranch = !query || matched.some(match => li.contains(match) || match.contains(li));
      li.hidden = !matchingBranch || (!allowed && !li.contains(scope));
      const children = li.querySelector('details');
      if (children && query && matched.some(match => li !== match && li.contains(match))) {
        if (!openBeforeSearch.has(children)) openBeforeSearch.set(children, children.open);
        children.open = true;
      }
      const box = li.querySelector('input');
      box.disabled = !allowed;
      if (scope && li !== scope && li.contains(scope)) li.querySelector('details').open = true;
    }
    updateCount();
  }
  for (const box of boxes) {
    if (box.checked) {
      for (let parent = box.closest('details'); parent && parent.id !== 'report-package'; parent = parent.parentElement.closest('details')) parent.open = true;
    }
    box.addEventListener('change', updateCount);
  }
  function showWaves() {
    document.getElementById('comparison-waves').hidden = Boolean(form.elements.focus_wave.value);
  }
  document.getElementById('package-search').hidden = false;
  search.addEventListener('input', () => {
    for (const [details, open] of openBeforeSearch) details.open = open;
    openBeforeSearch.clear();
    showBranch();
  });
  form.elements.oe.addEventListener('change', showBranch);
  form.elements.focus_wave.addEventListener('change', showWaves);
  showBranch();
  showWaves();
})();
