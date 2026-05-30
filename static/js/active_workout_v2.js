// ? CONFIG ?????????????????????????????????????????????????
const CFG              = window.ACTIVE_WORKOUT_CONFIG || {};
const exercises        = CFG.exercises        || [];
const csrfToken        = CFG.csrfToken        || '';
const initialExIdx     = CFG.initialExerciseIndex || 0;
const initialCompleted = CFG.initialCompleted || 0;
const exitRedirectUrl  = CFG.exitRedirectUrl  || '';
const defaultImage     = CFG.defaultExerciseImage || '';

// ? TRANSLATIONS ?????????????????????????????????????????????????????
const T = Object.assign({
    didIt:    'Did It',
    kg:       'KG',
    reps:     'REPS',
    setOf:    'SET',
    of:       'OF',
    set:      'Set',
    complete: 'Complete',
    pause:    'Pause',
    resume:   'Resume',
    next:     'NEXT',
    rest:     'Rest',
    tapToSkip:'Tap to skip',
    skipRest: 'Skip Rest',
    nextUp:   'Next Up',
    progress: 'PROGRESS',
    noDesc:   'No description available.',
}, CFG.translations || {});

try {
    const p = window.location.pathname;
    if (/\/favorites\/programs\/\d+\/start\/?$/.test(p)) {
        WORKOUT_URLS.complete = p.replace(/\/start\/?$/, '/complete/');
        WORKOUT_URLS.start = p;
    }
} catch(e) {}

// ? STATE ????????????????????????????????????????????????
let currentExIdx   = initialExIdx;
let isPaused       = false;
let isResting      = false;
let timerInterval  = null;
let restInterval   = null;
let restTimeLeft   = 0;
let sessionStart   = null;
let totalPaused    = 0;
let pauseStart     = null;
let totalCalories  = 0;
let totalSecs      = 0;
let totalCompleted = initialCompleted;
let totalWeight    = 0;

const setWeights = {};
const doneSets   = {};

// ? UTILS ????????????????????????????????????????????????
const toFin   = (v, fb=0) => { const n=Number(v); return isFinite(n)?n:fb; };
const fmtTime = s => `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;
const $       = id => document.getElementById(id);

const elapsed = () => {
    if (!sessionStart) return 0;
    let e = Date.now() - sessionStart;
    if (isPaused && pauseStart) e -= (Date.now() - pauseStart);
    e -= totalPaused;
    return Math.max(0, Math.floor(e/1000));
};

const getW  = (ei,si) => setWeights[ei]?.[si] !== undefined ? setWeights[ei][si] : toFin(exercises[ei]?.recommended_weight, 0);
const saveW = (ei,si,v) => { if(!setWeights[ei]) setWeights[ei]={}; setWeights[ei][si]=Math.max(0,toFin(v,0)); };
const isDone = (ei,si) => doneSets[ei]?.has(si) ?? false;
const markD  = (ei,si) => { if(!doneSets[ei]) doneSets[ei]=new Set(); doneSets[ei].add(si); };
const doneN  = ei => doneSets[ei]?.size ?? 0;

const updateExit = () => {
    const b=$('saveExitBtn'); if(!b) return;
    b.disabled=totalCompleted<1; b.style.opacity=totalCompleted<1?'0.5':'1';
};

// ?? PROGRESS SEGMENTS (har exercise = 1 segment, set soniga qarab to'ladi) ??
const buildSegments = () => {
    const wrap = $('progressSegments'); if (!wrap) return;
    wrap.innerHTML = '';
    const n = exercises.length || 1;
    for (let i = 0; i < n; i++) {
        const seg = document.createElement('div');
        seg.className = 'progress-segment';
        const fill = document.createElement('div');
        fill.className = 'progress-segment-fill';
        fill.id = 'segFill-' + i;
        seg.appendChild(fill);
        wrap.appendChild(seg);
    }
};

const updateSegments = () => {
    const n = exercises.length || 0;
    for (let i = 0; i < n; i++) {
        const fill = $('segFill-' + i); if (!fill) continue;
        if (i < currentExIdx) {
            fill.style.width = '100%';            // tugagan exercise'lar to'liq
        } else if (i === currentExIdx) {
            // joriy exercise - tugatilgan set soniga qarab to'ladi
            const ex = exercises[i];
            const totalSets = (ex && ex.sets) ? ex.sets : 1;
            const pct = totalSets > 0 ? (doneN(i) / totalSets) * 100 : 0;
            fill.style.width = pct + '%';
        } else {
            fill.style.width = '0%';
        }
    }
};

// ? MEDIA ????????????????????????????????????????????????
const resetMedia = ex => {
    const v=$('exerciseVideo'), img=$('exerciseImage'); if(!v||!img) return;
    v.pause(); v.currentTime=0;
    if (ex?.video) {
        v.src=ex.video; v.muted=true; v.autoplay=true; v.loop=true;
        v.setAttribute('playsinline',''); v.removeAttribute('controls');
        v.classList.add('active'); img.style.display='none';
        v.load(); v.play().catch(()=>{});
    } else {
        v.removeAttribute('src'); v.load(); v.classList.remove('active');
        img.src=ex?.image||defaultImage; img.style.display='block';
    }
};
const toggleExerciseMedia = () => { if(exercises[currentExIdx]?.description) openDescModal(); };

// ?? FULLSCREEN (vertikal to'liq ekran - gif/video formatini saqlaydi) ??
const toggleFullscreen = (e) => {
    if (e) { e.stopPropagation(); }
    const v = $('exerciseVideo');
    const img = $('exerciseImage');
    const wrap = $('mediaContainer');
    if (!wrap) return;

    const videoActive = v && v.classList.contains('active');
    const el = videoActive ? v : img;

    // 1) iOS native video fullscreen (gif/video formatini saqlaydi, loop/muted o'zgarmaydi)
    if (videoActive && typeof v.webkitEnterFullscreen === 'function') {
        try { v.webkitEnterFullscreen(); return; } catch (err) {}
    }

    // 2) Standart Fullscreen API (Android/desktop)
    const isFs = document.fullscreenElement || document.webkitFullscreenElement;
    if (!isFs) {
        const target = videoActive ? v : wrap;
        if (target.requestFullscreen) { target.requestFullscreen(); return; }
        if (target.webkitRequestFullscreen) { target.webkitRequestFullscreen(); return; }
        // 3) CSS fallback (iOS rasm / WebView) - vertikal to'liq ekran
        wrap.classList.toggle('css-fullscreen');
        document.body.classList.toggle('fs-lock');
    } else {
        if (document.exitFullscreen) document.exitFullscreen();
        else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
    }
};

// CSS fallback fullscreen'dan chiqish (tap qilganda)
document.addEventListener('click', (e) => {
    const fsEl = document.querySelector('.exercise-media-container.css-fullscreen');
    if (fsEl && !e.target.closest('.fullscreen-btn')) {
        fsEl.classList.remove('css-fullscreen');
        document.body.classList.remove('fs-lock');
    }
}, true);

// ? DESC MODAL ???????????????????????????????????????????
const renderDescTrigger = desc => {
    const preview = $('descPreview'); if (!preview) return;
    preview.textContent = (desc && desc.trim()) ? desc.trim() : T.noDesc;
};

const openDescModal = () => {
    const ex = exercises[currentExIdx]; if (!ex) return;
    const ov = $('descOverlay'); if (!ov) return;

    const tx = $('descModalText') || $('descText');
    if (tx) tx.textContent = ex.description || T.noDesc;

    const media = $('descMedia');
    if (media) {
        if (ex.video) {
            media.innerHTML = `<video autoplay loop muted playsinline style="width:100%;height:100%;object-fit:cover;display:block;"><source src="${ex.video}"></video>`;
            media.style.display = 'block';
        } else if (ex.image) {
            media.innerHTML = `<img src="${ex.image}" alt="" style="width:100%;height:100%;object-fit:cover;display:block;">`;
            media.style.display = 'block';
        } else {
            media.style.display = 'none';
        }
    }

    ov.classList.add('active');
    if (!isPaused && !isResting) { isPaused = true; pauseStart = Date.now(); }
};

const closeDescModal = () => {
    const ov = $('descOverlay');
    if (ov) ov.classList.remove('active');
    const video = document.querySelector('#descMedia video');
    if (video) video.pause();
    if (isPaused && pauseStart && !isResting) {
        isPaused = false; totalPaused += (Date.now() - pauseStart); pauseStart = null;
        const pi = $('pauseIcon'); if (pi) pi.innerHTML = '<i class="fas fa-pause"></i>';
    }
};

const closeDescModalOnBg = e => { if (e.target.id === 'descOverlay') closeDescModal(); };

// ?? NEXT UP ??
const updateNextUp = () => {
    const section = $('nextUpSection'); if (!section) return;
    const nextIdx = currentExIdx + 1;
    if (nextIdx >= exercises.length) {
        section.style.display = 'none';
        return;
    }
    const next = exercises[nextIdx];
    section.style.display = 'block';
    const nm = $('nextUpName'); if (nm) nm.textContent = next.name || '';

    // davomiylik / set ma'lumoti
    const dur = $('nextUpDur');
    if (dur) {
        const exType = (next.type || 'strength').toLowerCase();
        if (exType === 'strength' && next.sets) {
            dur.textContent = `${next.sets} ${T.setOf.toLowerCase()} × ${next.reps || ''} ${T.reps.toLowerCase()}`;
        } else if (next.duration_minutes) {
            dur.textContent = `${next.duration_minutes} min`;
        } else {
            dur.textContent = '';
        }
    }

    updateNextUpThumb(next.image);
};

const updateNextUpThumb = imageUrl => {
    const thumbEl = $('nextUpThumb'); if (!thumbEl) return;
    if (imageUrl) {
        thumbEl.outerHTML = `<img src="${imageUrl}" alt="" class="next-up-thumb" id="nextUpThumb">`;
    } else if (thumbEl.tagName === 'IMG') {
        thumbEl.outerHTML = `<div class="next-up-thumb-placeholder" id="nextUpThumb">?</div>`;
    }
};

const openNextupModal = () => {
    const nextIdx = currentExIdx + 1;
    if (nextIdx >= exercises.length) return;
    const ex = exercises[nextIdx];

    const nm = $('nextupModalName'); if (nm) nm.textContent = ex.name || '';
    const dur = $('nextupModalDur');
    if (dur) {
        const exType = (ex.type || 'strength').toLowerCase();
        if (exType === 'strength' && ex.sets) {
            dur.textContent = `${ex.sets} ${T.setOf.toLowerCase()} × ${ex.reps || ''} ${T.reps.toLowerCase()}`;
        } else if (ex.duration_minutes) {
            dur.textContent = `${ex.duration_minutes} min`;
        } else {
            dur.textContent = '';
        }
    }
    const desc = $('nextupModalDesc'); if (desc) desc.textContent = ex.description || T.noDesc;

    const media = $('nextupModalMedia');
    if (media) {
        if (ex.video) {
            media.innerHTML = `<video autoplay loop muted playsinline><source src="${ex.video}"></video>`;
        } else if (ex.image) {
            media.innerHTML = `<img src="${ex.image}" alt="">`;
        } else {
            media.innerHTML = `<div class="nextup-modal-placeholder">?</div>`;
        }
    }
    const ov = $('nextupOverlay'); if (ov) ov.classList.add('active');
};

const closeNextupModal = () => {
    const ov = $('nextupOverlay');
    if (ov) ov.classList.remove('active');
    const video = document.querySelector('#nextupModalMedia video');
    if (video) video.pause();
};

// ?? SET CARDS ???????????????????????????????????????????
const renderSetCards = () => {
    const ex=exercises[currentExIdx], wr=$('setsWrapper');
    const exType=(ex.type||'strength').toLowerCase(); if(!wr||!ex||exType!=='strength') return;
    wr.innerHTML='';

    for (let i=0; i<ex.sets; i++) {
        const done = isDone(currentExIdx, i);
        const w    = getW(currentExIdx, i);
        const wStr = w%1===0 ? String(w) : w.toFixed(1);
        const rStr = ex.reps_max && ex.reps_max!==ex.reps
            ? `${ex.reps}?${ex.reps_max}` : String(ex.reps);

        const lr = document.createElement('div');
        lr.className='set-label-row';
        lr.innerHTML=`
            <span class="set-label-text">${T.setOf} ${i+1} ${T.of} ${ex.sets}</span>
            <span class="set-label-done${done?' show':''}" id="dl_${currentExIdx}_${i}">? ${T.complete}</span>
        `;
        wr.appendChild(lr);

        const card = document.createElement('div');
        card.className=`set-card${done?' done':''}`;
        card.id=`sc_${currentExIdx}_${i}`;

        const wZone = document.createElement('div');
        wZone.className='set-weight-zone';

        if (!done) {
            const inp = document.createElement('input');
            inp.type='number';
            inp.className='w-inp';
            inp.id=`wi_${currentExIdx}_${i}`;
            inp.value=wStr;
            inp.step='0.5';
            inp.min='0';
            inp.setAttribute('inputmode','decimal');
            inp.setAttribute('pattern','[0-9.]*');

            const ei=currentExIdx, si=i;
            inp.addEventListener('input', () => {
                saveW(ei, si, parseFloat(inp.value)||0);
            });
            inp.addEventListener('blur', () => {
                const val=Math.max(0,parseFloat(inp.value)||0);
                saveW(ei,si,val);
                inp.value = val%1===0 ? String(val) : val.toFixed(1);
            });
            inp.addEventListener('focus', () => {
                setTimeout(()=>inp.select(), 50);
            });

            wZone.appendChild(inp);
        } else {
            const sp=document.createElement('span');
            sp.className='w-inp';
            sp.textContent=wStr;
            wZone.appendChild(sp);
        }

        const unitLbl=document.createElement('span');
        unitLbl.className='w-unit'; unitLbl.textContent=T.kg;
        wZone.appendChild(unitLbl);

        const div=document.createElement('div'); div.className='set-divider';

        const rZone=document.createElement('div'); rZone.className='set-reps-zone';
        rZone.innerHTML=`<span class="r-num">${rStr}</span><span class="r-lbl">${T.reps}</span>`;

        const diCell=document.createElement('div');
        diCell.className='did-it-cell';
        diCell.id=`di_${currentExIdx}_${i}`;
        diCell.textContent=done?'?':T.didIt;
        if(!done) {
            diCell.addEventListener('click', ()=>didItSet(i));
        }

        card.appendChild(wZone);
        card.appendChild(div);
        card.appendChild(rZone);
        card.appendChild(diCell);
        wr.appendChild(card);
    }
};

// ? DID IT ???????????????????????????????????????????????
const didItSet = si => {
    const ei = currentExIdx;

    for (let i = 0; i <= si; i++) {
        if (isDone(ei, i)) continue;

        const inp = $(`wi_${ei}_${i}`);
        if (inp && inp.tagName === 'INPUT') saveW(ei, i, parseFloat(inp.value) || 0);

        const w = getW(ei, i);
        const ex = exercises[ei];
        if (!ex) continue;

        totalWeight += w * ex.reps;
        totalCompleted += 1;
        markD(ei, i);
    }

    updateExit();
    updateSegments();

    const di = $(`di_${ei}_${si}`);
    if (di) {
        const r = document.createElement('span');
        r.className = 'ripple-c';
        const sz = Math.max(di.offsetWidth, di.offsetHeight);
        Object.assign(r.style, {
            width: sz + 'px', height: sz + 'px',
            left: (di.offsetWidth / 2 - sz / 2) + 'px',
            top: (di.offsetHeight / 2 - sz / 2) + 'px'
        });
        di.appendChild(r);
        setTimeout(() => r.remove(), 600);
    }

    setTimeout(() => {
        for (let i = 0; i <= si; i++) {
            const card = $(`sc_${ei}_${i}`);
            const dl = $(`dl_${ei}_${i}`);
            const diEl = $(`di_${ei}_${i}`);
            const inp = $(`wi_${ei}_${i}`);

            if (card) {
                card.classList.add('done', 'pulse');
                setTimeout(() => card.classList.remove('pulse'), 700);
            }
            if (dl) dl.classList.add('show');
            if (diEl) { diEl.textContent = '?'; diEl.style.pointerEvents = 'none'; }
            if (inp && inp.tagName === 'INPUT') {
                const val = getW(ei, i);
                const sp = document.createElement('span');
                sp.className = 'w-inp';
                sp.textContent = val % 1 === 0 ? String(val) : val.toFixed(1);
                inp.parentNode.replaceChild(sp, inp);
            }
        }
    }, 150);

    const dn = doneN(ei);
    const ex = exercises[ei];
    if (dn < ex.sets) {
        setTimeout(() => startRest(toFin(ex.rest_seconds, 60), si + 1, ex.sets, si + 2, ex), 400);
    } else {
        totalCalories += toFin(ex.calories_per_minute, 5) * toFin(ex.duration_minutes, 0);
        setTimeout(() => loadExercise(ei + 1), 500);
    }
};

// ? LOAD EXERCISE ????????????????????????????????????????
const loadExercise = idx => {
    if(idx>=exercises.length) { finishWorkout(); return; }
    const ex=exercises[idx]; if(!ex) { finishWorkout(); return; }

    currentExIdx=idx; isResting=false; isPaused=false;

    const cur=$('current'), nm=$('exerciseName'),
          pb=$('pauseBtn'), pi=$('pauseIcon'), pt=$('pauseText'), ft=$('floatingTimer');
    if(cur) cur.textContent=idx+1;
    if(nm)  nm.textContent=ex.name||'';
    if(pb)  pb.style.display='flex';
    if(pi)  pi.innerHTML='<i class="fas fa-pause"></i>';
    if(pt)  pt.textContent=T.pause;
    if(ft)  ft.classList.remove('hidden');

    resetMedia(ex);
    renderDescTrigger(ex.description);

    const wr=$('setsWrapper');
    if(wr) {
        const exType2=(ex.type||'strength').toLowerCase(); wr.style.display=exType2==='strength'?'flex':'none';
        if(exType2==='strength') renderSetCards();
    }

    updateSegments();
    updateNextUp();

    if(!sessionStart) { sessionStart=Date.now(); startTimer(); }
};

// ?? TIMER ????????????????????????????????????????????????
const startTimer=()=>{
    clearInterval(timerInterval);
    timerInterval=setInterval(()=>{
        if(!isPaused&&!isResting){
            const ft=$('floatingTimer'); if(ft) ft.textContent=fmtTime(elapsed());
        }
    },100);
};

// ?? PAUSE ????????????????????????????????????????????????
const togglePause=()=>{
    if(isResting) return;
    const pi=$('pauseIcon'), pt=$('pauseText');
    if(!isPaused){
        isPaused=true; pauseStart=Date.now();
        if(pi) pi.innerHTML='<i class="fas fa-play"></i>';
        if(pt) pt.textContent=T.resume;
    } else {
        isPaused=false;
        if(pauseStart){ totalPaused+=(Date.now()-pauseStart); pauseStart=null; }
        if(pi) pi.innerHTML='<i class="fas fa-pause"></i>';
        if(pt) pt.textContent=T.pause;
    }
};

// ? REST ????????????????????????????????????????????????? (next exercise olib tashlandi)
const startRest=(sec,completedN,totalSets,nextN,ex)=>{
    isResting=true;
    const ft=$('floatingTimer'), pb=$('pauseBtn');
    if(ft) ft.classList.add('hidden');
    if(pb) pb.style.display='none';

    const badge=$('restBadge'), rt=$('restTimer'), ov=$('restOverlay');
    if(badge) badge.textContent=`${T.set} ${completedN} ${T.complete}`;
    restTimeLeft=sec;
    if(rt) rt.textContent=fmtTime(restTimeLeft);
    if(ov) ov.classList.add('active');

    clearInterval(restInterval);
    restInterval=setInterval(()=>{
        restTimeLeft--;
        const r=$('restTimer'); if(r) r.textContent=fmtTime(Math.max(0,restTimeLeft));
        if(restTimeLeft<=0) skipRest();
    },1000);
};

const skipRest=()=>{
    isResting=false; clearInterval(restInterval);
    const ov=$('restOverlay'),ft=$('floatingTimer'),pb=$('pauseBtn'),pi=$('pauseIcon'),pt=$('pauseText');
    if(ov) ov.classList.remove('active');
    if(ft) ft.classList.remove('hidden');
    if(pb) pb.style.display='flex';
    if(pi) pi.innerHTML='<i class="fas fa-pause"></i>';
    if(pt) pt.textContent=T.pause;
};

// ? SKIP TO NEXT EXERCISE ????????????????????????????????
const skipToNextExercise = () => {
    const restOv = $('restOverlay');
    if (restOv && restOv.classList.contains('active')) {
        restOv.classList.remove('active');
        isResting = false;
        if (restInterval) { clearInterval(restInterval); restInterval = null; }
    }

    const ex = exercises[currentExIdx];
    if (!ex) return;

    for (let i = 0; i < ex.sets; i++) {
        if (!isDone(currentExIdx, i)) {
            const inp = $(`wi_${currentExIdx}_${i}`);
            if (inp && inp.tagName === 'INPUT') {
                saveW(currentExIdx, i, parseFloat(inp.value) || 0);
            }
            markD(currentExIdx, i);
            totalCompleted++;
        }
    }

    totalCalories += toFin(ex.calories_per_minute, 5) * toFin(ex.duration_minutes, 0);
    updateExit();
    updateSegments();

    if (currentExIdx + 1 < exercises.length) {
        loadExercise(currentExIdx + 1);
    } else {
        finishWorkout();
    }
};

// ? EXIT ?????????????????????????????????????????????????
const showExitModal=()=>{
    const m=$('exitModal'); if(m) m.classList.add('active');
    if(!isPaused&&!isResting) togglePause();
};
const returnToWorkout=()=>{
    const m=$('exitModal'); if(m) m.classList.remove('active');
    if(isPaused&&!isResting) togglePause();
};

const submitForm=action=>{
    totalSecs=elapsed();
    const form=document.createElement('form'); form.method='POST';
    const urls=typeof WORKOUT_URLS!=='undefined'?WORKOUT_URLS:{};
    if(action==='complete'){
        form.action=urls.complete||window.location.pathname;
    } else {
        if(exitRedirectUrl){ window.location.href=exitRedirectUrl; return; }
        form.action=urls.complete||window.location.pathname;
    }
    const fields={
        csrfmiddlewaretoken:csrfToken,action,save_progress:'true',
        total_duration:totalSecs,total_calories:totalCalories.toFixed(2),
        exercises_completed:totalCompleted,total_weight:totalWeight.toFixed(2),
    };
    if(action==='exit'){ fields.current_exercise_index=currentExIdx; fields.current_set=doneN(currentExIdx)+1; }
    Object.entries(fields).forEach(([n,v])=>{
        const i=document.createElement('input'); i.type='hidden'; i.name=n; i.value=v; form.appendChild(i);
    });
    document.body.appendChild(form); form.submit();
};

const finishWorkout    =()=>submitForm('complete');
const saveAndExit      =()=>{ if(totalCompleted<1) return; submitForm('exit'); };
const exitWithoutSaving=()=>exitRedirectUrl?(window.location.href=exitRedirectUrl):history.back();

const completeExercise=()=>{
    const ex=exercises[currentExIdx]; if(!ex||ex.type!=='cardio') return;
    totalCalories+=toFin(ex.calories_per_minute,5)*toFin(ex.duration_minutes,0);
    totalCompleted+=1; updateExit(); loadExercise(currentExIdx+1);
};

// ? INIT ?????????????????????????????????????????????????
document.addEventListener('click', (e) => {
    if (!e.target.closest('.set-weight-zone') && !e.target.classList.contains('w-inp')) {
        document.activeElement?.blur();
    }
});

document.addEventListener('DOMContentLoaded',()=>{
    buildSegments();
    loadExercise(initialExIdx);
    updateExit();
});

// ? WINDOW EXPORTS ???????????????????????????????????????
Object.assign(window, {
    closeDescModal,
    closeDescModalOnBg,
    closeNextupModal,
    completeExercise,
    exitWithoutSaving,
    openDescModal,
    openNextupModal,
    returnToWorkout,
    saveAndExit,
    showExitModal,
    skipRest,
    skipToNextExercise,
    toggleFullscreen,
    togglePause,
    toggleExerciseMedia,
});

console.log('? Active Workout v2 loaded. skipToNextExercise:', typeof window.skipToNextExercise);