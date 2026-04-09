/**
 * TOKEN PAY ID — Automatic Puzzle CAPTCHA
 * Invisible by default. Shows a slider puzzle when behavior is suspicious.
 * Manual mode: always shows before form submit.
 */
(function(global) {
    'use strict';

    // ── Behavior monitor ──────────────────────────────────────────────────────
    let _score = 0; // higher = more bot-like
    let _mouseMovements = 0;
    let _keystrokes = 0;
    let _formFocusTime = null;
    let _captchaMode = 'auto';
    let _autoThreshold = 3;
    let _captchaToken = null;

    function _trackBehavior() {
        document.addEventListener('mousemove', () => { _mouseMovements++; if (_score > 0) _score = Math.max(0, _score - 0.05); }, { passive: true });
        document.addEventListener('keydown', () => { _keystrokes++; }, { passive: true });
        document.addEventListener('focusin', e => { if (e.target.tagName === 'INPUT') _formFocusTime = Date.now(); });
    }

    function _getBotScore() {
        let s = 0;
        if (_mouseMovements < 3) s += 2;
        if (_keystrokes < 2) s += 1;
        const fillTime = _formFocusTime ? (Date.now() - _formFocusTime) : 0;
        if (fillTime < 800 && _keystrokes > 0) s += 2; // filled too fast
        return s;
    }

    // ── Fetch config ──────────────────────────────────────────────────────────
    function _loadConfig() {
        return fetch('/api/v1/captcha/config').then(r => r.json()).then(d => {
            _captchaMode = d.mode || 'auto';
            _autoThreshold = d.auto_threshold || 3;
        }).catch(() => {});
    }

    // ── Challenge fetch ───────────────────────────────────────────────────────
    function _fetchChallenge() {
        return fetch('/api/v1/captcha/challenge').then(r => r.json());
    }

    // ── Verify solution ───────────────────────────────────────────────────────
    function _verifySolution(nonce, x) {
        return fetch('/api/v1/captcha/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nonce, x })
        }).then(r => r.json());
    }

    // ── Draw puzzle on canvas ─────────────────────────────────────────────────
    function _drawPuzzle(bgCanvas, pieceCanvas, holeX, holeY, pieceSize, sliderX) {
        const W = bgCanvas.width, H = bgCanvas.height;
        const bx = bgCanvas.getContext('2d');
        const px = pieceCanvas.getContext('2d');

        // Procedural background scene (unique per challenge)
        const seed = (holeX * 137 + holeY * 251) % 360;

        // Sky gradient
        const sky = bx.createLinearGradient(0, 0, 0, H);
        sky.addColorStop(0, `hsl(${seed}, 45%, 18%)`);
        sky.addColorStop(0.5, `hsl(${(seed + 30) % 360}, 35%, 12%)`);
        sky.addColorStop(1, `hsl(${(seed + 60) % 360}, 25%, 8%)`);
        bx.fillStyle = sky;
        bx.fillRect(0, 0, W, H);

        // Stars / dots
        bx.save();
        const rng = (s) => { s = Math.sin(s) * 43758.5453; return s - Math.floor(s); };
        for (let i = 0; i < 40; i++) {
            const sx = rng(i * 13.7 + seed) * W;
            const sy = rng(i * 7.3 + seed + 100) * H * 0.6;
            const sr = rng(i * 3.1 + seed + 200) * 1.5 + 0.3;
            bx.beginPath();
            bx.arc(sx, sy, sr, 0, Math.PI * 2);
            bx.fillStyle = `rgba(255,255,255,${rng(i + 50) * 0.3 + 0.1})`;
            bx.fill();
        }
        bx.restore();

        // Mountain layers
        for (let layer = 0; layer < 3; layer++) {
            bx.save();
            const baseY = H * (0.45 + layer * 0.15);
            const lightness = 6 + layer * 3;
            bx.fillStyle = `hsl(${(seed + layer * 40) % 360}, 20%, ${lightness}%)`;
            bx.beginPath();
            bx.moveTo(0, H);
            for (let mx = 0; mx <= W; mx += 4) {
                const n1 = Math.sin(mx * 0.02 + layer * 2 + seed * 0.01) * 25;
                const n2 = Math.sin(mx * 0.05 + layer * 5 + seed * 0.02) * 12;
                const n3 = Math.sin(mx * 0.11 + layer * 11) * 6;
                bx.lineTo(mx, baseY + n1 + n2 + n3);
            }
            bx.lineTo(W, H);
            bx.closePath();
            bx.fill();
            bx.restore();
        }

        // Glow orb
        bx.save();
        const orbX = W * (0.2 + rng(seed + 77) * 0.6);
        const orbY = H * (0.15 + rng(seed + 88) * 0.25);
        const orbGrad = bx.createRadialGradient(orbX, orbY, 0, orbX, orbY, 40);
        orbGrad.addColorStop(0, `hsla(${seed}, 60%, 70%, 0.25)`);
        orbGrad.addColorStop(1, 'transparent');
        bx.fillStyle = orbGrad;
        bx.fillRect(0, 0, W, H);
        bx.restore();

        // Noise texture overlay
        bx.save();
        bx.globalAlpha = 0.04;
        for (let ny = 0; ny < H; ny += 3) {
            for (let nx = 0; nx < W; nx += 3) {
                if (rng(nx * 97 + ny * 53 + seed) > 0.5) {
                    bx.fillStyle = '#fff';
                    bx.fillRect(nx, ny, 1, 1);
                }
            }
        }
        bx.restore();

        // "TOKEN PAY" watermark
        bx.save();
        bx.font = 'bold 10px Comfortaa, sans-serif';
        bx.fillStyle = 'rgba(255,255,255,0.06)';
        bx.fillText('TOKEN PAY', W - 85, H - 8);
        bx.restore();

        // Draw puzzle hole (dark rectangle with inner glow)
        bx.save();
        bx.fillStyle = 'rgba(0,0,0,0.65)';
        bx.fillRect(holeX, holeY, pieceSize, pieceSize);
        bx.strokeStyle = 'rgba(255,255,255,0.15)';
        bx.lineWidth = 1.5;
        bx.strokeRect(holeX + 0.75, holeY + 0.75, pieceSize - 1.5, pieceSize - 1.5);
        bx.restore();

        // Guide arrows in hole
        bx.save();
        bx.globalAlpha = 0.25;
        bx.fillStyle = '#fff';
        const cx = holeX + pieceSize / 2, cy = holeY + pieceSize / 2;
        bx.beginPath();
        bx.moveTo(cx - 10, cy); bx.lineTo(cx - 4, cy - 5); bx.lineTo(cx - 4, cy + 5); bx.closePath();
        bx.fill();
        bx.beginPath();
        bx.moveTo(cx + 10, cy); bx.lineTo(cx + 4, cy - 5); bx.lineTo(cx + 4, cy + 5); bx.closePath();
        bx.fill();
        bx.restore();

        // Draw piece (same bg snippet + bright border)
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = W; tempCanvas.height = H;
        const tx = tempCanvas.getContext('2d');
        tx.drawImage(bgCanvas, 0, 0);

        px.clearRect(0, 0, pieceSize, pieceSize);
        px.drawImage(tempCanvas, holeX, holeY, pieceSize, pieceSize, 0, 0, pieceSize, pieceSize);

        // Add bright border to piece
        px.strokeStyle = 'rgba(255,255,255,0.55)';
        px.lineWidth = 2;
        px.strokeRect(1, 1, pieceSize - 2, pieceSize - 2);

        // Piece inner shadow
        const pieceGrad = px.createLinearGradient(0, 0, pieceSize, pieceSize);
        pieceGrad.addColorStop(0, 'rgba(255,255,255,0.08)');
        pieceGrad.addColorStop(1, 'rgba(0,0,0,0.15)');
        px.fillStyle = pieceGrad;
        px.fillRect(0, 0, pieceSize, pieceSize);
    }

    // ── Draw custom image background ─────────────────────────────────────────
    function _drawCustomBg(bgCanvas, pieceCanvas, bgImage, holeX, holeY, pieceSize, onReady) {
        const img = new Image();
        img.onload = function() {
            const W = bgCanvas.width, H = bgCanvas.height;
            const bx = bgCanvas.getContext('2d');
            const px = pieceCanvas.getContext('2d');
            // Draw image scaled to fill canvas
            bx.drawImage(img, 0, 0, W, H);
            // Draw puzzle hole
            bx.save();
            bx.fillStyle = 'rgba(0,0,0,0.65)';
            bx.fillRect(holeX, holeY, pieceSize, pieceSize);
            bx.strokeStyle = 'rgba(255,255,255,0.15)';
            bx.lineWidth = 1.5;
            bx.strokeRect(holeX + 0.75, holeY + 0.75, pieceSize - 1.5, pieceSize - 1.5);
            bx.restore();
            // Guide arrows
            bx.save();
            bx.globalAlpha = 0.25;
            bx.fillStyle = '#fff';
            const cx = holeX + pieceSize / 2, cy = holeY + pieceSize / 2;
            bx.beginPath(); bx.moveTo(cx - 10, cy); bx.lineTo(cx - 4, cy - 5); bx.lineTo(cx - 4, cy + 5); bx.closePath(); bx.fill();
            bx.beginPath(); bx.moveTo(cx + 10, cy); bx.lineTo(cx + 4, cy - 5); bx.lineTo(cx + 4, cy + 5); bx.closePath(); bx.fill();
            bx.restore();
            // Draw piece from original image
            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = W; tempCanvas.height = H;
            const tx = tempCanvas.getContext('2d');
            tx.drawImage(img, 0, 0, W, H);
            px.clearRect(0, 0, pieceSize, pieceSize);
            px.drawImage(tempCanvas, holeX, holeY, pieceSize, pieceSize, 0, 0, pieceSize, pieceSize);
            px.strokeStyle = 'rgba(255,255,255,0.55)';
            px.lineWidth = 2;
            px.strokeRect(1, 1, pieceSize - 2, pieceSize - 2);
            onReady();
        };
        img.onerror = function() { onReady(); }; // fallback: procedural bg already drawn
        img.src = bgImage;
    }

    // ── Show captcha modal ─────────────────────────────────────────────────────
    function _showModal(onSuccess, onFail) {
        _fetchChallenge().then(ch => {
            let { nonce, hole_x, hole_y, width, height, piece_size, bg_image } = ch;
            const ps = piece_size || 50;

            const overlay = document.createElement('div');
            overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.7);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);z-index:99999;display:flex;align-items:center;justify-content:center;animation:tpCaptchaIn .22s ease';

            const style = document.createElement('style');
            style.textContent = `
                @keyframes tpCaptchaIn{from{opacity:0;transform:scale(.95)}to{opacity:1;transform:scale(1)}}
                @keyframes tpCaptchaShake{0%,100%{transform:translateX(0)}20%{transform:translateX(-8px)}40%{transform:translateX(8px)}60%{transform:translateX(-5px)}80%{transform:translateX(5px)}}
                .tpc-box{background:#0d0d0f;border:1px solid rgba(255,255,255,.1);border-radius:16px;padding:24px;width:360px;max-width:92vw;box-shadow:0 24px 80px rgba(0,0,0,.8);font-family:Comfortaa,sans-serif;color:#fff}
                .tpc-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
                .tpc-title{font-size:.88rem;font-weight:700;color:rgba(255,255,255,.9)}
                .tpc-subtitle{font-size:.7rem;color:rgba(255,255,255,.35);margin-top:2px}
                .tpc-close{background:none;border:none;color:rgba(255,255,255,.3);cursor:pointer;font-size:1.2rem;padding:2px 6px;border-radius:4px;transition:all .15s;line-height:1}
                .tpc-close:hover{color:rgba(255,255,255,.7);background:rgba(255,255,255,.06)}
                .tpc-canvas-wrap{position:relative;border-radius:10px;overflow:hidden;margin-bottom:16px;border:1px solid rgba(255,255,255,.06)}
                .tpc-piece{position:absolute;top:${hole_y}px;left:0;cursor:grab;transition:box-shadow .15s;border-radius:3px}
                .tpc-piece:active{cursor:grabbing;box-shadow:0 0 0 2px rgba(255,255,255,.4)}
                .tpc-slider-wrap{margin-bottom:16px}
                .tpc-slider-track{position:relative;height:40px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);border-radius:10px;overflow:hidden}
                .tpc-slider-fill{position:absolute;left:0;top:0;bottom:0;background:rgba(255,255,255,.06);border-radius:10px;transition:none;pointer-events:none}
                .tpc-slider-thumb{position:absolute;top:4px;bottom:4px;width:32px;background:#fff;border-radius:7px;cursor:grab;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 12px rgba(0,0,0,.4);transition:box-shadow .15s;user-select:none}
                .tpc-slider-thumb:hover{box-shadow:0 2px 20px rgba(255,255,255,.2)}
                .tpc-slider-thumb:active{cursor:grabbing}
                .tpc-slider-arrow{width:16px;height:16px;opacity:.5}
                .tpc-hint{font-size:.7rem;color:rgba(255,255,255,.25);text-align:center;margin-bottom:14px}
                .tpc-error{font-size:.72rem;color:rgba(255,255,255,.55);text-align:center;margin-bottom:10px;display:none}
                .tpc-footer{display:flex;align-items:center;justify-content:space-between}
                .tpc-brand{font-size:.62rem;color:rgba(255,255,255,.15);font-weight:700;letter-spacing:.5px}
                .tpc-refresh{background:none;border:none;color:rgba(255,255,255,.2);cursor:pointer;font-size:.7rem;font-family:inherit;padding:4px 8px;border-radius:6px;transition:all .15s;display:flex;align-items:center;gap:4px}
                .tpc-refresh:hover{color:rgba(255,255,255,.5);background:rgba(255,255,255,.05)}
                .tpc-success-icon{width:48px;height:48px;border-radius:50%;background:rgba(255,255,255,.06);border:2px solid rgba(255,255,255,.15);display:flex;align-items:center;justify-content:center;margin:0 auto 12px}
            `;
            document.head.appendChild(style);

            overlay.innerHTML = `
                <div class="tpc-box">
                    <div class="tpc-header">
                        <div>
                            <div class="tpc-title">Подтверждение</div>
                            <div class="tpc-subtitle">Переместите фрагмент на нужное место</div>
                        </div>
                        <button class="tpc-close" id="tpcClose">✕</button>
                    </div>
                    <div class="tpc-canvas-wrap" id="tpcWrap">
                        <canvas id="tpcBg" width="${width}" height="${height}" style="display:block;width:100%;height:auto"></canvas>
                        <canvas id="tpcPiece" class="tpc-piece" width="${ps}" height="${ps}" style="width:${ps}px;height:${ps}px"></canvas>
                    </div>
                    <div class="tpc-slider-wrap">
                        <div class="tpc-slider-track" id="tpcTrack">
                            <div class="tpc-slider-fill" id="tpcFill"></div>
                            <div class="tpc-slider-thumb" id="tpcThumb">
                                <svg class="tpc-slider-arrow" viewBox="0 0 24 24" fill="none" stroke="rgba(0,0,0,.5)" stroke-width="2.5"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                            </div>
                        </div>
                    </div>
                    <div class="tpc-hint">Перетащите → чтобы установить фрагмент</div>
                    <div class="tpc-error" id="tpcError"></div>
                    <div class="tpc-footer">
                        <span class="tpc-brand">TOKEN PAY ID</span>
                        <button class="tpc-refresh" id="tpcRefresh">
                            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M1 4v6h6M23 20v-6h-6"/><path d="M20.49 9A9 9 0 005.64 5.64L1 10M23 14l-4.64 4.36A9 9 0 013.51 15"/></svg>
                            Обновить
                        </button>
                    </div>
                </div>`;

            document.body.appendChild(overlay);

            const bgCanvas = document.getElementById('tpcBg');
            const pieceCanvas = document.getElementById('tpcPiece');
            const track = document.getElementById('tpcTrack');
            const thumb = document.getElementById('tpcThumb');
            const fill = document.getElementById('tpcFill');
            const errEl = document.getElementById('tpcError');
            const wrap = document.getElementById('tpcWrap');

            // Scale factor (CSS vs canvas pixels)
            const scale = width / wrap.getBoundingClientRect().width || 1;

            // Draw puzzle: use custom image if provided, otherwise procedural
            if (bg_image) {
                _drawPuzzle(bgCanvas, pieceCanvas, hole_x, hole_y, ps, 0);
                _drawCustomBg(bgCanvas, pieceCanvas, bg_image, hole_x, hole_y, ps, () => {});
            } else {
                _drawPuzzle(bgCanvas, pieceCanvas, hole_x, hole_y, ps, 0);
            }

            // Position piece canvas absolutely over background
            const scaleY = (height / (bgCanvas.getBoundingClientRect().height || height));
            pieceCanvas.style.top = Math.round(hole_y / (height / 100)) + '%';

            // Slider drag
            const trackW = track.offsetWidth - thumb.offsetWidth;
            let dragging = false, startX = 0, thumbX = 0;

            function setThumbPos(px_) {
                thumbX = Math.max(0, Math.min(trackW, px_));
                thumb.style.left = thumbX + 'px';
                fill.style.width = (thumbX + thumb.offsetWidth) + 'px';
                // Move puzzle piece proportionally
                const pieceTravel = width - ps - 10;
                const canvasPieceX = Math.round((thumbX / trackW) * pieceTravel);
                const displayPieceX = Math.round((thumbX / trackW) * (wrap.offsetWidth - ps));
                pieceCanvas.style.left = displayPieceX + 'px';
                pieceCanvas.dataset.canvasX = canvasPieceX;
            }

            function onStart(clientX) { dragging = true; startX = clientX - thumbX; }
            function onMove(clientX) { if (!dragging) return; setThumbPos(clientX - startX); }
            function onEnd() {
                if (!dragging) return; dragging = false;
                const canvasX = parseInt(pieceCanvas.dataset.canvasX || 0);
                _verifySolution(nonce, canvasX).then(d => {
                    if (d && d.success) {
                        _captchaToken = d.captcha_token;
                        // Show success animation
                        errEl.style.display = 'none';
                        thumb.style.background = 'rgba(255,255,255,.7)';
                        fill.style.background = 'rgba(255,255,255,.1)';
                        setTimeout(() => {
                            _cleanup();
                            overlay.remove();
                            style.remove();
                            onSuccess(_captchaToken);
                        }, 600);
                    } else {
                        // Shake + reset
                        errEl.textContent = d.error?.message || 'Неверно. Попробуйте снова.';
                        errEl.style.display = 'block';
                        overlay.querySelector('.tpc-box').style.animation = 'tpCaptchaShake .4s ease';
                        setTimeout(() => {
                            overlay.querySelector('.tpc-box').style.animation = '';
                            setThumbPos(0);
                            // Re-fetch challenge
                            _fetchChallenge().then(ch2 => {
                                nonce = ch2.nonce;
                                _drawPuzzle(bgCanvas, pieceCanvas, ch2.hole_x, ch2.hole_y, ps, 0);
                                pieceCanvas.style.top = Math.round(ch2.hole_y / (height / 100)) + '%';
                            });
                        }, 500);
                    }
                }).catch(() => { errEl.textContent = 'Ошибка сети.'; errEl.style.display = 'block'; });
            }

            // Named handlers for cleanup
            function _onMouseMove(e) { onMove(e.clientX); }
            function _onMouseUp() { onEnd(); }
            function _onTouchMove(e) { if(dragging) { e.preventDefault(); onMove(e.touches[0].clientX); } }
            function _onTouchEnd() { onEnd(); }
            function _cleanup() {
                document.removeEventListener('mousemove', _onMouseMove);
                document.removeEventListener('mouseup', _onMouseUp);
                document.removeEventListener('touchmove', _onTouchMove);
                document.removeEventListener('touchend', _onTouchEnd);
            }

            // Mouse events
            thumb.addEventListener('mousedown', e => { e.preventDefault(); onStart(e.clientX); });
            document.addEventListener('mousemove', _onMouseMove);
            document.addEventListener('mouseup', _onMouseUp);

            // Touch events
            thumb.addEventListener('touchstart', e => { e.preventDefault(); onStart(e.touches[0].clientX); }, { passive: false });
            document.addEventListener('touchmove', _onTouchMove, { passive: false });
            document.addEventListener('touchend', _onTouchEnd);

            // Refresh
            document.getElementById('tpcRefresh').addEventListener('click', () => {
                _fetchChallenge().then(ch2 => {
                    nonce = ch2.nonce;
                    _drawPuzzle(bgCanvas, pieceCanvas, ch2.hole_x, ch2.hole_y, ps, 0);
                    pieceCanvas.style.top = Math.round(ch2.hole_y / (height / 100)) + '%';
                    setThumbPos(0);
                    errEl.style.display = 'none';
                    thumb.style.background = '#fff';
                    fill.style.background = 'rgba(255,255,255,.06)';
                });
            });

            // Close
            document.getElementById('tpcClose').addEventListener('click', () => {
                _cleanup();
                overlay.remove();
                style.remove();
                if (onFail) onFail('closed');
            });

        }).catch(err => { console.error('[CAPTCHA] fetch error', err); onSuccess(null); });
    }

    // ── Public API ─────────────────────────────────────────────────────────────
    /**
     * Call before form submit.
     * Returns a Promise that resolves with captcha_token (or null if captcha is off/skipped).
     */
    function check() {
        return new Promise((resolve) => {
            if (_captchaToken) { const t = _captchaToken; _captchaToken = null; resolve(t); return; }
            if (_captchaMode === 'off') { resolve(null); return; }
            if (_captchaMode === 'auto') {
                const score = _getBotScore();
                if (score < _autoThreshold) { resolve(null); return; }
            }
            // Modal was requested — if user dismisses, resolve false to signal cancellation
            _showModal(resolve, () => resolve(false));
        });
    }

    /**
     * Force-show captcha (manual trigger).
     */
    function show() {
        return new Promise((resolve, reject) => {
            _showModal(resolve, reject);
        });
    }

    /**
     * Reset behavior counters (call after successful login).
     */
    function reset() {
        _score = 0; _mouseMovements = 0; _keystrokes = 0;
        _formFocusTime = null; _captchaToken = null;
    }

    // Init
    _trackBehavior();
    _loadConfig();

    global.TokenPayCaptcha = { check, show, reset, getMode: function() { return _captchaMode; } };

})(window);
