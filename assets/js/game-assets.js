(function () {
  'use strict';

  const ROOT = 'assets/game';
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

  const api = {
    building(id, level) {
      const safeId = Number(id);
      const safeLevel = Math.max(1, Number(level) || 1);

      if (!Number.isFinite(safeId)) return null;

      return request(
        `${ROOT}/buildings/${safeId}/level-${safeLevel}.webp`
      );
    },

    wall(level) {
      return request(
        `${ROOT}/walls/level-${Math.max(1, Number(level) || 1)}.webp`
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
      building: `${ROOT}/buildings/{building-id}/level-{level}.webp`,
      wall: `${ROOT}/walls/level-{level}.webp`,
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
