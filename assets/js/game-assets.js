(function () {
  'use strict';

  const ROOT = 'assets/game';
  const BUILDING_SOURCE_ROOT = `${ROOT}/buildings-source`;
  const BUILDING_SOURCE = Object.freeze({
    // Home Village IDs from the in-game village export. Builder Base reuses
    // several numeric IDs, so this table must stay scoped to obj.buildings.
    1000000: { dir: 'army/army-camp', prefix: 'Army Camp', max: 14 },
    1000001: { dir: 'resource/town-hall', max: 18, file: level => `Town Hall${level}${level === 17 ? '-1' : ''}.png` },
    1000002: { dir: 'resource/elixir-collector', prefix: 'Elixir Collector', max: 17 },
    1000003: { dir: 'resource/elixir-storage', prefix: 'Elixir Storage', max: 19 },
    1000004: { dir: 'resource/gold-mine', prefix: 'Gold Mine', max: 17 },
    1000005: { dir: 'resource/gold-storage', prefix: 'Gold Storage', max: 19 },
    1000006: { dir: 'army/barracks', prefix: 'Barracks', max: 19 },
    1000007: { dir: 'army/laboratory', prefix: 'Laboratory', max: 16 },
    1000008: { dir: 'defensive/cannon', prefix: 'Cannon', max: 21 },
    1000009: { dir: 'defensive/archer-tower', prefix: 'Archer Tower', max: 21 },
    1000011: { dir: 'defensive/wizard-tower', prefix: 'Wizard Tower', max: 17 },
    1000012: { dir: 'defensive/air-defense', prefix: 'Air Defense', max: 16 },
    1000013: { dir: 'defensive/mortar', prefix: 'Mortar', max: 18 },
    1000014: { dir: 'resource/clan-castle', prefix: 'Clan Castle', max: 14 },
    1000015: { dir: 'other/builder-s-hut', file: 'Builders Hut.png' },
    1000019: { dir: 'defensive/hidden-tesla', prefix: 'Hidden Tesla', max: 17 },
    1000020: { dir: 'army/spell-factory', prefix: 'Spell Factory', max: 9 },
    1000021: { dir: 'defensive/x-bow', prefix: 'X-Bow', max: 13, variant: () => ' Ground' },
    1000023: { dir: 'resource/dark-elixir-drill', prefix: 'Dark Elixir Drill', max: 11 },
    1000024: { dir: 'resource/dark-elixir-storage', prefix: 'Dark Elixir Storage', max: 13 },
    1000026: { dir: 'army/dark-barracks', prefix: 'Dark Barracks', max: 13 },
    1000027: { dir: 'defensive/inferno-tower', prefix: 'Inferno Tower', max: 12, variant: () => ' Single' },
    1000028: { dir: 'defensive/air-sweeper', prefix: 'Air Sweeper', max: 7 },
    1000029: { dir: 'army/dark-spell-factory', prefix: 'Dark Spell Factory', max: 8 },
    1000031: { dir: 'defensive/eagle-artillery', prefix: 'Eagle Artillery', max: 7 },
    1000032: { dir: 'defensive/bomb-tower', prefix: 'Bomb Tower', max: 13 },
    1000059: { dir: 'army/workshop', prefix: 'Workshop', max: 9 },
    1000067: { dir: 'defensive/scattershot', prefix: 'Scattershot', max: 7 },
    1000068: { dir: 'army/pet-house', prefix: 'Pet House', max: 12 },
    1000070: {
      dir: 'army/blacksmith',
      max: 10,
      file: level => `Blacksmith${Math.min(9, level % 2 === 0 ? level - 1 : level)}.png`
    },
    1000071: { dir: 'army/hero-hall', prefix: 'Hero Hall', max: 12 },
    1000072: { dir: 'defensive/spell-tower', prefix: 'Spell Tower', max: 4, variant: () => ' Rage' },
    1000077: { dir: 'defensive/monolith', prefix: 'Monolith', max: 5 },
    1000079: { dir: 'defensive/multi-gear-tower', prefix: 'Multi-Gear Tower', max: 3, variant: () => ' LongRange' },
    1000084: { dir: 'defensive/multi-archer-tower', prefix: 'Multi-Archer Tower', max: 4 },
    1000085: { dir: 'defensive/ricochet-cannon', prefix: 'Ricochet Cannon', max: 4 },
    1000086: { dir: 'defensive/revenge-tower', max: 2, file: level => `Revenge Tower${level} Dormant.png` },
    1000089: { dir: 'defensive/firespitter', prefix: 'Firespitter', max: 3 },
    1000093: { dir: 'other/helper-hut', file: 'Helper Hut.png' },
    1000097: { dir: 'defensive/crafting-station', file: 'Crafting Station.png' },
    1000102: {
      dir: 'defensive/super-wizard-tower',
      max: 5,
      file: level => `Super Wizard Tower${level}${level >= 3 ? 'C' : ''}.png`
    }
  });
  const cache = new Map();
  const listeners = new Set();
  let loaded = 0;
  let missing = 0;

  function notify() {
    const detail = {
      loaded,
      missing,
      pending: [...cache.values()].filter(item => item.state === 'loading').length
    };
    listeners.forEach(listener => listener(detail));
  }

  function request(url) {
    if (!url) return null;

    const known = cache.get(url);
    if (known) return known.state === 'ready' ? known.image : null;

    const item = {
      state: 'loading',
      image: new Image()
    };

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

  function buildingSourceUrl(id, level) {
    const spec = BUILDING_SOURCE[id];
    if (!spec) return null;
    const sourceLevel = Math.min(spec.max || level, Math.max(spec.min || 1, level));
    const file = typeof spec.file === 'function'
      ? spec.file(sourceLevel)
      : spec.file || `${spec.prefix}${sourceLevel}${spec.variant ? spec.variant(sourceLevel) : ''}.png`;
    return `${BUILDING_SOURCE_ROOT}/${spec.dir}/${file}`;
  }

  const api = {
    building(id, level) {
      const safeId = Number(id);
      const safeLevel = Math.max(1, Number(level) || 1);

      if (!Number.isFinite(safeId)) return null;

      return request(buildingSourceUrl(safeId, safeLevel));
    },

    buildingUrl(id, level) {
      const safeId = Number(id);
      const safeLevel = Math.max(1, Number(level) || 1);
      return Number.isFinite(safeId) ? buildingSourceUrl(safeId, safeLevel) : null;
    },

    wall(level) {
      return request(
        `${BUILDING_SOURCE_ROOT}/defensive/wall/Wall${Math.min(19, Math.max(1, Number(level) || 1))}.png`
      );
    },

    scenery(name) {
      const item = (window.SCENERY_CATALOG || [])
        .find(entry => entry.id === name);

      return request(
        `${ROOT}/scenery/${item?.file || `${name}.webp`}`
      );
    },

    sceneryInfo(name) {
      return (window.SCENERY_CATALOG || [])
        .find(entry => entry.id === name) || null;
    },

    sceneryCatalog: window.SCENERY_CATALOG || [],

    onStatus(listener) {
      listeners.add(listener);
      listener({
        loaded,
        missing,
        pending: 0
      });

      return () => listeners.delete(listener);
    },

    convention: {
      building: `${BUILDING_SOURCE_ROOT}/{category}/{building}/{name}{level}.png`,
      wall: `${BUILDING_SOURCE_ROOT}/defensive/wall/Wall{level}.png`,
      scenery: `${ROOT}/scenery/{name}.webp`
    }
  };

  window.GameAssetPack = api;

  /*
   * --------------------------------------------------------------------------
   * Skeleton Kingdom buildable-grid correction
   * --------------------------------------------------------------------------
   *
   * Penting:
   * Diamond ini adalah BATAS AREA BUILDABLE 44 x 44.
   * Batu/decor yang berada di luar diamond ini bukan bagian dari grid building.
   *
   * Koordinat diukur ulang berdasarkan batas merah pada screenshot
   * Skeleton Kingdom, lalu dinormalisasi terhadap seluruh image scenery.
   *
   * 0,0 ----------> 1,0
   *  |
   *  |
   *  v
   * 0,1
   */
  const SKELETON_BUILDABLE_GRID = Object.freeze({
    top: Object.freeze([
      0.50031327,
      0.25266061
    ]),

    right: Object.freeze([
      0.62441881,
      0.42490589
    ]),

    bottom: Object.freeze([
      0.50041759,
      0.59747215
    ]),

    left: Object.freeze([
      0.37642174,
      0.42530011
    ])
  });

  function cloneSkeletonGrid() {
    return {
      top: [...SKELETON_BUILDABLE_GRID.top],
      right: [...SKELETON_BUILDABLE_GRID.right],
      bottom: [...SKELETON_BUILDABLE_GRID.bottom],
      left: [...SKELETON_BUILDABLE_GRID.left]
    };
  }

  function installSkeletonGridCorrection() {
    /*
     * game-assets.js dipanggil SEBELUM script utama index.html.
     * Karena itu override dilakukan setelah seluruh HTML selesai diparse.
     */
    const apply = () => {
      /*
       * Expose untuk debug di DevTools:
       *
       *   SKELETON_KINGDOM_BUILDABLE_GRID
       */
      window.SKELETON_KINGDOM_BUILDABLE_GRID =
        cloneSkeletonGrid();

      /*
       * Catalog juga diperbaiki supaya sceneryInfo() memberi nilai benar.
       */
      const catalogItem = (window.SCENERY_CATALOG || [])
        .find(item => item.id === 'skeleton-kingdom');

      if (catalogItem) {
        catalogItem.grid = cloneSkeletonGrid();
      }

      /*
       * index.html versi sekarang punya fixed grid sendiri dan secara sengaja
       * mengabaikan localStorage untuk Skeleton Kingdom.
       *
       * Kita override dua fungsi global ini supaya fixed grid di index lama
       * tidak lagi dipakai.
       */
      if (
        typeof window.defaultGridForSelectedScenery === 'function'
      ) {
        window.defaultGridForSelectedScenery = function () {
          return cloneSkeletonGrid();
        };
      }

      if (
        typeof window.effectiveGridForSelectedScenery === 'function'
      ) {
        window.effectiveGridForSelectedScenery = function () {
          return cloneSkeletonGrid();
        };
      }

      /*
       * Pastikan coordinate system tetap 44 x 44.
       * 44 tile = titik boundary 0..44 pada tiap axis.
       */
      const gridW = document.getElementById('gridW');
      const gridH = document.getElementById('gridH');

      if (gridW) {
        gridW.value = '44';
        gridW.min = '44';
        gridW.max = '44';
      }

      if (gridH) {
        gridH.value = '44';
        gridH.min = '44';
        gridH.max = '44';
      }

      /*
       * Hapus calibration lama untuk Skeleton Kingdom jika pernah tersimpan.
       * Sebenarnya effectiveGridForSelectedScenery di atas sudah mengabaikannya,
       * tapi ini mencegah data lama membingungkan nanti.
       */
      try {
        const storageKey = 'coc-scenery-calibrations-v1';
        const saved = JSON.parse(
          localStorage.getItem(storageKey) || '{}'
        );

        if (
          saved &&
          Object.prototype.hasOwnProperty.call(
            saved,
            'skeleton-kingdom'
          )
        ) {
          delete saved['skeleton-kingdom'];
          localStorage.setItem(
            storageKey,
            JSON.stringify(saved)
          );
        }
      } catch (error) {
        console.warn(
          '[Skeleton Kingdom] calibration lama tidak bisa dibersihkan:',
          error
        );
      }

      /*
       * Redraw setelah override.
       * Delay 1 frame memastikan sceneryFrame dibuat dari grid baru.
       */
      requestAnimationFrame(() => {
        try {
          if (typeof window.render === 'function') {
            window.render();
          } else if (
            typeof window.drawCanvas === 'function'
          ) {
            window.drawCanvas();
          }
        } catch (error) {
          console.warn(
            '[Skeleton Kingdom] redraw gagal:',
            error
          );
        }
      });

      console.info(
        '[Skeleton Kingdom] buildable 44x44 grid correction active',
        cloneSkeletonGrid()
      );
    };

    if (document.readyState === 'loading') {
      document.addEventListener(
        'DOMContentLoaded',
        apply,
        { once: true }
      );
    } else {
      apply();
    }
  }

  installSkeletonGridCorrection();
})();
