(() => {
  const panel = document.getElementById('activity');
  const label = panel.querySelector('span');
  const active = new Map();
  let timer;

  function render() {
    clearTimeout(timer);
    if (!active.size) {
      panel.hidden = true;
      label.textContent = '';
      return;
    }
    const show = () => {
      label.textContent = Array.from(active.values()).pop();
      panel.hidden = false;
    };
    if (panel.hidden) timer = setTimeout(show, 180);
    else show();
  }

  function start(message) {
    const key = Symbol();
    active.set(key, message);
    render();
    return () => { active.delete(key); render(); };
  }
  window.studioActivity = start;

  let endNavigation;
  function navigate() {
    endNavigation?.();
    endNavigation = start('Seite wird geladen …');
  }
  window.addEventListener('pageshow', () => { endNavigation?.(); });
  if (window.navigation) {
    navigation.addEventListener('navigate', event => {
      if (event.hashChange || event.downloadRequest !== null) return;
      navigate();
      event.signal.addEventListener('abort', endNavigation, {once:true});
    });
    navigation.addEventListener('navigateerror', () => endNavigation?.());
  }

  async function download(url, options) {
    const done = start('Download wird vorbereitet …');
    try {
      const response = await fetch(url, options);
      const disposition = response.headers.get('Content-Disposition') || '';
      if (!response.ok || !disposition.startsWith('attachment')) {
        const error = new DOMParser().parseFromString(await response.text(), 'text/html');
        throw new Error(error.querySelector('main .notice')?.textContent || 'Download fehlgeschlagen.');
      }
      const blobUrl = URL.createObjectURL(await response.blob());
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = /filename="?([^";]+)"?/i.exec(disposition)?.[1] || 'Download';
      a.click();
      setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
    } catch (error) {
      window.alert(error.message);
    } finally {
      done();
    }
  }

  document.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.shiftKey ||
        event.metaKey || event.altKey || link.target && link.target !== '_self' ||
        link.origin !== location.origin || link.hasAttribute('download')) return;
    if (link.hasAttribute('data-attachment')) {
      event.preventDefault();
      download(link.href);
    } else if (!window.navigation && !(link.hash && link.pathname === location.pathname && link.search === location.search)) {
      navigate();
    }
  });
  document.addEventListener('submit', event => {
    if (event.defaultPrevented) return;
    const form = event.target;
    if (event.submitter?.formTarget === '_blank') return;
    if (form.hasAttribute('data-attachment') || event.submitter?.hasAttribute('data-attachment')) {
      event.preventDefault();
      download(form.getAttribute('action'), {method:'POST', body:new FormData(form, event.submitter)});
    } else if (!window.navigation) navigate();
  });
  window.addEventListener('keydown', event => {
    if (event.key === 'Escape') endNavigation?.();
  });
})();
