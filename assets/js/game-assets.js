(function () {
  'use strict';

  const ROOT = 'assets/game';
  const cache = new Map();
  const listeners = new Set();
  let loaded = 0;
  let missing = 0;

  function notify() {
    const detail = { loaded, missing, pending: [...cache.values()].filter(item => item.state === 'loading').length };
    listeners.forEach(listener => listener(detail));
  }

  function request(url) {
    if (!url) return null;
    const known = cache.get(url);
    if (known) return known.state === 'ready' ? known.image : null;

    const item = { state: 'loading', image: new Image() };
    cache.set(url, item);
    item.image.decoding = 'async';
    item.image.onload = () => {
      item.state = 'ready';
      loaded++;
      notify();
      window.dispatchEvent(new CustomEvent('gameassetload'));
    };
    item.image.onerror = () => {
      item.state = 'missing';
      missing++;
      notify();
    };
    item.image.src = url;
    return null;
  }

  const api = {
    building(id, level) {
      const safeId = Number(id);
      const safeLevel = Math.max(1, Number(level) || 1);
      if (!Number.isFinite(safeId)) return null;
      return request(`${ROOT}/buildings/${safeId}/level-${safeLevel}.webp`);
    },
    wall(level) {
      return request(`${ROOT}/walls/level-${Math.max(1, Number(level) || 1)}.webp`);
    },
    scenery(name) {
      const item = (window.SCENERY_CATALOG || []).find(entry => entry.id === name);
      return request(`${ROOT}/scenery/${item?.file || `${name}.webp`}`);
    },
    sceneryInfo(name) {
      return (window.SCENERY_CATALOG || []).find(entry => entry.id === name) || null;
    },
    sceneryCatalog: window.SCENERY_CATALOG || [],
    onStatus(listener) {
      listeners.add(listener);
      listener({ loaded, missing, pending: 0 });
      return () => listeners.delete(listener);
    },
    convention: {
      building: `${ROOT}/buildings/{building-id}/level-{level}.webp`,
      wall: `${ROOT}/walls/level-{level}.webp`,
      scenery: `${ROOT}/scenery/{name}.webp`
    }
  };

  window.GameAssetPack = api;
})();
