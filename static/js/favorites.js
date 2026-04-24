        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
let currentEditingCollectionId = null;

// Get current language from URL
function getCurrentLanguage() {
    const path = window.location.pathname;
    const match = path.match(/^\/(en|ru|uz)\//);
    return match ? match[1] : 'en';
}

const LANG = getCurrentLanguage();

// TAB SWITCHING
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', function () {
        const tabName = this.dataset.tab;
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        this.classList.add('active');

        document.getElementById('programsContainer').style.display = 'none';
        document.getElementById('favoritesList').style.display = 'none';
        document.getElementById('collectionsContainer').style.display = 'none';
        document.getElementById('editionsContainer').style.display = 'none';

        if (tabName === 'programs') {
            document.getElementById('programsContainer').style.display = 'flex';
        } else if (tabName === 'exercise') {
            document.getElementById('favoritesList').style.display = 'flex';
        } else if (tabName === 'collections') {
            document.getElementById('collectionsContainer').style.display = 'flex';
        } else if (tabName === 'editions') {
            document.getElementById('editionsContainer').style.display = 'flex';
        }
    });
});

// PROGRAM FILTERING
function filterProgramCards() {
    const goalValue = document.getElementById('goalFilter').value;
    const collectionValue = document.getElementById('collectionFilter').value;

    document.querySelectorAll('#programCardsWrap .program-card').forEach(card => {
        const goalOk = !goalValue || card.dataset.goal === goalValue;
        const collectionOk = !collectionValue || card.dataset.collectionId === collectionValue;
        card.style.display = (goalOk && collectionOk) ? 'block' : 'none';
    });
}

document.getElementById('goalFilter')?.addEventListener('change', filterProgramCards);
document.getElementById('collectionFilter')?.addEventListener('change', filterProgramCards);

// PROGRAM CREATE MODAL
function openProgramModal() {
    document.getElementById('programModal').classList.add('active');
}

function closeProgramModal() {
    document.getElementById('programModal').classList.remove('active');
}

document.getElementById('openProgramModalBtn')?.addEventListener('click', openProgramModal);
document.getElementById('closeProgramModalBtn')?.addEventListener('click', closeProgramModal);
document.getElementById('cancelProgramBtn')?.addEventListener('click', closeProgramModal);

document.getElementById('createProgramBtn')?.addEventListener('click', async () => {
    const name = document.getElementById('programName').value.trim();
    const goal = document.getElementById('programGoal').value;
    const collectionId = document.getElementById('programCollection').value;

    if (!name) {
        alert(window.FAVORITES_CONFIG.strings.enterProgramName);
        return;
    }

    const formData = new FormData();
    formData.append('name', name);
    formData.append('goal', goal);
    formData.append('collection_id', collectionId);

    const response = await fetch(`/${LANG}/favorites/programs/create/`, {
        method: 'POST',
        headers: {'X-CSRFToken': csrfToken},
        body: formData
    });

    const data = await response.json();
    if (!response.ok || !data.success) {
        alert(data.error || window.FAVORITES_CONFIG.strings.failedCreateProgram);
        return;
    }

    const wrap = document.getElementById('programCardsWrap');
    const card = document.createElement('div');
    card.className = 'program-card';
    card.dataset.goal = data.program.goal;
    card.dataset.collectionId = String(data.program.collection_id || '');
    card.innerHTML = `
        <h4>${data.program.name}</h4>
        <div>🎯 ${data.program.goal_display}</div>
        <div>🏋️ ${window.FAVORITES_CONFIG.strings.totalExercises}: ${data.program.total_exercises}</div>
        <div>📅 ${window.FAVORITES_CONFIG.strings.estimatedWeeks}: ${data.program.weeks}</div>
        <button class="start-program-btn" data-start-url="/${LANG}/favorites/programs/${data.program.id}/start/">${window.FAVORITES_CONFIG.strings.startWorkout}</button>
    `;
    wrap.prepend(card);
    closeProgramModal();
    bindStartProgramButtons();
    filterProgramCards();
});

function bindStartProgramButtons() {
    document.querySelectorAll('.start-program-btn').forEach(btn => {
        btn.onclick = function () {
            window.location.href = this.dataset.startUrl;
        };
    });
}
bindStartProgramButtons();

// OPEN CREATE MODAL
document.getElementById('addCollectionBtn').addEventListener('click', function () {
    document.getElementById('collectionModal').classList.add('active');
    document.getElementById('collectionName').value = '';
    document.querySelectorAll('#exerciseSelectList .exercise-select-item').forEach(item => {
        item.classList.remove('selected');
    });
});

// CLOSE CREATE MODAL
function closeCollectionModal() {
    document.getElementById('collectionModal').classList.remove('active');
}

document.getElementById('closeCollectionModalBtn').addEventListener('click', closeCollectionModal);
document.getElementById('cancelCollectionBtn').addEventListener('click', closeCollectionModal);

// EXERCISE SELECTION CREATE
document.querySelectorAll('#exerciseSelectList .exercise-select-item').forEach(item => {
    item.addEventListener('click', function () {
        this.classList.toggle('selected');
    });
});

// SAVE COLLECTION
document.getElementById('saveCollectionBtn').addEventListener('click', function () {
    const name = document.getElementById('collectionName').value.trim();
    if (!name) {
        alert('Iltimos, to\'plam nomini kiriting');
        return;
    }

    const selectedItems = document.querySelectorAll('#exerciseSelectList .exercise-select-item.selected');
    const exerciseIds = Array.from(selectedItems).map(i => i.dataset.exerciseId);

    const formData = new FormData();
    formData.append("name", name);
    exerciseIds.forEach(id => formData.append("exercise_ids[]", id));

    fetch(`/${LANG}/create/collection/`, {
        method: "POST",
        headers: {"X-CSRFToken": csrfToken},
        body: formData
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            closeCollectionModal();
            location.reload();
        } else {
            alert(data.error || 'Xatolik yuz berdi');
        }
    })
    .catch(err => {
        console.error(err);
        alert("Xatolik yuz berdi");
    });
});

// CLOSE EDIT MODAL
function closeEditModal() {
    document.getElementById('editModal').classList.remove('active');
    currentEditingCollectionId = null;
}

document.getElementById('closeEditModalBtn').addEventListener('click', closeEditModal);
document.getElementById('cancelEditBtn').addEventListener('click', closeEditModal);

// EXERCISE SELECTION EDIT
document.querySelectorAll('#editExerciseList .exercise-select-item').forEach(item => {
    item.addEventListener('click', function () {
        this.classList.toggle('selected');
    });
});

// EDIT COLLECTION
document.querySelectorAll('.edit-collection-btn').forEach(btn => {
    btn.addEventListener('click', function () {
        const collectionId = this.dataset.collectionId;
        currentEditingCollectionId = collectionId;
        document.getElementById('editModal').classList.add('active');

        fetch(`/${LANG}/collection/update/${collectionId}/`, {
            method: 'POST',
            headers: {'X-CSRFToken': csrfToken, 'Accept': 'application/json'}
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                document.getElementById('editCollectionName').value = data.name;
                document.querySelectorAll('#editExerciseList .exercise-select-item').forEach(item => {
                    item.classList.remove('selected');
                });
                const exerciseIds = new Set(data.exercise_ids.map(String));
                document.querySelectorAll('#editExerciseList .exercise-select-item').forEach(item => {
                    if (exerciseIds.has(item.dataset.exerciseId)) {
                        item.classList.add('selected');
                    }
                });
            } else {
                alert('Ma\'lumotlarni yuklashda xatolik');
            }
        })
        .catch(err => {
            console.error(err);
            alert('Xatolik yuz berdi');
        });
    });
});

// UPDATE COLLECTION
document.getElementById('updateCollectionBtn').addEventListener('click', function () {
    if (!currentEditingCollectionId) {
        alert('To\'plam tanlanmagan');
        return;
    }

    const name = document.getElementById('editCollectionName').value.trim();
    if (!name) {
        alert('Iltimos, to\'plam nomini kiriting');
        return;
    }

    const selectedItems = document.querySelectorAll('#editExerciseList .exercise-select-item.selected');
    const selectedIds = Array.from(selectedItems).map(i => i.dataset.exerciseId);

    const formData = new FormData();
    formData.append("name", name);
    selectedIds.forEach(exId => formData.append("exercise_ids[]", exId));

    fetch(`/${LANG}/collection/update/${currentEditingCollectionId}/`, {
        method: "POST",
        headers: {"X-CSRFToken": csrfToken},
        body: formData
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            closeEditModal();
            location.reload();
        } else {
            alert(data.error || 'Yangilashda xatolik');
        }
    })
    .catch(err => {
        console.error(err);
        alert("Xatolik yuz berdi");
    });
});

// SETUP UNFAVORITE BUTTON
function setupUnfavoriteButton(btn) {
    btn.addEventListener('click', function (e) {
        e.stopPropagation();
        e.preventDefault();

        const exerciseId = this.dataset.exerciseId;
        if (!confirm('Sevimlilardan olib tashlaysizmi?')) return;

        fetch(`/${LANG}/exercises/favorite/toggle/${exerciseId}/`, {
            method: 'POST',
            headers: {'X-CSRFToken': csrfToken}
        })
        .then(() => {
            const item = this.closest('.favorite-item');
            item.style.animation = 'slideOutRight 0.5s forwards';
            setTimeout(() => {
                item.remove();
                updateFavoritesCount(-1);
            }, 500);
        })
        .catch(err => {
            console.error(err);
            alert('Olib tashlashda xatolik');
        });
    });
}

// INITIAL UNFAVORITE BUTTONS
document.querySelectorAll('.unfavorite-btn').forEach(btn => {
    setupUnfavoriteButton(btn);
});

// DELETE COLLECTION
document.querySelectorAll('.delete-collection-btn').forEach(btn => {
    btn.addEventListener('click', function () {
        const collectionId = this.dataset.collectionId;
        const collectionName = this.dataset.collectionName;

        if (!confirm(`"${collectionName}" to'plamini o'chirasizmi? Bu amalni bekor qilib bo'lmaydi.`)) return;

        fetch(`/${LANG}/collection/delete/${collectionId}/`, {
            method: 'POST',
            headers: {'X-CSRFToken': csrfToken}
        })
        .then(() => location.reload())
        .catch(err => {
            console.error(err);
            alert('O\'chirishda xatolik');
        });
    });
});

// UPDATE FAVORITES COUNT
function updateFavoritesCount(change) {
    const countEl = document.getElementById('total-favorites-count');
    if (countEl) {
        const currentCount = parseInt(countEl.textContent) || 0;
        countEl.textContent = Math.max(0, currentCount + change);
    }
}

// ADD EXERCISE TO FAVORITES LIST - REAL TIME
function addExerciseToFavoritesList(exerciseData) {
    console.log('✅ Adding exercise to list:', exerciseData);

    const favoritesList = document.getElementById('favoritesList');
    if (!favoritesList) {
        console.error('❌ Favorites list not found!');
        return;
    }

    // Remove empty state if exists
    const emptyState = favoritesList.querySelector('.empty-state');
    if (emptyState) {
        emptyState.remove();
    }

    // Create new favorite item
    const newItem = document.createElement('div');
    newItem.className = 'favorite-item';
    newItem.dataset.id = exerciseData.favorite_id || '';

    const thumbnailUrl = exerciseData.thumbnail || '/static/img/default-thumb.jpg';
    const exerciseUrl = `/${LANG}/exercises/detail/${exerciseData.exercise_id}/`;

    newItem.innerHTML = `
        <a href="${exerciseUrl}" class="item-link-wrapper">
            <img src="${thumbnailUrl}"
                 alt="${exerciseData.exercise_name}"
                 class="favorite-thumbnail"
                 onerror="this.src='/static/img/default-thumb.jpg'">
            <div class="favorite-info">
                <div class="favorite-title">${exerciseData.exercise_name}</div>
                <div class="favorite-meta">
                    <i class="fas fa-dumbbell"></i> ${exerciseData.body_part}
                </div>
                <div class="favorite-tags">
                    <span class="favorite-tag">${exerciseData.difficulty.toUpperCase()}</span>
                </div>
            </div>
        </a>
        <button class="unfavorite-btn" data-exercise-id="${exerciseData.exercise_id}">⭐</button>
    `;

    // Add to beginning of list with animation
    newItem.style.opacity = '0';
    newItem.style.transform = 'translateY(20px)';
    favoritesList.insertBefore(newItem, favoritesList.firstChild);

    // Trigger animation
    setTimeout(() => {
        newItem.style.transition = 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)';
        newItem.style.opacity = '1';
        newItem.style.transform = 'translateY(0)';
    }, 50);

    // Setup unfavorite button
    const unfavoriteBtn = newItem.querySelector('.unfavorite-btn');
    setupUnfavoriteButton(unfavoriteBtn);

    // Update count
    updateFavoritesCount(1);

    console.log('✅ Exercise added successfully!');
}

// REMOVE EXERCISE FROM COLLECTION - MAIN FUNCTION
function setupRemoveButton(btn) {
    btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();

        const url = this.dataset.url;
        const collectionId = this.dataset.collectionId;
        const exerciseId = this.dataset.exerciseId;

        console.log('🔴 Remove clicked:', {url, collectionId, exerciseId});

        if (!confirm("Mashqni to'plamdan olib tashlaysizmi?")) {
            return;
        }

        const exerciseItem = this.closest('.collection-exercise-item');

        // Send request
        fetch(url, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Accept': 'application/json'
            }
        })
        .then(response => {
            console.log('📡 Response status:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('📦 Server response:', data);

            if (data.success) {
                console.log('✅ Success! Processing...');

                // Step 1: Remove from collection with animation
                exerciseItem.style.transition = 'all 0.3s ease';
                exerciseItem.style.transform = 'scale(0.8)';
                exerciseItem.style.opacity = '0';

                setTimeout(() => {
                    exerciseItem.remove();

                    // Step 2: Update collection UI
                    updateCollectionUI(collectionId);

                    // Step 3: Add to favorites list
                    setTimeout(() => {
                        addExerciseToFavoritesList({
                            exercise_id: data.exercise_id,
                            exercise_name: data.exercise_name,
                            thumbnail: data.thumbnail,
                            body_part: data.body_part,
                            difficulty: data.difficulty,
                            favorite_id: data.favorite_id
                        });
                    }, 100);

                }, 300);

            } else {
                console.error('❌ Server returned error:', data.error);
                alert(data.error || "Olib tashlashda xatolik");
            }
        })
        .catch(err => {
            console.error('❌ Request failed:', err);
            alert("Xatolik yuz berdi. Qaytadan urinib ko'ring.");
        });
    });
}

// UPDATE COLLECTION UI AFTER REMOVAL
function updateCollectionUI(collectionId) {
    const collectionCard = document.querySelector(`.collection-card[data-collection-id="${collectionId}"]`);
    if (!collectionCard) return;

    const exercisesContainer = collectionCard.querySelector('.collection-exercises');
    const remainingExercises = exercisesContainer.querySelectorAll('.collection-exercise-item');

    // If no exercises left, show empty message
    if (remainingExercises.length === 0) {
        exercisesContainer.innerHTML = `
            <div style="grid-column: 1/-1; text-align: center; color: rgba(255,255,255,0.5); padding: 20px; font-size: 12px;">
                Bu to'plamda hali mashqlar yo'q
            </div>
        `;
    }

    // Update exercise count
    const countSpan = collectionCard.querySelector('.collection-meta span:first-child');
    if (countSpan) {
        const currentCount = parseInt(countSpan.textContent.match(/\d+/)?.[0] || '0');
        const newCount = Math.max(0, currentCount - 1);
        countSpan.innerHTML = `<i class="fas fa-dumbbell"></i> ${newCount} mashq`;
    }
}

// SETUP ALL REMOVE BUTTONS
document.querySelectorAll('.collection-remove-btn').forEach(btn => {
    setupRemoveButton(btn);
});

// ESC KEY TO CLOSE MODALS
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        if (document.getElementById('collectionModal').classList.contains('active')) {
            closeCollectionModal();
        }
        if (document.getElementById('editModal').classList.contains('active')) {
            closeEditModal();
        }
        if (document.getElementById('programModal').classList.contains('active')) {
            closeProgramModal();
        }
    }
});

// TOUCH FEEDBACK FOR MOBILE
document.querySelectorAll('.favorite-item, .collection-card, .edition-card').forEach(card => {
    card.addEventListener('touchstart', function () {
        this.style.transform = 'scale(0.98)';
    });
    card.addEventListener('touchend', function () {
        this.style.transform = '';
    });
});

// PURCHASE & START BUTTONS
document.querySelectorAll('.purchase-edition-btn').forEach(btn => {
    btn.addEventListener('click', function () {
        alert('Xarid funksiyasi tez orada!');
    });
});

document.querySelectorAll('.start-workout-btn:not(.purchase-edition-btn)').forEach(btn => {
    btn.addEventListener('click', function () {
        const editionId = this.dataset.editionId;
        window.location.href = `/${LANG}/editions/${editionId}/start/`;
    });
});

document.querySelectorAll('.view-details-btn').forEach(btn => {
    btn.addEventListener('click', function () {
        const editionId = this.dataset.editionId;
        window.location.href = `/${LANG}/editions/${editionId}/`;
    });
});

console.log('✅ Favorites page loaded! Language:', LANG);
    
