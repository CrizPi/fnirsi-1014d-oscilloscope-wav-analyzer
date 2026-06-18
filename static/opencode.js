// FNIRSI 1014D Analyzer - Professional UI Module
// All interactive functionality for the desktop application.

(function () {
    'use strict';

    /* ===== TOAST SYSTEM ===== */
    let toastTimer = null;

    function showToast(message, variant) {
        variant = variant || 'success';
        var toast = document.getElementById('toast');
        if (!toast || !message) return;
        toast.textContent = message;
        toast.dataset.variant = variant;
        toast.hidden = false;
        toast.classList.add('is-visible');
        window.clearTimeout(toastTimer);
        toastTimer = window.setTimeout(function () {
            toast.classList.remove('is-visible');
            window.setTimeout(function () { toast.hidden = true; }, 180);
        }, 2200);
    }

    /* ===== COPY ENDPOINT ===== */
    async function copyEndpoint(event, url, okMessage) {
        event.preventDefault();
        try {
            var response = await fetch(url);
            var text = await response.text();
            await navigator.clipboard.writeText(text);
            showToast(okMessage, 'success');
        } catch (error) {
            console.error(error);
            showToast('Error copying content.', 'error');
        }
    }

    /* ===== LOADING OVERLAY ===== */
    function showLoadingOverlay() {
        var overlay = document.getElementById('loadingOverlay');
        if (!overlay) return;
        overlay.classList.add('visible');
        overlay.setAttribute('aria-hidden', 'false');
    }

    function hideLoadingOverlay() {
        var overlay = document.getElementById('loadingOverlay');
        if (!overlay) return;
        overlay.classList.remove('visible');
        overlay.setAttribute('aria-hidden', 'true');
    }

    /* ===== SIDEBAR NAVIGATION ===== */
    function activatePanel(target) {
        var items = document.querySelectorAll('.sidebar-item[data-panel]');
        var panels = document.querySelectorAll('.content-panel');

        items.forEach(function (item) { item.classList.remove('active'); });
        panels.forEach(function (p) { p.classList.remove('active'); });

        var activeItem = document.querySelector('.sidebar-item[data-panel="' + target + '"]');
        var activePanel = document.getElementById('panel-' + target);
        if (activeItem) activeItem.classList.add('active');
        if (activePanel) activePanel.classList.add('active');

        localStorage.setItem('selectedPanel', target);
    }

    function activateFilter(target) {
        var buttons = document.querySelectorAll('.filtro[data-target]');
        var sections = document.querySelectorAll('.contenido');
        buttons.forEach(function (b) { b.classList.remove('activo'); });
        sections.forEach(function (s) { s.style.display = 'none'; });

        var activeBtn = document.querySelector('.filtro[data-target="' + target + '"]');
        var section = document.querySelector('.' + target);
        if (activeBtn) activeBtn.classList.add('activo');
        if (section) section.style.display = 'block';
        localStorage.setItem('selectedFilter', target);
    }

    /* ===== AJAX FRAGMENT SYSTEM ===== */
    function replaceNodeFromHtml(id, html) {
        if (!html) return;
        var current = document.getElementById(id);
        if (!current) return;
        var template = document.createElement('template');
        template.innerHTML = html.trim();
        var next = template.content.firstElementChild;
        if (next) current.replaceWith(next);
    }

    function applyAjaxFragments(payload, previousScrollY) {
        replaceNodeFromHtml('alertHost', payload.alertHost);
        replaceNodeFromHtml('pageState', payload.pageState);
        if (payload.moduleSectionId && payload.moduleSection) {
            replaceNodeFromHtml(payload.moduleSectionId, payload.moduleSection);
        }
        if (payload.measuresPanel) {
            replaceNodeFromHtml('measuresPanel', payload.measuresPanel);
        }
        initCursorGraph();
        var selectedFilter = localStorage.getItem('selectedFilter') || 'math';
        activateFilter(selectedFilter);
        var pageState = document.getElementById('pageState');
        if (pageState && pageState.dataset.toastMessage) {
            showToast(pageState.dataset.toastMessage, pageState.dataset.toastVariant || 'success');
        }
        window.requestAnimationFrame(function () {
            window.scrollTo(0, previousScrollY);
            window.requestAnimationFrame(function () {
                window.scrollTo(0, previousScrollY);
            });
        });
    }

    function getModuleActionName(formData) {
        var keys = [
            'math_op', 'fft_apply', 'statistics_apply',
            'calculus_apply', 'current_apply', 'current_save', 'total_current_apply',
            'calibration_apply',
            'calibration_reset', 'cursor_apply', 'cycle_apply',
            'save_snapshot', 'compare_apply',
            'digital_pwm_apply', 'digital_edges_apply', 'digital_pulses_apply',
            'digital_logic_apply'
        ];
        return keys.find(function (k) { return formData.has(k); }) || '';
    }

    async function submitModuleForm(form) {
        showLoadingOverlay();
        var formData = new FormData(form);
        var previousScrollY = window.scrollY;
        try {
            var response = await fetch(
                form.getAttribute('action') || window.location.pathname,
                {
                    method: 'POST',
                    body: formData,
                    credentials: 'same-origin',
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                }
            );
            var payload = await response.json();
            if (!response.ok) {
                applyAjaxFragments(payload, previousScrollY);
                throw new Error((payload && payload.error) || 'Action failed.');
            }
            applyAjaxFragments(payload, previousScrollY);
        } finally {
            hideLoadingOverlay();
        }
    }

    /* ===== CURSOR GRAPH ===== */
    var cursorGraph, cursorForm, cursorT1Input, cursorT2Input;
    var cursorSvg, cursorGrid, cursorWavePath, cursorWavePathB;
    var cursorLineT1, cursorLineT2, cursorHandleT1, cursorHandleT2;
    var cursorLabelT1, cursorLabelT2, cursorDotT1, cursorDotT2;
    var cursorPlotPoints = [];
    var cursorPlotPointsB = [];
    var cursorTimeMin = 0, cursorTimeMax = 1;
    var cursorVoltageMin = -1, cursorVoltageMax = 1;
    var cursorVdivCh1 = 0.1, cursorVdivCh2 = 1;
    var activeCursorKey = null;
    var cursorMode = 'single';

    var SVG_W = 1000, SVG_H = 607;
    var PLOT_L = 28, PLOT_R = 972, PLOT_T = 24, PLOT_B = 563;

    function clamp(v, min, max) { return Math.min(Math.max(v, min), max); }
    function formatTime(v) { return Number.parseFloat(v.toFixed(9)).toString(); }

    function timeToPercent(t) {
        if (!isFinite(cursorTimeMin) || !isFinite(cursorTimeMax) || cursorTimeMax <= cursorTimeMin) return 0;
        return clamp((t - cursorTimeMin) / (cursorTimeMax - cursorTimeMin), 0, 1) * 100;
    }

    function percentToTime(p) {
        if (!isFinite(cursorTimeMin) || !isFinite(cursorTimeMax) || cursorTimeMax <= cursorTimeMin) return 0;
        return cursorTimeMin + (cursorTimeMax - cursorTimeMin) * clamp(p / 100, 0, 1);
    }

    function timeToSvgX(t) { return PLOT_L + ((PLOT_R - PLOT_L) * timeToPercent(t)) / 100; }

    function getVoltageRange(points) {
        if (!points || !points.length) return { vMin: -1, vMax: 1 };
        var vMin = Infinity, vMax = -Infinity;
        for (var i = 0; i < points.length; i++) {
            var v = points[i].v;
            if (v < vMin) vMin = v;
            if (v > vMax) vMax = v;
        }
        var maxAbs = Math.max(Math.abs(vMin), Math.abs(vMax), 1e-9);
        return { vMin: -maxAbs, vMax: maxAbs };
    }

    function interpolateVAtT(t) {
        if (!cursorPlotPoints.length) return 0;
        if (t <= cursorPlotPoints[0].t) return cursorPlotPoints[0].v;
        if (t >= cursorPlotPoints[cursorPlotPoints.length - 1].t) return cursorPlotPoints[cursorPlotPoints.length - 1].v;
        for (var i = 0; i < cursorPlotPoints.length - 1; i++) {
            var a = cursorPlotPoints[i], b = cursorPlotPoints[i + 1];
            if (t >= a.t && t <= b.t) {
                var span = b.t - a.t || 1;
                return a.v + (b.v - a.v) * ((t - a.t) / span);
            }
        }
        return cursorPlotPoints[cursorPlotPoints.length - 1].v;
    }

    var CHANNEL_COLORS = { X: '#ffff00', Y: '#00e5ff', MATH: '#ff00ff' };  /* must match constants.py CHANNEL_COLORS_STR */
    var CENTER_LINE_COLOR = '#6A6A7A';

    function _escapeXml(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }

    function fmtTime(value) {
        if (value >= 1) return value.toFixed(3) + ' s/Div';
        if (value >= 1e-3) return (value * 1e3).toFixed(2) + ' ms/Div';
        if (value >= 1e-6) return (value * 1e6).toFixed(1) + ' \u00b5s/Div';
        return (value * 1e9).toFixed(1) + ' ns/Div';
    }

    function fmtVolt(value) {
        if (value >= 1) return value.toFixed(3) + ' V/Div';
        if (value >= 1e-3) return (value * 1e3).toFixed(2) + ' mV/Div';
        return (value * 1e6).toFixed(1) + ' \u00b5V/Div';
    }

    function getChannelColor(ch) {
        if (ch) return CHANNEL_COLORS[ch] || CHANNEL_COLORS.X;
        ch = cursorGraph ? cursorGraph.dataset.channel || 'X' : 'X';
        return CHANNEL_COLORS[ch] || CHANNEL_COLORS.X;
    }

    function getSignalColor(signalCh) {
        return CHANNEL_COLORS[signalCh] || CHANNEL_COLORS.X;
    }

    function getCurrentSignalA() {
        var sel = document.querySelector('select[name="cursor_signal_a"]');
        return sel ? sel.value : (cursorGraph ? cursorGraph.dataset.signalA || 'X' : 'X');
    }

    function getCurrentSignalB() {
        var sel = document.querySelector('select[name="cursor_signal_b"]');
        return sel ? sel.value : (cursorGraph ? cursorGraph.dataset.signalB || 'Y' : 'Y');
    }

    function getCurrentMode() {
        var sel = document.querySelector('select[name="cursor_mode"]');
        return sel ? sel.value : (cursorGraph ? cursorGraph.dataset.cursorMode || 'single' : 'single');
    }

    function getChannelLabel() {
        if (!cursorGraph) return 'CH1';
        var ch = cursorGraph.dataset.channel || 'X';
        if (ch === 'X') return cursorGraph.dataset.ch1Name || 'CH1';
        if (ch === 'Y') return cursorGraph.dataset.ch2Name || 'CH2';
        return 'MATH';
    }

    function getSignalLabel(signalCh) {
        if (signalCh === 'X') return cursorGraph ? cursorGraph.dataset.ch1Name || 'CH1' : 'CH1';
        if (signalCh === 'Y') return cursorGraph ? cursorGraph.dataset.ch2Name || 'CH2' : 'CH2';
        return 'MATH';
    }

    function _getVdivForSignal(signalCh) {
        if (signalCh === 'X') return cursorVdivCh1;
        if (signalCh === 'Y') return cursorVdivCh2;
        return cursorVdivCh1;
    }

    function _getVoltageRangeForSignal(signalCh) {
        var vdiv = _getVdivForSignal(signalCh);
        return { vMin: -4 * vdiv, vMax: 4 * vdiv };
    }

    function getCurrentSingleChannel() {
        var sel = document.querySelector('select[name="cursor_channel"]');
        return sel ? sel.value : (cursorGraph ? cursorGraph.dataset.channel || 'X' : 'X');
    }

    function renderCursorLegend() {
        var el = document.getElementById('cursorGraphInfo');
        if (!el) return;
        var tdiv = cursorGraph ? Number.parseFloat(cursorGraph.dataset.tdiv || '0') : 0;
        var tdivStr = tdiv > 0 ? fmtTime(tdiv) : '';
        var parts = [];
        if (cursorMode === 'dual') {
            var sigA = getCurrentSignalA();
            var sigB = getCurrentSignalB();
            var colorA = getSignalColor(sigA);
            var colorB = getSignalColor(sigB);
            var labelA = getSignalLabel(sigA);
            var labelB = getSignalLabel(sigB);
            var vdivA = _getVdivForSignal(sigA);
            var vdivB = _getVdivForSignal(sigB);
            var vdivAStr = vdivA > 0 ? fmtVolt(vdivA) : '';
            var vdivBStr = vdivB > 0 ? fmtVolt(vdivB) : '';
            parts.push('<span class="graph-label"><span class="graph-swatch" style="background:' + colorA + '"></span>' + _escapeXml(labelA) + ' A ' + _escapeXml(vdivAStr) + '</span>');
            parts.push('<span class="graph-label"><span class="graph-swatch" style="background:' + colorB + '"></span>' + _escapeXml(labelB) + ' B ' + _escapeXml(vdivBStr) + '</span>');
            if (tdivStr) parts.push('<span class="graph-label graph-label-time">Time ' + _escapeXml(tdivStr) + '</span>');
        } else {
            var ch = getCurrentSingleChannel();
            var label = getSignalLabel(ch);
            var color = getSignalColor(ch);
            var vdiv = _getVdivForSignal(ch);
            var vdivStr = vdiv > 0 ? fmtVolt(vdiv) : '';
            parts.push('<span class="graph-label"><span class="graph-swatch" style="background:' + color + '"></span>' + _escapeXml(label) + ' ' + _escapeXml(vdivStr) + '</span>');
            if (tdivStr) parts.push('<span class="graph-label graph-label-time">Time ' + _escapeXml(tdivStr) + '</span>');
        }
        el.innerHTML = parts.join(' ');
    }

    function renderCursorGrid() {
        if (!cursorGrid) return;
        var parts = [];
        var hDivs = 14, hSub = 5;
        var vDivs = 8, vSub = 5;
        var hSteps = hDivs * hSub;
        var vSteps = vDivs * vSub;
        var centerH = Math.floor(hSteps / 2);
        var centerV = Math.floor(vSteps / 2);
        for (var i = 0; i <= hSteps; i++) {
            var isCenter = (i === centerH);
            var isMajor = (i % hSub === 0) && !isCenter;
            var color = isCenter ? CENTER_LINE_COLOR : (isMajor ? '#555566' : '#25252E');
            var width = isCenter ? 0.8 : (isMajor ? 0.5 : 0.25);
            var x = PLOT_L + ((PLOT_R - PLOT_L) * i) / hSteps;
            parts.push('<line x1="' + x + '" y1="' + PLOT_T + '" x2="' + x + '" y2="' + PLOT_B + '" stroke="' + color + '" stroke-width="' + width + '"></line>');
        }
        for (var j = 0; j <= vSteps; j++) {
            var isCenter = (j === centerV);
            var isMajor = (j % vSub === 0) && !isCenter;
            var color = isCenter ? CENTER_LINE_COLOR : (isMajor ? '#555566' : '#25252E');
            var width = isCenter ? 0.8 : (isMajor ? 0.5 : 0.25);
            var y = PLOT_T + ((PLOT_B - PLOT_T) * j) / vSteps;
            parts.push('<line x1="' + PLOT_L + '" y1="' + y + '" x2="' + PLOT_R + '" y2="' + y + '" stroke="' + color + '" stroke-width="' + width + '"></line>');
        }
        cursorGrid.innerHTML = parts.join('');
    }

    function voltageToSvgY(v, vMin, vMax) {
        if (!isFinite(vMin) || !isFinite(vMax) || vMax <= vMin) return (PLOT_T + PLOT_B) / 2;
        var n = clamp((v - vMin) / (vMax - vMin), 0, 1);
        return PLOT_B - n * (PLOT_B - PLOT_T);
    }

    function renderCursorWave() {
        if (!cursorWavePath) return;
        if (cursorPlotPoints.length) {
            var ch = cursorMode === 'dual' ? getCurrentSignalA() : getCurrentSingleChannel();
            var range = _getVoltageRangeForSignal(ch);
            var vMin = range.vMin, vMax = range.vMax;
            var sigLabelA = getSignalLabel(ch);
            var vdivA = _getVdivForSignal(ch);
            console.log('[CURSOR] renderCursorWave signal=' + sigLabelA + ' ch=' + ch + ' vdiv=' + fmtVolt(vdivA) + ' vRange=[' + vMin.toFixed(4) + ',' + vMax.toFixed(4) + '] firstPoint=' + (cursorPlotPoints.length ? cursorPlotPoints[0].v.toFixed(4) : 'none') + ' y=' + voltageToSvgY(cursorPlotPoints.length ? cursorPlotPoints[0].v : 0, vMin, vMax).toFixed(1));
            var d = cursorPlotPoints.map(function (p, i) {
                return (i === 0 ? 'M' : 'L') + ' ' + timeToSvgX(p.t) + ' ' + voltageToSvgY(p.v, vMin, vMax);
            }).join(' ');
            cursorWavePath.setAttribute('d', d);
            cursorWavePath.style.stroke = getSignalColor(ch);
            cursorWavePath.style.display = '';
        } else {
            cursorWavePath.style.display = 'none';
        }
    }

    function renderCursorWaveB() {
        if (!cursorWavePathB) return;
        if (cursorPlotPointsB && cursorPlotPointsB.length) {
            var sigB = getCurrentSignalB();
            var range = cursorMode === 'dual' ? _getVoltageRangeForSignal(sigB) : { vMin: cursorVoltageMin, vMax: cursorVoltageMax };
            var vMin = range.vMin, vMax = range.vMax;
            var sigLabelB = getSignalLabel(sigB);
            var vdivB = _getVdivForSignal(sigB);
            console.log('[CURSOR] renderCursorWaveB signal=' + sigLabelB + ' vdiv=' + fmtVolt(vdivB) + ' vRange=[' + vMin.toFixed(4) + ',' + vMax.toFixed(4) + '] firstPoint=' + cursorPlotPointsB[0].v.toFixed(4) + ' y=' + voltageToSvgY(cursorPlotPointsB[0].v, vMin, vMax).toFixed(1));
            var d = cursorPlotPointsB.map(function (p, i) {
                return (i === 0 ? 'M' : 'L') + ' ' + timeToSvgX(p.t) + ' ' + voltageToSvgY(p.v, vMin, vMax);
            }).join(' ');
            cursorWavePathB.setAttribute('d', d);
            cursorWavePathB.style.stroke = getSignalColor(getCurrentSignalB());
            cursorWavePathB.style.display = '';
        } else {
            cursorWavePathB.style.display = 'none';
        }
    }

    function interpolateVAtTOn(points, t) {
        if (!points || !points.length) return 0;
        if (t <= points[0].t) return points[0].v;
        if (t >= points[points.length - 1].t) return points[points.length - 1].v;
        for (var i = 0; i < points.length - 1; i++) {
            var a = points[i], b = points[i + 1];
            if (t >= a.t && t <= b.t) {
                var span = b.t - a.t || 1;
                return a.v + (b.v - a.v) * ((t - a.t) / span);
            }
        }
        return points[points.length - 1].v;
    }

    function updateCursorOverlay() {
        if (!cursorSvg || !cursorT1Input || !cursorT2Input) return;
        var t1 = Number.parseFloat(cursorT1Input.value || '0');
        var t2 = Number.parseFloat(cursorT2Input.value || '0');
        var t1x = timeToSvgX(t1), t2x = timeToSvgX(t2);
        var ptsA = cursorMode === 'dual' ? cursorPlotPoints : cursorPlotPoints;
        var ptsB = cursorMode === 'dual' ? cursorPlotPointsB : cursorPlotPoints;
        var rangeA, rangeB;
        if (cursorMode === 'dual') {
            rangeA = _getVoltageRangeForSignal(getCurrentSignalA());
            rangeB = _getVoltageRangeForSignal(getCurrentSignalB());
        } else {
            rangeA = _getVoltageRangeForSignal(getCurrentSingleChannel());
            rangeB = rangeA;
        }
        var t1y = voltageToSvgY(interpolateVAtTOn(ptsA, t1), rangeA.vMin, rangeA.vMax);
        var t2y = voltageToSvgY(interpolateVAtTOn(ptsB, t2), rangeB.vMin, rangeB.vMax);
        console.log('[CURSOR] overlay t1=' + t1.toFixed(6) + ' t1y=' + t1y.toFixed(1) + ' rangeA=[' + rangeA.vMin.toFixed(4) + ',' + rangeA.vMax.toFixed(4) + '] t2=' + t2.toFixed(6) + ' t2y=' + t2y.toFixed(1) + ' rangeB=[' + rangeB.vMin.toFixed(4) + ',' + rangeB.vMax.toFixed(4) + ']');

        [cursorLineT1, cursorHandleT1, cursorLabelT1, t1x, t1y].forEach(function (el, idx) {
            if (idx === 0 && el) { el.setAttribute('x1', t1x); el.setAttribute('x2', t1x); }
            if (idx === 1 && el) { el.setAttribute('cx', t1x); el.setAttribute('cy', t1y); }
            if (idx === 2 && el) el.setAttribute('x', t1x);
        });
        [cursorLineT2, cursorHandleT2, cursorLabelT2, t2x, t2y].forEach(function (el, idx) {
            if (idx === 0 && el) { el.setAttribute('x1', t2x); el.setAttribute('x2', t2x); }
            if (idx === 1 && el) { el.setAttribute('cx', t2x); el.setAttribute('cy', t2y); }
            if (idx === 2 && el) el.setAttribute('x', t2x);
        });
        if (cursorDotT1) { cursorDotT1.setAttribute('cx', t1x); cursorDotT1.setAttribute('cy', t1y); }
        if (cursorDotT2) { cursorDotT2.setAttribute('cx', t2x); cursorDotT2.setAttribute('cy', t2y); }
    }

    function handleCursorMove(clientX) {
        if (!activeCursorKey || !cursorSvg || !cursorT1Input || !cursorT2Input) return;
        var rect = cursorSvg.getBoundingClientRect();
        if (!rect.width) return;
        var leftPx = rect.left + (PLOT_L / SVG_W) * rect.width;
        var rightPx = rect.left + (PLOT_R / SVG_W) * rect.width;
        var pct = ((clientX - leftPx) / (rightPx - leftPx)) * 100;
        var tv = formatTime(percentToTime(pct));
        if (activeCursorKey === 't1') cursorT1Input.value = tv;
        else if (activeCursorKey === 't2') cursorT2Input.value = tv;
        updateCursorOverlay();
    }

    function initCursorGraph() {
        cursorGraph = document.getElementById('cursorGraph');
        cursorForm = document.querySelector('#module-cursor form');
        cursorT1Input = cursorForm && cursorForm.querySelector('input[name="cursor_t1"]');
        cursorT2Input = cursorForm && cursorForm.querySelector('input[name="cursor_t2"]');
        cursorMode = getCurrentMode();
        // Sync visible channel select into hidden form input + auto-submit
        var chSelect = document.querySelector('select[name="cursor_channel"]');
        var chHidden = cursorForm && cursorForm.querySelector('input[name="cursor_channel"]');
        if (chSelect && chHidden) {
            chHidden.value = chSelect.value;
            chSelect.addEventListener('change', function () {
                chHidden.value = chSelect.value;
                submitModuleForm(cursorForm).catch(function (err) { console.error(err); });
            });
        }
        // Sync visible mode select into hidden form input + auto-submit
        var modeSelect = document.querySelector('select[name="cursor_mode"]');
        var modeHidden = cursorForm && cursorForm.querySelector('input[name="cursor_mode"]');
        if (modeSelect && modeHidden) {
            modeHidden.value = modeSelect.value;
            modeSelect.addEventListener('change', function () {
                modeHidden.value = modeSelect.value;
                toggleCursorMode(modeSelect.value);
                submitModuleForm(cursorForm).catch(function (err) { console.error(err); });
            });
            toggleCursorMode(modeSelect.value);
        }
        // Sync visible signal A select + auto-submit
        var sigASelect = document.querySelector('select[name="cursor_signal_a"]');
        var sigAHidden = cursorForm && cursorForm.querySelector('input[name="cursor_signal_a"]');
        if (sigASelect && sigAHidden) {
            sigAHidden.value = sigASelect.value;
            sigASelect.addEventListener('change', function () {
                sigAHidden.value = sigASelect.value;
                submitModuleForm(cursorForm).catch(function (err) { console.error(err); });
            });
        }
        // Sync visible signal B select + auto-submit
        var sigBSelect = document.querySelector('select[name="cursor_signal_b"]');
        var sigBHidden = cursorForm && cursorForm.querySelector('input[name="cursor_signal_b"]');
        if (sigBSelect && sigBHidden) {
            sigBHidden.value = sigBSelect.value;
            sigBSelect.addEventListener('change', function () {
                sigBHidden.value = sigBSelect.value;
                submitModuleForm(cursorForm).catch(function (err) { console.error(err); });
            });
        }
        cursorSvg = cursorGraph && cursorGraph.querySelector('.cursor-svg');
        cursorGrid = document.getElementById('cursorGrid');
        cursorWavePath = document.getElementById('cursorWavePath');
        cursorWavePathB = document.getElementById('cursorWavePathB');
        cursorLineT1 = document.getElementById('cursorLineT1');
        cursorLineT2 = document.getElementById('cursorLineT2');
        cursorHandleT1 = document.getElementById('cursorHandleT1');
        cursorHandleT2 = document.getElementById('cursorHandleT2');
        cursorLabelT1 = document.getElementById('cursorLabelT1');
        cursorLabelT2 = document.getElementById('cursorLabelT2');
        cursorDotT1 = document.getElementById('cursorDotT1');
        cursorDotT2 = document.getElementById('cursorDotT2');
        var dataEl = document.getElementById('cursorPlotData');
        cursorPlotPoints = dataEl ? JSON.parse(dataEl.textContent || '[]') : [];
        var dataElB = document.getElementById('cursorPlotDataB');
        try { cursorPlotPointsB = dataElB ? JSON.parse(dataElB.textContent || '[]') : []; } catch(e) { cursorPlotPointsB = []; }
        if (!cursorPlotPointsB || !Array.isArray(cursorPlotPointsB)) cursorPlotPointsB = [];
        if (cursorGraph) {
            cursorTimeMin = Number.parseFloat(cursorGraph.dataset.timeMin || '0');
            cursorTimeMax = Number.parseFloat(cursorGraph.dataset.timeMax || '1');
            cursorVoltageMin = Number.parseFloat(cursorGraph.dataset.voltageMin || '-1');
            cursorVoltageMax = Number.parseFloat(cursorGraph.dataset.voltageMax || '1');
            cursorVdivCh1 = Number.parseFloat(cursorGraph.dataset.vdivCh1 || '0.1');
            cursorVdivCh2 = Number.parseFloat(cursorGraph.dataset.vdivCh2 || '1');
        }
        renderCursorGrid();
        renderCursorLegend();
        renderCursorWave();
        renderCursorWaveB();
        updateCursorOverlay();
    }

    function toggleCursorMode(mode) {
        cursorMode = mode;
        var singleEls = document.querySelectorAll('.cursor-single-only');
        var dualEls = document.querySelectorAll('.cursor-dual-only');
        if (mode === 'dual') {
            singleEls.forEach(function (el) { el.style.display = 'none'; });
            dualEls.forEach(function (el) { el.style.display = ''; });
        } else {
            singleEls.forEach(function (el) { el.style.display = ''; });
            dualEls.forEach(function (el) { el.style.display = 'none'; });
        }
        renderCursorLegend();
        renderCursorWave();
        renderCursorWaveB();
    }

    /* ===== DOWNLOAD HANDLING (PyWeb) ===== */
    async function blobToBase64(blob) {
        return new Promise(function (resolve, reject) {
            var reader = new FileReader();
            reader.onloadend = function () {
                var result = String(reader.result || '');
                var idx = result.indexOf('base64,');
                if (idx === -1) { reject(new Error('Unable to encode download.')); return; }
                resolve(result.slice(idx + 7));
            };
            reader.onerror = function () { reject(new Error('Unable to read download blob.')); };
            reader.readAsDataURL(blob);
        });
    }

    /* ===== EVENT BINDING ===== */
    function init() {
        // Sidebar navigation
        document.addEventListener('click', function (e) {
            var item = e.target.closest('.sidebar-item[data-panel]');
            if (item) {
                e.preventDefault();
                activatePanel(item.getAttribute('data-panel'));
                return;
            }
            var filterBtn = e.target.closest('.filtro[data-target]');
            if (filterBtn) {
                e.preventDefault();
                activateFilter(filterBtn.getAttribute('data-target'));
                return;
            }
        });

        // File upload widget — channel name modal + auto-submit
        (function() {
            var form = document.getElementById('upload-file-form');
            var fileInput = document.getElementById('file');
            var dropzone = document.getElementById('file-dropzone');
            var modal = document.getElementById('channelModal');
            var modalCh1 = document.getElementById('modal-ch1');
            var modalCh2 = document.getElementById('modal-ch2');
            var modalInvertCh1 = document.getElementById('modal-invert-ch1');
            var modalInvertCh2 = document.getElementById('modal-invert-ch2');
            var modalContinue = document.getElementById('modal-continue');
            var modalCancel = document.getElementById('modal-cancel');
            if (!form || !fileInput || !dropzone || !modal) return;

            function showModal() {
                if (modal.getAttribute('aria-hidden') === 'false') return;
                // Pre-fill from existing page state (set by server via data attributes)
                var state = document.getElementById('pageState');
                modalCh1.value = state ? state.getAttribute('data-ch1-name') || 'CH1' : 'CH1';
                modalCh2.value = state ? state.getAttribute('data-ch2-name') || 'CH2' : 'CH2';
                modalInvertCh1.checked = false;
                modalInvertCh2.checked = false;
                modal.setAttribute('aria-hidden', 'false');
            }

            function hideModal() { modal.setAttribute('aria-hidden', 'true'); }

            function doSubmit() {
                hideModal();
                showLoadingOverlay();
                // Strip old hidden inputs
                form.querySelectorAll('.ch-name-input').forEach(function(el) { el.remove(); });
                // Add hidden inputs with chosen names
                var h1 = document.createElement('input');
                h1.type = 'hidden'; h1.name = 'ch1_name'; h1.className = 'ch-name-input';
                h1.value = modalCh1.value.trim() || 'CH1';
                form.appendChild(h1);
                var h2 = document.createElement('input');
                h2.type = 'hidden'; h2.name = 'ch2_name'; h2.className = 'ch-name-input';
                h2.value = modalCh2.value.trim() || 'CH2';
                form.appendChild(h2);
                // Add invert flags
                var inv1 = document.createElement('input');
                inv1.type = 'hidden'; inv1.name = 'invert_ch1'; inv1.className = 'ch-name-input';
                inv1.value = modalInvertCh1.checked ? 'on' : '';
                form.appendChild(inv1);
                var inv2 = document.createElement('input');
                inv2.type = 'hidden'; inv2.name = 'invert_ch2'; inv2.className = 'ch-name-input';
                inv2.value = modalInvertCh2.checked ? 'on' : '';
                form.appendChild(inv2);
                // Submit via hidden btn so name=upload-file is included
                var btn = form.querySelector('.file-submit-btn');
                if (btn) { btn.click(); } else { form.submit(); }
            }

            function onFileSelected() {
                if (fileInput.files.length) {
                    showModal();
                }
            }

            fileInput.addEventListener('change', onFileSelected);

            modalContinue.addEventListener('click', doSubmit);

            modalCancel.addEventListener('click', function() {
                hideModal();
                fileInput.value = '';
            });

            // Also allow Enter key in modal inputs to submit
            modalCh1.addEventListener('keydown', function(e) { if (e.key === 'Enter') { e.preventDefault(); doSubmit(); } });
            modalCh2.addEventListener('keydown', function(e) { if (e.key === 'Enter') { e.preventDefault(); doSubmit(); } });
            // Escape closes modal (strips file selection)
            modal.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') {
                    e.preventDefault();
                    hideModal();
                    fileInput.value = '';
                }
            });

            // Global drag & drop — anywhere on the page
            var dragOverlay = null;

            function ensureDragOverlay() {
                if (dragOverlay) return dragOverlay;
                dragOverlay = document.createElement('div');
                dragOverlay.id = 'global-drag-overlay';
                dragOverlay.innerHTML =
                    '<div class="drag-overlay-body">' +
                        '<svg class="drag-overlay-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">' +
                            '<path d="M12 2v20M16 6v12M8 6v12M20 10v4M4 10v4"/>' +
                        '</svg>' +
                        '<span class="drag-overlay-text">Drop your .wav file anywhere to import</span>' +
                    '</div>';
                document.body.appendChild(dragOverlay);
                return dragOverlay;
            }

            function showDragFeedback() {
                dropzone.classList.add('drag-over');
                ensureDragOverlay().classList.add('active');
            }

            function hideDragFeedback() {
                dropzone.classList.remove('drag-over');
                if (dragOverlay) dragOverlay.classList.remove('active');
            }

            document.addEventListener('dragenter', function (e) {
                e.preventDefault();
                e.stopPropagation();
                showDragFeedback();
            }, false);

            document.addEventListener('dragover', function (e) {
                e.preventDefault();
            }, false);

            document.addEventListener('dragleave', function (e) {
                // Only act when the cursor truly leaves the document
                // (relatedTarget is null or outside the document)
                if (!e.relatedTarget || !document.body.contains(e.relatedTarget)) {
                    e.preventDefault();
                    e.stopPropagation();
                    hideDragFeedback();
                }
            }, false);

            document.addEventListener('drop', function (e) {
                e.preventDefault();
                e.stopPropagation();
                hideDragFeedback();
                var files = e.dataTransfer && e.dataTransfer.files;
                if (files && files.length) {
                    var f = files[0];
                    if (f.name && f.name.toLowerCase().endsWith('.wav')) {
                        fileInput.files = files;
                        showModal();
                    }
                }
            }, false);
        })();

        // Module forms - AJAX submit
        document.addEventListener('submit', function (e) {
            var form = e.target;
            if (!(form instanceof HTMLFormElement)) return;
            if (form.classList.contains('download') || form.classList.contains('no-ajax')) return;
            if (form.method && form.method.toUpperCase() === 'POST' && form.closest('#modulePanel')) {
                e.preventDefault();
                submitModuleForm(form).catch(function (err) {
                    console.error(err);
                    showToast(err.message || 'Action failed.', 'error');
                });
                return;
            }
            // Regular forms that reload the page
            localStorage.setItem('scrollY', window.scrollY);
            showLoadingOverlay();
        });

        // Download forms - capture for PyWeb
        document.querySelectorAll('form.download').forEach(function (form) {
            form.addEventListener('submit', async function (e) {
                if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.save_download) return;
                e.preventDefault();
                try {
                    var response = await fetch(form.action, { credentials: 'same-origin' });
                    if (!response.ok) {
                        var msg = await response.text();
                        throw new Error(msg || 'Download failed (' + response.status + ').');
                    }
                    var blob = await response.blob();
                    var b64 = await blobToBase64(blob);
                    var disp = response.headers.get('Content-Disposition') || '';
                    var utf8Match = disp.match(/filename\*=UTF-8''([^;]+)/i);
                    var plainMatch = disp.match(/filename="?([^";]+)"?/i);
                    var fname = utf8Match
                        ? decodeURIComponent(utf8Match[1])
                        : (plainMatch ? plainMatch[1] : 'download.bin');
                    var result = await window.pywebview.api.save_download(fname, b64);
                    if (!result || !result.ok) throw new Error((result && result.message) || 'Download failed.');
                    showToast('Download completed.', 'success');
                } catch (err) {
                    console.error(err);
                    showToast(err.message || 'Download failed.', 'error');
                }
            });
        });

        // Graph download buttons — use PyWebView native API when available
        document.querySelectorAll('a.graph-dl-btn[href]').forEach(function (link) {
            link.addEventListener('click', async function (e) {
                if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.save_download) return;
                e.preventDefault();
                try {
                    var response = await fetch(link.href, { credentials: 'same-origin' });
                    if (!response.ok) { var msg = await response.text(); throw new Error(msg || 'Download failed (' + response.status + ').'); }
                    var blob = await response.blob();
                    var b64 = await blobToBase64(blob);
                    var disp = response.headers.get('Content-Disposition') || '';
                    var utf8Match = disp.match(/filename\*=UTF-8''([^;]+)/i);
                    var plainMatch = disp.match(/filename="?([^";]+)"?/i);
                    var fname = utf8Match ? decodeURIComponent(utf8Match[1]) : (plainMatch ? plainMatch[1] : 'graph.png');
                    var result = await window.pywebview.api.save_download(fname, b64);
                    if (!result || !result.ok) throw new Error((result && result.message) || 'Download failed.');
                    showToast('Download completed.', 'success');
                } catch (err) {
                    console.error(err);
                    showToast(err.message || 'Download failed.', 'error');
                }
            });
        });

        // Cursor pointer events
        document.addEventListener('pointerdown', function (e) {
            var target = e.target.closest('#cursorHandleT1, #cursorHandleT2, #cursorLineT1, #cursorLineT2');
            if (!target) return;
            activeCursorKey = target.id.endsWith('T1') ? 't1' : 't2';
            handleCursorMove(e.clientX);
            e.preventDefault();
        });

        window.addEventListener('pointermove', function (e) {
            if (!activeCursorKey) return;
            handleCursorMove(e.clientX);
        });

        window.addEventListener('pointerup', async function (e) {
            if (!activeCursorKey || !cursorForm) { activeCursorKey = null; return; }
            handleCursorMove(e.clientX);
            activeCursorKey = null;
            try { await submitModuleForm(cursorForm); }
            catch (err) { console.error(err); showToast(err.message || 'Action failed.', 'error'); }
        });

        window.addEventListener('pointercancel', function () { activeCursorKey = null; });
    }

    // Init on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            init();
            var panel = localStorage.getItem('selectedPanel') || 'main';
            activatePanel(panel);
            var filter = localStorage.getItem('selectedFilter') || 'math';
            activateFilter(filter);
            initCursorGraph();
            var ps = document.getElementById('pageState');
            if (ps && ps.dataset.toastMessage) showToast(ps.dataset.toastMessage, ps.dataset.toastVariant || 'success');
            var sy = localStorage.getItem('scrollY');
            if (sy !== null) { window.scrollTo(0, parseInt(sy, 10)); localStorage.removeItem('scrollY'); }
        });
    } else {
        init();
        var initialPanel = localStorage.getItem('selectedPanel') || 'main';
        activatePanel(initialPanel);
        initCursorGraph();
        var initialState = document.getElementById('pageState');
        if (initialState && initialState.dataset.toastMessage) showToast(initialState.dataset.toastMessage, initialState.dataset.toastVariant || 'success');
    }

    // Expose functions globally for onclick handlers
    window.copyEndpoint = copyEndpoint;
    window.activateFilter = activateFilter;
    window.activatePanel = activatePanel;
    window.showToast = showToast;
    window.submitModuleForm = submitModuleForm;

    // Download a base64 image from the DOM by CSS selector or img element
    window.downloadImage = function(selector, filename) {
        const img = typeof selector === 'string' ? document.querySelector(selector) : selector;
        if (!img || !img.src) return;
        const a = document.createElement('a');
        a.href = img.src;
        a.download = filename || 'graph.png';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    };
})();
