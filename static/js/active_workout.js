// Backend ma'lumotlar
const workoutId = window.ACTIVE_WORKOUT_CONFIG.workoutPk;
const totalExercises = window.ACTIVE_WORKOUT_CONFIG.totalExercises;
const csrfToken = window.ACTIVE_WORKOUT_CONFIG.csrfToken;
const exercises = window.ACTIVE_WORKOUT_CONFIG.exercises;
const initialExerciseIndex = window.ACTIVE_WORKOUT_CONFIG.initialExerciseIndex;
const initialSet = window.ACTIVE_WORKOUT_CONFIG.initialSet;
const initialCompleted = window.ACTIVE_WORKOUT_CONFIG.initialCompleted;
const currentPath = window.location.pathname || '';
const isCustomProgramFlow = /\/favorites\/programs\/\d+\/start\/?$/.test(currentPath);

if (isCustomProgramFlow) {
    WORKOUT_URLS.complete = currentPath.replace(/\/start\/?$/, '/complete/');
    WORKOUT_URLS.start = currentPath;
}

// TO'G'RILANGAN TIMER LOGIKASI
let currentExerciseIndex = initialExerciseIndex;
let currentSet = initialSet;
let isPaused = false;
let isResting = false;
let timerInterval = null;
let restInterval = null;
let restTimeLeft = 0;

// YANGI: Umumiy trenirovka vaqti uchun
let sessionStartTime = null;  // Trenirovka boshlangan vaqt
let totalPausedTime = 0;      // Umumiy pause qilingan vaqt (millisekunda)
let pauseStartTime = null;    // Pause boshlangan vaqt

let totalCaloriesBurned = 0;
let totalDurationSeconds = 0;
let totalExercisesCompleted = initialCompleted;

// Yordamchi funksiyalar
const formatTime = (s) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
};

// YANGI: Haqiqiy o'tgan vaqtni hisoblash (pause vaqtini hisobga olgan holda)
const getElapsedSeconds = () => {
    if (!sessionStartTime) return 0;

    const now = Date.now();
    let totalElapsed = now - sessionStartTime;

    // Agar hozir pause holatida bo'lsa
    if (isPaused && pauseStartTime) {
        totalElapsed -= (now - pauseStartTime);
    }

    // Umumiy pause vaqtini ayirish
    totalElapsed -= totalPausedTime;

    return Math.floor(totalElapsed / 1000);
};

const updateExitButtonState = () => {
    const btn = document.getElementById("saveExitBtn");
    if (!btn) return;

    const disabled = totalExercisesCompleted < 1;

    btn.disabled = disabled;
    btn.style.opacity = disabled ? "0.5" : "1";
    btn.style.cursor = disabled ? "not-allowed" : "pointer";
};

const toggleExerciseDescription = (event) => {
    event.stopPropagation();
    const card = document.getElementById('exerciseDescriptionCard');
    const hint = document.getElementById('exerciseDescriptionHint');
    const isExpanded = card.classList.toggle('expanded');
    hint.textContent = isExpanded ? 'Tap to collapse' : 'Tap to expand';
};

const renderExerciseDescription = (description) => {
    const card = document.getElementById('exerciseDescriptionCard');
    const text = document.getElementById('exerciseDescription');
    const hint = document.getElementById('exerciseDescriptionHint');
    const safeDescription = (description || '').trim();

    if (!safeDescription) {
        card.style.display = 'none';
        card.classList.remove('expanded');
        return;
    }

    text.textContent = safeDescription;
    card.style.display = 'block';
    card.classList.remove('expanded');
    hint.textContent = 'Tap to expand';
};

const toggleExerciseMedia = () => {
    const video = document.getElementById('exerciseVideo');
    const image = document.getElementById('exerciseImage');
    const hint = document.getElementById('playVideoHint');

    if (!video.src) return;

    if (!video.classList.contains('active')) {
        video.classList.add('active');
        image.style.display = 'none';
        hint.style.display = 'none';
        video.play().catch(() => {
        });
    }
};

const resetExerciseMedia = (ex) => {
    const video = document.getElementById('exerciseVideo');
    const image = document.getElementById('exerciseImage');
    const hint = document.getElementById('playVideoHint');

    video.pause();
    video.currentTime = 0;
    video.classList.remove('active');
    image.style.display = 'block';

    if (ex.video) {
        video.src = ex.video;
        hint.style.display = 'block';
    } else {
        video.removeAttribute('src');
        video.load();
        hint.style.display = 'none';
    }
};

// === Asosiy: Mashqni yuklash ===
const loadExercise = (index, startingSet = 1) => {
    if (index >= exercises.length) return finishWorkout();

    const ex = exercises[index];
    currentExerciseIndex = index;
    currentSet = startingSet;
    isResting = false;
    isPaused = false;

    // UI yangilash
    document.getElementById('current').textContent = index + 1;
    document.getElementById('exerciseName').textContent = ex.name;
    document.getElementById('exerciseImage').src = ex.image || window.ACTIVE_WORKOUT_CONFIG.defaultExerciseImage;
    resetExerciseMedia(ex);
    renderExerciseDescription(ex.description);

    // Tugmalar
    const didBtn = document.getElementById('didItBtn');
    didBtn.classList.remove('completed');
    didBtn.disabled = false;
    didBtn.style.display = 'inline-flex';
    didBtn.textContent = ex.type === 'cardio' ? 'Did it' : 'Set Done';

    const pauseBtn = document.getElementById('pauseBtn');
    pauseBtn.style.display = 'inline-flex';
    document.getElementById('pauseIcon').innerHTML = '<i class="fas fa-pause"></i>';

    // Set details (faqat strength)
    if (ex.type === 'strength') {
        document.getElementById('strengthDetails').style.display = 'flex';
        document.getElementById('totalSets').textContent = ex.sets;
        document.getElementById('repsCount').textContent = ex.reps;
        document.getElementById('currentSet').textContent = currentSet;
    } else {
        document.getElementById('strengthDetails').style.display = 'none';
    }

    // Trenirovka faqat birinchi marta boshlanganda
    if (sessionStartTime === null) {
        sessionStartTime = Date.now();
        startSessionTimer();
    }

    showUpNext(index);
};

// TO'G'RILANGAN TIMER
const startSessionTimer = () => {
    clearInterval(timerInterval);
    timerInterval = setInterval(() => {
        // Pause yoki rest paytida timer to'xtaydi
        if (!isPaused && !isResting) {
            const elapsedSec = getElapsedSeconds();
            document.getElementById('floatingTimer').textContent = formatTime(elapsedSec);
        }
    }, 100);
};

// TO'G'RILANGAN PAUSE
const togglePause = () => {
    if (isResting) return;

    if (!isPaused) {
        // Pause boshlash
        isPaused = true;
        pauseStartTime = Date.now();
        document.getElementById('pauseIcon').innerHTML = '<i class="fas fa-play"></i>';
    } else {
        // Pause tugashi
        isPaused = false;
        if (pauseStartTime) {
            totalPausedTime += (Date.now() - pauseStartTime);
            pauseStartTime = null;
        }
        document.getElementById('pauseIcon').innerHTML = '<i class="fas fa-pause"></i>';
    }
};

// === Mashqni tugatish (Set Done yoki Did it) ===
const completeExercise = (auto = false) => {
    const ex = exercises[currentExerciseIndex];
    const btn = document.getElementById('didItBtn');
    btn.disabled = true;
    updateExitButtonState();

    // Kaloriya hisoblash
    if (ex.type === 'cardio') {
        totalCaloriesBurned += ex.calories_per_minute * ex.duration_minutes;
    } else if (ex.type === 'strength' && currentSet >= ex.sets) {
        totalCaloriesBurned += ex.calories_per_minute * ex.duration_minutes;
    }

    if (ex.type === 'strength' && currentSet < ex.sets) {
        totalExercisesCompleted += 1;
        startRest(ex.rest_seconds, currentSet, ex.sets);
        currentSet++;
        return;
    }

    // Oxirgi set yoki cardio
    totalExercisesCompleted += 1;
    btn.classList.add('completed');
    btn.innerHTML = '✅ Done';
    setTimeout(() => loadExercise(currentExerciseIndex + 1), 800);
};

// === Rest boshlash ===
const startRest = (restSec, completedSet, totalSets) => {
    isResting = true;

    // Floating timer yashirish
    document.getElementById('floatingTimer').classList.add('hidden');

    // Tugmalar yashiriladi
    document.getElementById('didItBtn').style.display = 'none';
    document.getElementById('pauseBtn').style.display = 'none';

    // UI
    document.getElementById('setCompleteBadge').textContent = `Set ${completedSet} Complete ✅`;
    const ex = exercises[currentExerciseIndex];
    const nextText = ex.type === 'strength'
        ? `Set ${currentSet + 1}/${ex.sets}`
        : (exercises[currentExerciseIndex + 1]?.name || "Workout Complete");
    document.getElementById('restUpNextName').textContent = nextText;

    document.getElementById('restOverlay').classList.add('active');
    restTimeLeft = restSec;
    document.getElementById('restTimer').textContent = formatTime(restTimeLeft);

    clearInterval(restInterval);
    restInterval = setInterval(() => {
        restTimeLeft--;
        document.getElementById('restTimer').textContent = formatTime(restTimeLeft);
        if (restTimeLeft <= 0) skipRest();
    }, 1000);
};

// === Restni o'tkazib yuborish ===
const skipRest = () => {
    isResting = false;
    clearInterval(restInterval);
    document.getElementById('restOverlay').classList.remove('active');

    // Floating timer ko'rsatish
    document.getElementById('floatingTimer').classList.remove('hidden');

    // Tugmalar qayta paydo bo'ladi
    const didBtn = document.getElementById('didItBtn');
    didBtn.style.display = 'inline-flex';
    didBtn.disabled = false;
    didBtn.classList.remove('completed');

    const pauseBtn = document.getElementById('pauseBtn');
    pauseBtn.style.display = 'inline-flex';
    document.getElementById('pauseIcon').innerHTML = '<i class="fas fa-pause"></i>';

    const ex = exercises[currentExerciseIndex];
    if (ex.type === 'strength' && currentSet <= ex.sets) {
        document.getElementById('currentSet').textContent = currentSet;
    } else {
        loadExercise(currentExerciseIndex + 1);
    }
};

// === Up Next ko'rsatish ===
const showUpNext = (index) => {
    const upNext = document.getElementById('upNext');
    const ex = exercises[index];

    if (ex.type === 'strength' && currentSet < ex.sets) {
        upNext.style.display = 'flex';
        document.getElementById('upNextImage').src = ex.image || window.ACTIVE_WORKOUT_CONFIG.defaultExerciseImage;
        document.getElementById('upNextName').textContent = ex.name;
        document.getElementById('upNextDetails').textContent = `Next: Set ${currentSet + 1}/${ex.sets}`;
        return;
    }

    if (index < exercises.length - 1) {
        const next = exercises[index + 1];
        upNext.style.display = 'flex';
        document.getElementById('upNextImage').src = next.image || window.ACTIVE_WORKOUT_CONFIG.defaultExerciseImage;
        document.getElementById('upNextName').textContent = next.name;
        document.getElementById('upNextDetails').textContent = next.type === 'cardio'
            ? `${next.duration_minutes} min`
            : `${next.sets} sets × ${next.reps} reps`;
    } else {
        upNext.style.display = 'none';
    }
};

// === Exit modal ===
const showExitModal = () => {
    document.getElementById('exitModal').classList.add('active');
    if (!isPaused && !isResting) togglePause();
};

const returnToWorkout = () => {
    document.getElementById('exitModal').classList.remove('active');
    if (isPaused && !isResting) togglePause();
};

const createForm = (save, action) => {
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = action === 'complete'
        ? WORKOUT_URLS.complete
        : WORKOUT_URLS.start;
    totalDurationSeconds = getElapsedSeconds();

    const fields = {
        csrfmiddlewaretoken: csrfToken,
        action: action,
        save_progress: save ? 'true' : 'false',
        total_duration: totalDurationSeconds,
        total_calories: totalCaloriesBurned.toFixed(2),
        exercises_completed: totalExercisesCompleted,
    };

    if (action === 'exit' && save) {
        fields.current_exercise_index = currentExerciseIndex;
        fields.current_set = currentSet;
    }

    Object.entries(fields).forEach(([name, value]) => {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = name;
        input.value = value;
        form.appendChild(input);
    });

    return form;
};

const finishWorkout = () => {
    document.body.appendChild(createForm(true, 'complete'));
    document.forms[document.forms.length - 1].submit();
};

const saveAndExit = () => {
    if (totalExercisesCompleted < 1) {
        return;
    }
    document.body.appendChild(createForm(true, 'exit'));
    document.forms[document.forms.length - 1].submit();
};

const exitWithoutSaving = () => {
    document.body.appendChild(createForm(false, 'exit'));
    document.forms[document.forms.length - 1].submit();
};

// === Ishga tushirish ===
document.addEventListener('DOMContentLoaded', () => {
    loadExercise(initialExerciseIndex, initialSet);
    updateExitButtonState();
});
