(function () {
    const cfg = window.EXERCISE_SAVE_CONFIG || {};
    const favoriteBtn = document.getElementById('favoriteBtn');
    const icon = document.getElementById('favoriteIcon');

    const backdrop = document.getElementById('saveSheetBackdrop');
    const sheet = document.getElementById('saveSheet');
    const existingWrap = document.getElementById('existingCollectionsWrap');
    const listEl = document.getElementById('collectionsList');

    function openSheet() {
        backdrop?.classList.add('active');
        sheet?.classList.add('active');
    }

    function closeSheet() {
        backdrop?.classList.remove('active');
        sheet?.classList.remove('active');
        existingWrap.style.display = 'none';
    }

    function setFavUi(isFav) {
        if (!icon || !favoriteBtn) return;
        icon.textContent = isFav ? '★' : '☆';
        favoriteBtn.classList.toggle('favorited', isFav);
    }

    async function quickSave() {
        const res = await fetch(cfg.toggleFavoriteUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': cfg.csrfToken,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({})
        });
        const data = await res.json();
        if (data.status === 'added') setFavUi(true);
        if (data.status === 'removed') setFavUi(false);
    }

    async function loadCollections() {
        listEl.innerHTML = '';
        const res = await fetch(cfg.collectionsApiUrl, {headers: {'Accept': 'application/json'}});
        const collections = await res.json();

        if (!Array.isArray(collections) || !collections.length) {
            listEl.innerHTML = `<div style="opacity:.7;padding:8px;">${cfg.strings.noCollections}</div>`;
            return;
        }

        collections.forEach((c) => {
            const btn = document.createElement('button');
            btn.className = 'collection-item-btn';
            btn.textContent = `${c.name} (${c.exercise_count || 0})`;
            btn.addEventListener('click', async () => {
                const endpoint = cfg.favoriteToggleBaseUrl.replace('{collection_id}', c.id);
                const body = new FormData();
                body.append('exercise_id', cfg.exerciseId);
                const resp = await fetch(endpoint, {
                    method: 'POST',
                    headers: {'X-CSRFToken': cfg.csrfToken},
                    body
                });
                const data = await resp.json();
                if (data.success) {
                    alert(cfg.strings.savedToCollection);
                    setFavUi(true);
                    closeSheet();
                }
            });
            listEl.appendChild(btn);
        });
    }

    async function createCollection() {
        const nameInput = document.getElementById('newCollectionName');
        const name = nameInput.value.trim();
        if (!name) {
            alert(cfg.strings.enterCollectionName);
            return;
        }
        const fd = new FormData();
        fd.append('name', name);
        fd.append('exercise_ids[]', cfg.exerciseId);

        const res = await fetch(cfg.createCollectionUrl, {
            method: 'POST',
            headers: {'X-CSRFToken': cfg.csrfToken},
            body: fd
        });
        const data = await res.json();
        if (res.ok && data.success) {
            alert(cfg.strings.collectionCreated);
            nameInput.value = '';
            closeSheet();
            setFavUi(true);
        } else {
            alert(data.error || cfg.strings.error);
        }
    }

    favoriteBtn?.addEventListener('click', openSheet);
    document.getElementById('sheetCloseBtn')?.addEventListener('click', closeSheet);
    backdrop?.addEventListener('click', closeSheet);
    document.getElementById('quickSaveBtn')?.addEventListener('click', quickSave);
    document.getElementById('existingCollectionBtn')?.addEventListener('click', async () => {
        existingWrap.style.display = 'block';
        await loadCollections();
    });
    document.getElementById('newCollectionBtn')?.addEventListener('click', () => {
        document.getElementById('newCollectionBlock').style.display = 'block';
    });
    document.getElementById('createCollectionFromDetailBtn')?.addEventListener('click', createCollection);
})();
