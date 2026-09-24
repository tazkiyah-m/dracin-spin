const SEGMENTS = [
  { key: null,                name: "Zonk",              label: "ZONK",        color: "#FFFFFF", textColor: "#000000", isPrize: false },
  { key: "Palekko Chicken",   name: "Palekko Chicken",   line1: "PALEKKO",     line2: "CHICKEN", color: "#800020", textColor: "#FFFFFF", isPrize: true },
  { key: null,                name: "Zonk",              label: "ZONK",        color: "#161616", textColor: "#FFFFFF", isPrize: false },
  { key: null,                name: "Zonk",              label: "ZONK",        color: "#FFFFFF", textColor: "#000000", isPrize: false },
  { key: "Gacoan DNA",        name: "Gacoan DNA",        line1: "GACOAN",      line2: "DNA",     color: "#800020", textColor: "#FFFFFF", isPrize: true },
  { key: null,                name: "Zonk",              label: "ZONK",        color: "#161616", textColor: "#FFFFFF", isPrize: false },
  { key: null,                name: "Zonk",              label: "ZONK",        color: "#FFFFFF", textColor: "#000000", isPrize: false },
  { key: "Grass Jelly Drink", name: "Grass Jelly Drink", line1: "GRASS JELLY", line2: "DRINK",   color: "#800020", textColor: "#FFFFFF", isPrize: true },
  { key: null,                name: "Zonk",              label: "ZONK",        color: "#161616", textColor: "#FFFFFF", isPrize: false },
  { key: null,                name: "Zonk",              label: "ZONK",        color: "#FFFFFF", textColor: "#000000", isPrize: false },
];

const SLICE = 360 / SEGMENTS.length;

const wheelEl = document.getElementById("wheel");
const credit2kEl = document.getElementById("credit-2k");
const credit5kEl = document.getElementById("credit-5k");
const spinBtn2k = document.getElementById("spin-btn-2k");
const spinBtn5k = document.getElementById("spin-btn-5k");
const resultEl = document.getElementById("result");
const legendEl = document.getElementById("legend");
const historyListEl = document.getElementById("history-list");
const qrisContainer = document.getElementById("qris-container");
const confettiCanvas = document.getElementById("confetti-canvas");
const crackOverlay = document.getElementById("crack-overlay");

let currentRotation = 0;
let spinning = false;

// ===== WEB AUDIO API SOUND EFFECTS =====
let audioCtx = null;
function getAudioCtx() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  if (audioCtx.state === "suspended") audioCtx.resume();
  return audioCtx;
}

// Crisp mechanical wheel tick sound
let lastTickTime = 0;
function playTickSound(pitch = 1) {
  try {
    const ctx = getAudioCtx();
    const now = ctx.currentTime;
    if (now - lastTickTime < 0.028) return; // Prevent audio distortion when spinning super fast
    lastTickTime = now;

    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sine";
    const startFreq = (900 + Math.random() * 80) * pitch;
    osc.frequency.setValueAtTime(startFreq, now);
    osc.frequency.exponentialRampToValueAtTime(160, now + 0.022);

    gain.gain.setValueAtTime(0.08, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.022);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(now);
    osc.stop(now + 0.022);
  } catch(e) {}
}

// Cubic bezier solver matching CSS: cubic-bezier(0.12, 0.85, 0.15, 1)
function createBezierSolver(p1x, p1y, p2x, p2y) {
  const ax = 3 * p1x - 3 * p2x + 1;
  const bx = 3 * p2x - 6 * p1x;
  const cx = 3 * p1x;
  const ay = 3 * p1y - 3 * p2y + 1;
  const by = 3 * p2y - 6 * p1y;
  const cy = 3 * p1y;

  function sampleX(t) { return ((ax * t + bx) * t + cx) * t; }
  function sampleY(t) { return ((ay * t + by) * t + cy) * t; }
  function sampleDx(t) { return (3 * ax * t + 2 * bx) * t + cx; }

  return function(x) {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    let t = x;
    for (let i = 0; i < 8; i++) {
      const x2 = sampleX(t) - x;
      if (Math.abs(x2) < 1e-5) return sampleY(t);
      const d2 = sampleDx(t);
      if (Math.abs(d2) < 1e-5) break;
      t = t - x2 / d2;
      t = Math.max(0, Math.min(1, t));
    }
    return sampleY(t);
  };
}

const easeProgress = createBezierSolver(0.12, 0.85, 0.15, 1);

let spinRafId = null;

// Start physically synchronized sound ticker
function startSpinTicker(startAngle, targetAngle, durationMs = 4200) {
  stopSpinTicker();

  const totalDelta = targetAngle - startAngle;
  // Peg placed every 22.5 deg (16 pegs around the plate wheel)
  const pegStep = 22.5;
  let lastPeg = Math.floor(startAngle / pegStep);
  const startTime = performance.now();
  const pointerEl = document.querySelector(".pointer");
  if (pointerEl) pointerEl.classList.add("is-spinning");

  function tickLoop(currentTime) {
    const elapsed = currentTime - startTime;
    if (elapsed >= durationMs) {
      stopSpinTicker();
      return;
    }

    const t = Math.min(1, Math.max(0, elapsed / durationMs));
    const progress = easeProgress(t);
    const currentAngle = startAngle + progress * totalDelta;
    const currentPeg = Math.floor(currentAngle / pegStep);

    if (currentPeg > lastPeg) {
      // Sound pitch scales subtly with current speed factor
      const speedFactor = 1 - t;
      playTickSound(0.85 + speedFactor * 0.35);

      if (pointerEl) {
        pointerEl.style.transform = "translateX(-50%) rotate(-7deg)";
        setTimeout(() => {
          if (pointerEl && spinRafId !== null) {
            pointerEl.style.transform = "translateX(-50%) rotate(0deg)";
          }
        }, 30);
      }
      lastPeg = currentPeg;
    }

    spinRafId = requestAnimationFrame(tickLoop);
  }

  spinRafId = requestAnimationFrame(tickLoop);
}

function stopSpinTicker() {
  if (spinRafId !== null) {
    cancelAnimationFrame(spinRafId);
    spinRafId = null;
  }
  const pointerEl = document.querySelector(".pointer");
  if (pointerEl) {
    pointerEl.classList.remove("is-spinning");
    pointerEl.style.transform = "";
  }
}

function playWinFanfare() {
  try {
    const ctx = getAudioCtx();
    const notes = [523, 659, 784, 1047]; // C5 E5 G5 C6
    notes.forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "triangle";
      osc.frequency.setValueAtTime(freq, ctx.currentTime);
      gain.gain.setValueAtTime(0, ctx.currentTime + i * 0.15);
      gain.gain.linearRampToValueAtTime(0.15, ctx.currentTime + i * 0.15 + 0.05);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.15 + 0.5);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(ctx.currentTime + i * 0.15);
      osc.stop(ctx.currentTime + i * 0.15 + 0.5);
    });
    // Shimmer 
    setTimeout(() => {
      for (let i = 0; i < 3; i++) {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = "sine";
        osc.frequency.setValueAtTime(2000 + i * 500, ctx.currentTime);
        gain.gain.setValueAtTime(0.04, ctx.currentTime + i * 0.1);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.1 + 0.3);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(ctx.currentTime + i * 0.1);
        osc.stop(ctx.currentTime + i * 0.1 + 0.3);
      }
    }, 600);
  } catch(e) {}
}

function playZonkExplosion() {
  try {
    const ctx = getAudioCtx();
    // Explosion noise burst
    const bufferSize = ctx.sampleRate * 0.8;
    const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < bufferSize; i++) {
      data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / bufferSize, 2.5);
    }
    const noise = ctx.createBufferSource();
    noise.buffer = buffer;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0.35, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.8);
    // Low rumble
    const filter = ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.setValueAtTime(400, ctx.currentTime);
    filter.frequency.exponentialRampToValueAtTime(60, ctx.currentTime + 0.8);
    noise.connect(filter);
    filter.connect(gain);
    gain.connect(ctx.destination);
    noise.start(ctx.currentTime);
    noise.stop(ctx.currentTime + 0.8);
    
    // Impact thud
    const osc = ctx.createOscillator();
    const oscGain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(80, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(20, ctx.currentTime + 0.5);
    oscGain.gain.setValueAtTime(0.4, ctx.currentTime);
    oscGain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);
    osc.connect(oscGain);
    oscGain.connect(ctx.destination);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.5);
  } catch(e) {}
}

// ===== CONFETTI CELEBRATION SYSTEM =====
let confettiParticles = [];
let confettiAnimId = null;

function launchConfetti() {
  const canvas = confettiCanvas;
  if (!canvas) return;
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  canvas.style.display = "block";
  const ctx = canvas.getContext("2d");
  confettiParticles = [];

  const COLORS = ["#800020", "#FFFFFF", "#000000", "#FF4070", "#FFD700", "#FF6B6B"];
  const SHAPES = ["rect", "circle", "star"];

  for (let i = 0; i < 150; i++) {
    confettiParticles.push({
      x: Math.random() * canvas.width,
      y: canvas.height + Math.random() * 200,
      vx: (Math.random() - 0.5) * 8,
      vy: -(Math.random() * 14 + 8),
      size: Math.random() * 10 + 5,
      color: COLORS[Math.floor(Math.random() * COLORS.length)],
      shape: SHAPES[Math.floor(Math.random() * SHAPES.length)],
      rotation: Math.random() * 360,
      rotSpeed: (Math.random() - 0.5) * 12,
      gravity: 0.12 + Math.random() * 0.08,
      opacity: 1,
    });
  }

  function drawStar(ctx, cx, cy, r, rot) {
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate((rot * Math.PI) / 180);
    ctx.beginPath();
    for (let i = 0; i < 5; i++) {
      const angle = (i * 72 - 90) * Math.PI / 180;
      const innerAngle = ((i * 72) + 36 - 90) * Math.PI / 180;
      ctx.lineTo(Math.cos(angle) * r, Math.sin(angle) * r);
      ctx.lineTo(Math.cos(innerAngle) * r * 0.4, Math.sin(innerAngle) * r * 0.4);
    }
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }

  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    let alive = 0;
    confettiParticles.forEach(p => {
      p.vy += p.gravity;
      p.x += p.vx;
      p.y += p.vy;
      p.rotation += p.rotSpeed;
      if (p.y > canvas.height + 50) p.opacity -= 0.05;
      if (p.opacity <= 0) return;
      alive++;

      ctx.globalAlpha = p.opacity;
      ctx.fillStyle = p.color;
      ctx.strokeStyle = "#000000";
      ctx.lineWidth = 1.5;

      if (p.shape === "rect") {
        ctx.save();
        ctx.translate(p.x, p.y);
        ctx.rotate((p.rotation * Math.PI) / 180);
        ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
        ctx.strokeRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
        ctx.restore();
      } else if (p.shape === "circle") {
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size / 2, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      } else {
        drawStar(ctx, p.x, p.y, p.size / 2, p.rotation);
      }
    });
    ctx.globalAlpha = 1;

    if (alive > 0) {
      confettiAnimId = requestAnimationFrame(animate);
    } else {
      canvas.style.display = "none";
      confettiAnimId = null;
    }
  }
  if (confettiAnimId) cancelAnimationFrame(confettiAnimId);
  animate();
}

// ===== ZONK CRACK EFFECT =====
function showCrackEffect() {
  if (!crackOverlay) return;
  crackOverlay.hidden = false;
  crackOverlay.classList.add("is-active");
  // Screen shake
  document.body.classList.add("screen-shake");
  
  setTimeout(() => {
    document.body.classList.remove("screen-shake");
  }, 500);

  setTimeout(() => {
    crackOverlay.classList.remove("is-active");
    crackOverlay.classList.add("is-fading");
    setTimeout(() => {
      crackOverlay.hidden = true;
      crackOverlay.classList.remove("is-fading");
    }, 600);
  }, 2200);
}

// ===== INIT WHEEL (SVG Ceramic Plate) =====
function initWheel() {
  const size = 500;
  const cx = 250, cy = 250, R = 232;
  const sliceAngle = 360 / SEGMENTS.length;

  let svgHtml = `<svg viewBox="0 0 ${size} ${size}" class="wheel-svg">
    <circle cx="${cx}" cy="${cy}" r="246" fill="#FFFFFF" stroke="#000000" stroke-width="7"/>
    <circle cx="${cx}" cy="${cy}" r="240" fill="none" stroke="#000000" stroke-width="2.5" stroke-dasharray="4 6"/>
  `;

  SEGMENTS.forEach((seg, i) => {
    const a1 = i * sliceAngle, a2 = (i + 1) * sliceAngle, midA = a1 + sliceAngle / 2;
    const rad1 = (a1 * Math.PI) / 180, rad2 = (a2 * Math.PI) / 180;
    const x1 = cx + R * Math.sin(rad1), y1 = cy - R * Math.cos(rad1);
    const x2 = cx + R * Math.sin(rad2), y2 = cy - R * Math.cos(rad2);

    svgHtml += `<path d="M ${cx} ${cy} L ${x1.toFixed(2)} ${y1.toFixed(2)} A ${R} ${R} 0 0 1 ${x2.toFixed(2)} ${y2.toFixed(2)} Z" fill="${seg.color}" stroke="#000000" stroke-width="4.5" />`;

    svgHtml += `<g transform="rotate(${midA} ${cx} ${cy})">`;
    if (seg.isPrize) {
      svgHtml += `<circle cx="${cx}" cy="54" r="3.5" fill="#FFFFFF" stroke="#000000" stroke-width="1.5" />
        <text x="${cx}" y="74" text-anchor="middle" fill="${seg.textColor}" font-family="'Space Grotesk', sans-serif" font-weight="800">
          <tspan x="${cx}" dy="0" font-size="${seg.line1.length > 8 ? 10.5 : 12}" letter-spacing="1.5">${seg.line1}</tspan>
          <tspan x="${cx}" dy="16" font-size="${seg.line2.length > 8 ? 10.5 : 12}" letter-spacing="1.5">${seg.line2}</tspan>
        </text>`;
    } else {
      svgHtml += `<text x="${cx}" y="82" text-anchor="middle" fill="${seg.textColor}" font-family="'Space Grotesk', sans-serif" font-weight="900" font-size="13" letter-spacing="3">${seg.label}</text>`;
    }
    svgHtml += `</g>`;

    const studX = cx + 240 * Math.sin(rad1), studY = cy - 240 * Math.cos(rad1);
    svgHtml += `<circle cx="${studX.toFixed(2)}" cy="${studY.toFixed(2)}" r="4.5" fill="#800020" stroke="#000000" stroke-width="2" />`;
  });

  svgHtml += `
    <circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="#000000" stroke-width="6" pointer-events="none"/>
    <circle cx="${cx}" cy="${cy}" r="54" fill="#FFFFFF" stroke="#000000" stroke-width="5"/>
    <circle cx="${cx}" cy="${cy}" r="43" fill="#800020" stroke="#000000" stroke-width="3"/>
    <circle cx="${cx}" cy="${cy}" r="32" fill="#FFFFFF" stroke="#000000" stroke-width="3"/>
    <text x="${cx}" y="${cy + 5}" text-anchor="middle" fill="#000000" font-family="'Space Grotesk', sans-serif" font-weight="900" font-size="11.5" letter-spacing="2">DRACIN</text>
  </svg>`;

  wheelEl.innerHTML = svgHtml;
}

// ===== STATE & RENDERING =====
function renderLegend(prizes) {
  legendEl.innerHTML = Object.entries(prizes).map(([key, p]) => `
    <div class="legend-card">
      <div class="legend-name"><span class="legend-box"></span><span class="legend-text">${p.name}</span></div>
      <span class="legend-badge">PROMO</span>
    </div>
  `).join("");
}

function renderHistory(history) {
  if (!history.length) {
    historyListEl.innerHTML = '<li class="history-empty">Belum ada riwayat sajian.</li>';
    return;
  }
  historyListEl.innerHTML = history.map(h => `
    <li class="history-item ${h.is_win ? 'history-item--win' : 'history-item--lose'}">
      <span class="history-badge ${h.is_win ? 'badge-win' : 'badge-lose'}">${h.is_win ? 'MENANG' : 'ZONK'}</span>
      <span class="history-desc">${h.is_win ? h.prize_name : 'Belum Beruntung'}</span>
    </li>
  `).join("");
}

function applyState(state) {
  credit2kEl.textContent = state.credit_2k;
  credit5kEl.textContent = state.credit_5k;
  if (state.credit_2k > 0 || state.credit_5k > 0) {
    qrisContainer.classList.add("is-unlocked");
    qrisContainer.querySelector(".lock-badge").textContent = "STATUS: TERBUKA";
    qrisContainer.querySelector(".lock-instruction").textContent = "Kredit aktif! Silakan putar piring saji di bawah.";
    qrisContainer.querySelector(".lock-waiting").style.display = "none";
  } else {
    qrisContainer.classList.remove("is-unlocked");
    qrisContainer.querySelector(".lock-badge").textContent = "STATUS: TERKUNCI";
    qrisContainer.querySelector(".lock-instruction").textContent = "Silakan lakukan pembayaran QRIS di meja kasir (2K / 5K).";
    qrisContainer.querySelector(".lock-waiting").style.display = "flex";
  }
  spinBtn2k.disabled = state.credit_2k < 1 || spinning;
  spinBtn5k.disabled = state.credit_5k < 1 || spinning;
  renderLegend(state.prizes);
  renderHistory(state.history);
}

async function loadState() {
  try {
    const res = await fetch("/api/state");
    if (res.ok) applyState(await res.json());
  } catch (e) {}
}

setInterval(async () => {
  if (spinning) return;
  try { const res = await fetch("/api/state"); if (res.ok) applyState(await res.json()); } catch (e) {}
}, 2000);

// ===== SPIN LOGIC =====
async function spin(type) {
  if (spinning) return;
  spinning = true;
  spinBtn2k.disabled = true;
  spinBtn5k.disabled = true;
  resultEl.hidden = true;

  const clientToken = document.querySelector('meta[name="client-token"]')?.content || "";

  try {
    const res = await fetch("/api/spin", { 
      method: "POST",
      headers: { 
        "Content-Type": "application/json",
        "X-Client-Token": clientToken
      },
      body: JSON.stringify({ type: type, client_token: clientToken })
    });
    if (!res.ok) {
      const err = await res.json();
      resultEl.hidden = false;
      resultEl.className = "result lose";
      resultEl.textContent = err.error || "Terjadi kesalahan.";
      spinning = false;
      loadState();
      return;
    }
    const data = await res.json();

    const targetCenter = data.segment_index * SLICE + SLICE / 2;
    const extraSpins = 5 * 360;
    const currentMod = currentRotation % 360;
    const delta = (360 - targetCenter - currentMod + 360) % 360;
    const startAngle = currentRotation;
    const targetRotation = currentRotation + extraSpins + delta;
    currentRotation = targetRotation;

    // Start physically synchronized spinning sound
    startSpinTicker(startAngle, targetRotation, 4200);

    wheelEl.style.transform = `rotate(${currentRotation}deg)`;

    wheelEl.addEventListener("transitionend", function onEnd() {
      wheelEl.removeEventListener("transitionend", onEnd);
      stopSpinTicker();

      resultEl.hidden = false;
      if (data.is_win) {
        resultEl.className = "result win";
        resultEl.innerHTML = `<div class="result-title">★ SAJIAN TERPILIH ★</div><div class="result-prize">Kamu Mendapatkan: <strong>${data.prize_name}</strong></div>`;
        playWinFanfare();
        launchConfetti();
      } else {
        resultEl.className = "result lose";
        resultEl.innerHTML = `<div class="result-title">PIRING KOSONG (ZONK)</div><div class="result-prize">Belum beruntung, silakan coba lagi!</div>`;
        playZonkExplosion();
        showCrackEffect();
      }
      applyState(data.state);
      spinning = false;
    }, { once: true });
  } catch (e) {
    stopSpinTicker();
    spinning = false;
    spinBtn2k.disabled = false;
    spinBtn5k.disabled = false;
  }
}

spinBtn2k.addEventListener("click", () => spin("2k"));
spinBtn5k.addEventListener("click", () => spin("5k"));

initWheel();
loadState();

// ===== BGM DORAEMON (ON / OFF Toggle & Auto-Start) =====
const bgmAudio = document.getElementById("bgm-audio");
const bgmBtn = document.getElementById("bgm-btn");
const bgmState = document.getElementById("bgm-state");

function updateBgmUI(isPlaying) {
  if (!bgmBtn || !bgmState) return;
  if (isPlaying) {
    bgmBtn.classList.add("is-playing");
    bgmState.textContent = "ON";
  } else {
    bgmBtn.classList.remove("is-playing");
    bgmState.textContent = "OFF";
  }
}

if (bgmAudio) {
  bgmAudio.volume = 0.3;

  bgmAudio.addEventListener("play", () => updateBgmUI(true));
  bgmAudio.addEventListener("pause", () => updateBgmUI(false));
  bgmAudio.addEventListener("ended", () => updateBgmUI(false));

  if (bgmBtn) {
    bgmBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (bgmAudio.paused) {
        bgmAudio.play().catch(() => {});
      } else {
        bgmAudio.pause();
      }
    });
  }

  let firstInteractionDone = false;
  function handleFirstInteraction() {
    if (firstInteractionDone) return;
    firstInteractionDone = true;
    if (bgmAudio.paused) {
      bgmAudio.play().catch(() => {});
    }
  }

  bgmAudio.play().catch(() => {});
  ["click", "touchstart", "keydown"].forEach((evt) => {
    document.addEventListener(evt, handleFirstInteraction, { once: true });
  });
}
