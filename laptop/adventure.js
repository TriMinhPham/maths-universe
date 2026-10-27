/* Firstbot browser adventure. Progress and answers are always owned by the server. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const PENDING_KEY = 'firstbot.adventure.pending.v1';
  const palette = { L1: '#b4f3d2', L2: '#9ac9e7', L3: '#efca83', L4: '#c5afea', S: '#efb6a2' };
  let state = null;
  let view = 'map';
  let busy = false;
  let reconciliationRequired = false;
  let pending = readPending();
  let uncertainManual = Boolean(pending && !pending.payload.request_id);
  let historyBusy = false;
  let historyRequest = null;
  let historyResetQueued = false;
  let historyCursor = null;
  let historySeen = new Set();
  let parentReturnFocus = null;

  let historyGeneration = 0;

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }
  function readPending() {
    try {
      const value = JSON.parse(sessionStorage.getItem(PENDING_KEY));
      const allowed = ['/api/start', '/api/event', '/api/next', '/api/override', '/api/stars', '/api/earning'];
      return value && allowed.includes(value.path) && value.payload && typeof value.payload === 'object' ? value : null;
    } catch (_) { return null; }
  }
  function savePending(value) {
    pending = value;
    try {
      if (value) sessionStorage.setItem(PENDING_KEY, JSON.stringify(value));
      else sessionStorage.removeItem(PENDING_KEY);
    } catch (_) { /* A private browser may disable storage. Server state remains durable. */ }
  }
  function requestId() {
    if (globalThis.crypto && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
    if (!globalThis.crypto) throw new Error('This browser cannot create a safe request ID. Use a current browser.');
    const bytes = crypto.getRandomValues(new Uint8Array(24));
    return Array.from(bytes, n => n.toString(16).padStart(2, '0')).join('');
  }
  async function api(path, payload) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(path, {
        method: payload === undefined ? 'GET' : 'POST',
        headers: payload === undefined ? { Accept: 'application/json' } : { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: payload === undefined ? undefined : JSON.stringify(payload),
        credentials: 'same-origin', cache: 'no-store', signal: controller.signal
      });
      let result;
      try { result = await response.json(); }
      catch (_) { throw new Error('The server returned an unreadable response.'); }
      if (!response.ok) {
        const error = new Error(typeof result.detail === 'string' ? result.detail : `Request was not accepted (${response.status}).`);
        error.status = response.status;
        throw error;
      }
      return result;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('The connection timed out. The server may have saved this action; checking saved progress.');
      throw error;
    } finally { clearTimeout(timer); }
  }
  function validState(value) {
    if (!value || !Array.isArray(value.levels) || !value.settings || !Array.isArray(value.badges)) {
      throw new Error('The adventure returned an unexpected state. Please refresh or ask a grown-up.');
    }
    return value;
  }
  function setBusy(value) {
    busy = value;
    document.body.classList.toggle('busy', value);
    $('main').setAttribute('aria-busy', String(value));
    updateControls();
  }
  function updateControls() {
    const blocked = busy || Boolean(pending) || reconciliationRequired;
    document.querySelectorAll('[data-mutation]').forEach(button => {
      button.disabled = blocked || button.dataset.available === 'false';
    });
    for (const id of ['earning-form', 'stars-form', 'override-form']) {
      $(id).querySelector('button[type=submit]').disabled = blocked || !state || (id === 'override-form' && !$('override-stage').options.length);
    }
    $('retry-action').disabled = busy;
    $('refresh-state').disabled = busy;
    $('dismiss-uncertain').disabled = busy;
    $('continue-button').disabled = busy || !state;
  }
  function mutationButton(button, available = true) {
    button.dataset.mutation = 'true';
    button.dataset.available = String(available);
    button.disabled = busy || Boolean(pending) || reconciliationRequired || !available;
    return button;
  }
  function showError(message) {
    $('error-message').textContent = message;
    $('error-banner').hidden = false;
    $('retry-action').hidden = !pending || uncertainManual;
    $('dismiss-uncertain').hidden = !uncertainManual;
    if ($('parent-dialog').open) {
      $('parent-message').textContent = message;
      $('parent-message').classList.add('is-error');
    }
  }
  function clearError() {
    $('error-banner').hidden = true;
    $('parent-message').textContent = '';
    $('parent-message').classList.remove('is-error');
  }
  async function authoritativeState() {
    const next = validState(await api('/api/state'));
    state = next;
    render();
    // A mutation response is not enough: unlock only after authoritative GET + render.
    syncParentSettings();
    reconciliationRequired = false;
    updateControls();
    $('connection-status').textContent = 'Saved locally · Separate browser progress';
    return next;
  }
  async function refresh() {
    if (busy) return;
    setBusy(true);
    try {
      await authoritativeState();
      if (pending) showError(pendingMessage());
      else clearError();
      if ($('parent-dialog').open) await loadHistory(true);
    } catch (error) {
      $('connection-status').textContent = 'Not connected · Your saved progress stays on the server';
      showError(reconciliationRequired
        ? 'Saved, refresh required. Refresh progress before continuing. ' + error.message
        : error.message + ' Make sure the local adventure server is running.');
    } finally { setBusy(false); }
  }
  function pendingMessage() {
    return uncertainManual
      ? 'The result of the parent change is uncertain. Check refreshed settings, stars and audit history before trying again. This change will not be automatically resent. After checking, choose “I checked history” to re-enable controls.'
      : 'The last action has no confirmed response. Your current saved progress is shown. Choose “Retry same action” to safely resend its original request ID; no new attempt is created by that replay.';
  }
  async function mutate(path, payload, options = {}) {
    if (busy || pending || reconciliationRequired) return;
    if (options.idempotent !== false) payload.request_id = requestId();
    savePending({ path, payload });
    uncertainManual = options.idempotent === false;
    if (options.play) view = 'play';
    await sendPending();
  }
  async function sendPending() {
    if (busy || !pending || reconciliationRequired) return;
    const action = pending;
    setBusy(true);
    clearError();
    let accepted = false;
    try {
      await api(action.path, action.payload);
      accepted = true;
      reconciliationRequired = true;
      // Exact replay responses may be old. Always follow them with authoritative state.
      savePending(null);
      uncertainManual = false;
      await authoritativeState();
      if ($('parent-dialog').open) {
        syncParentSettings();
        $('parent-message').textContent = 'Saved. The settings and progress shown are from the server.';
        $('parent-message').classList.remove('is-error');
        await loadHistory(true);
      }
      if (view === 'play') focusPlayAfterAction();
    } catch (error) {
      if (!accepted && error.status && error.status >= 400 && error.status < 500) {
        savePending(null);
        uncertainManual = false;
      }
      try {
        await authoritativeState();
        if ($('parent-dialog').open) await loadHistory(true);
      } catch (_) { $('connection-status').textContent = 'Connection interrupted · Refresh required'; }
      const message = accepted
        ? reconciliationRequired
          ? 'Saved, refresh required. The action will not be resent. Refresh progress before continuing.'
          : 'The action was saved. Your progress has been refreshed from the server.'
        : error.message + (pending ? '\n' + pendingMessage() : ' Your saved progress has been refreshed when possible.');
      showError(message);
    } finally { setBusy(false); }
  }
  function focusPlayAfterAction() {
    requestAnimationFrame(() => {
      if (!state || !state.active) return;
      if (state.active.status === 'feedback') $('next-button').focus({ preventScroll: true });
      else if (state.active.status === 'complete') $('completion-map').focus({ preventScroll: true });
      else {
        const first = $('answers').querySelector('button:not(:disabled)');
        if (first) first.focus({ preventScroll: true });
      }
    });
  }
  function showView(nextView, focus = true) {
    view = nextView;
    render();
    if (focus) {
      const target = nextView === 'play' ? $('play-title') : $('map-title');
      target.focus({ preventScroll: true });
      window.scrollTo({ top: 0, behavior: 'instant' });
    }
  }
  function render() {
    if (!state) return;
    $('loading-view').hidden = true;
    if (view === 'play' && !state.active) view = 'map';
    $('map-view').hidden = view !== 'map';
    $('play-view').hidden = view !== 'play';
    $('star-count').textContent = String(state.stars);
    $('separation-notice').textContent = state.notice || 'Browser adventure progress is separate from robot lesson history.';
    renderMap();
    renderPlay();
    populateOverride();
    if (!$('parent-dialog').open) syncParentSettings();
    updateControls();
  }
  function svgNode(tag, attributes = {}) {
    const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
    return node;
  }
  function levelIcon(id) {
    const svg = svgNode('svg', { viewBox: '0 0 40 40', 'aria-hidden': 'true' });
    const line = { fill: 'none', stroke: 'currentColor', 'stroke-width': 2.3, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' };
    if (id === 'L1') {
      [[13,13],[27,13],[13,27],[27,27]].forEach(([cx,cy]) => svg.append(svgNode('circle', { cx, cy, r: 4, fill: 'currentColor' })));
    } else if (id === 'L2') {
      svg.append(svgNode('path', { d: 'M5 31V19m30 12V19M5 24h30M8 23q12-24 24 0M14 16v8m12-8v8', ...line }));
    } else if (id === 'L3') {
      svg.append(svgNode('path', { d: 'M5 34V19h9v15m2 0V8h9v26m2 0V15h8v19M3 34h34', ...line }));
    } else if (id === 'L4') {
      svg.append(svgNode('path', { d: 'M9 30V17q0-5 11-5t11 5v13zM14 30v5m12-5v5M13 20h14M16 8h8', ...line }));
      [15,25].forEach(cx => svg.append(svgNode('circle', { cx, cy: 26, r: 1.7, fill: 'currentColor' })));
    } else {
      svg.append(svgNode('circle', { cx: 12, cy: 14, r: 7, ...line }), svgNode('path', { d: 'm28 9 8 14H20zM10 26h12v11H10z', ...line }));
    }
    return svg;
  }
  function renderMap() {
    const active = state.active;
    $('resume-card').hidden = !active || active.status === 'complete';
    if (active) {
      $('resume-title').textContent = active.title;
      $('resume-description').textContent = `${active.completed_count} of ${active.total_count} problems complete. Your exact problem and choices are saved.`;
    }
    $('level-map').replaceChildren();
    for (const [index, level] of state.levels.entries()) {
      const optional = level.id === 'S';
      const article = element('article', `level-card${optional ? ' optional-level' : ''}`);
      article.style.setProperty('--level-color', palette[level.id] || palette.L1);
      if (!(level.stages || []).some(stage => stage.unlocked)) article.classList.add('is-locked');
      const heading = element('div', 'level-heading-block');
      const header = element('div', 'level-header');
      const icon = element('div', 'level-icon');
      icon.append(levelIcon(level.id));
      const labels = element('div');
      labels.append(element('p', 'level-kicker', optional ? 'Optional side quest' : `Chapter ${String(index + 1).padStart(2, '0')}`), element('h3', 'level-title', level.title));
      header.append(icon, labels);
      heading.append(header, element('p', 'level-description', level.description));
      article.append(heading);
      const stages = element('div', 'stage-list');
      for (const [stageIndex, stage] of (level.stages || []).entries()) stages.append(stageButton(stage, stageIndex + 1, false));
      if (level.boss) stages.append(stageButton(level.boss, '✦', true));
      article.append(stages);
      $('level-map').append(article);
    }
    $('badges').replaceChildren();
    for (const level of state.levels) {
      const earned = state.badges.includes(level.id);
      const badge = element('div', `badge${earned ? ' earned' : ''}`);
      badge.setAttribute('aria-label', `${level.title}: ${earned ? 'completion badge earned' : 'badge not yet earned'}`);
      badge.append(element('span', 'badge-medal', earned ? '★' : '✧'), element('span', 'badge-label', level.title));
      $('badges').append(badge);
    }
  }
  function stageButton(stage, number, boss) {
    const current = state.active && state.active.status !== 'complete' && state.active.stage_id === stage.id;
    const otherActive = state.active && state.active.status !== 'complete' && !current;
    const button = element('button', `stage-button${boss ? ' boss-button' : ''}${stage.completed ? ' completed' : ''}${current ? ' active' : ''}`);
    button.type = 'button';
    const copy = element('span', 'stage-copy');
    copy.append(element('strong', '', stage.title || 'Friendly boss'));
    let label;
    if (current) label = 'In progress · continue';
    else if (stage.completed) label = 'Completed · practise again';
    else if (stage.overridden) label = 'Opened by parent · not earned completion';
    else if (!stage.unlocked) label = boss ? 'Complete the stages above to unlock' : 'Locked · follow the adventure path';
    else label = boss ? 'Ready for a friendly challenge' : (stage.description || 'Two challenges · three problems each');
    if (otherActive && stage.unlocked) label += ' · finish your current stage first';
    copy.append(element('small', '', label));
    const available = current || (Boolean(stage.unlocked) && !otherActive);
    mutationButton(button, available);
    button.setAttribute('aria-label', `${stage.title || 'Friendly boss'}. ${label}`);
    button.append(element('span', 'stage-number', stage.completed ? '✓' : !stage.unlocked && !current ? '·' : number), copy, element('span', 'stage-end', current || available ? '→' : '⌑'));
    button.addEventListener('click', () => {
      if (current) showView('play');
      else mutate('/api/start', { stage_id: stage.id }, { play: true });
    });
    return button;
  }
  function dots(amount, compact = false, crossed = 0) {
    const group = element('div', `dots-group${compact ? ' compact' : ''}`);
    group.setAttribute('aria-hidden', 'true');
    group.style.gridTemplateColumns = `repeat(${Math.max(1, Math.min(compact ? 4 : 5, amount))}, ${compact ? 'var(--compact-dot-size, 16px)' : '22px'})`;
    if (amount === 0) group.append(element('span', 'empty-zero', 'none'));
    for (let i = 0; i < amount; i++) group.append(element('span', `dot${i >= amount - crossed ? ' crossed' : ''}`));
    return group;
  }
  function renderScene(scene) {
    const visual = $('problem-visual');
    visual.replaceChildren();
    if (scene.kind === 'count') {
      $('problem-prompt').textContent = 'How many dots can you find?';
      visual.setAttribute('role', 'group');
      visual.setAttribute('aria-label', 'Dots to count. Each dot is shown below.');
      // Individual accessible dots allow a screen-reader user to count without revealing a total.
      const group = dots(scene.a);
      group.removeAttribute('aria-hidden');
      [...group.children].forEach(dot => { dot.setAttribute('role', 'img'); dot.setAttribute('aria-label', 'dot'); });
      visual.append(group);
    } else if (scene.kind === 'shape') {
      const names = { 0: 'circle', 3: 'triangle', 4: 'square' };
      const name = names[scene.a];
      $('problem-prompt').textContent = `How many straight sides does a ${name} have?`;
      visual.setAttribute('role', 'img');
      visual.setAttribute('aria-label', `A ${name}`);
      const svg = svgNode('svg', { viewBox: '0 0 120 120', class: 'shape-visual', 'aria-hidden': 'true' });
      const attrs = { fill: '#b4f3d218', stroke: 'currentColor', 'stroke-width': 5, 'stroke-linejoin': 'round' };
      svg.append(scene.a === 0 ? svgNode('circle', { cx: 60, cy: 60, r: 46, ...attrs }) : scene.a === 3 ? svgNode('path', { d: 'M60 12 111 102H9Z', ...attrs }) : svgNode('rect', { x: 15, y: 15, width: 90, height: 90, rx: 2, ...attrs }));
      visual.append(svg);
    } else {
      const plus = scene.kind === 'add';
      $('problem-prompt').textContent = plus ? 'Let’s put them together.' : 'What is left when we take some away?';
      visual.setAttribute('role', 'img');
      visual.setAttribute('aria-label', `${scene.a} ${plus ? 'plus' : 'minus'} ${scene.b} equals what?`);
      const equation = element('div', 'arithmetic-visual');
      equation.setAttribute('aria-hidden', 'true');
      const left = element('div', 'operand');
      left.append(element('span', 'operand-value', scene.a), dots(scene.a, true, plus ? 0 : scene.b));
      const right = element('div', 'operand');
      right.append(element('span', 'operand-value', scene.b));
      if (plus) right.append(dots(scene.b, true));
      equation.append(left, element('span', 'equation-symbol', plus ? '+' : '−'), right, element('span', 'equation-symbol', '='), element('span', 'equation-question', '?'));
      visual.append(equation);
    }
  }
  function renderPlay() {
    const active = state.active;
    if (!active) return;
    $('play-title').textContent = active.title;
    $('play-kind').textContent = active.is_boss ? 'Friendly boss' : 'Practice adventure';
    $('challenge-label').textContent = active.is_boss ? 'A FAMILIAR LITTLE CHALLENGE' : `CHALLENGE ${Math.min(active.challenge_index + 1, active.challenge_count)} OF ${active.challenge_count}`;
    $('progress-label').textContent = `${active.completed_count} / ${active.total_count} complete`;
    $('run-progress').setAttribute('aria-valuemax', String(active.total_count));
    $('run-progress').setAttribute('aria-valuenow', String(active.completed_count));
    $('progress-fill').style.width = `${Math.max(0, Math.min(100, 100 * active.completed_count / Math.max(1, active.total_count)))}%`;
    const complete = active.status === 'complete';
    $('problem-card').hidden = complete;
    $('completion-card').hidden = !complete;
    $('boss-art').hidden = !active.is_boss;
    if (complete) {
      $('completion-title').textContent = active.is_boss ? 'You did it, explorer!' : 'Another step on your adventure!';
      $('completion-message').textContent = active.is_boss ? 'Friendly boss completed. Your completion badge is on the map — see where your curiosity takes you next.' : 'Both challenges are complete. Your progress is saved. The next discovery is waiting on the map.';
      return;
    }
    const problem = active.problem;
    if (!problem || !problem.scene) {
      $('problem-prompt').textContent = 'Your saved problem could not be displayed. Refresh progress to reconnect.';
      $('problem-visual').replaceChildren();
      $('answers').replaceChildren();
      mutationButton($('next-button'), false);
      mutationButton($('reveal-button'), false);
      mutationButton($('skip-button'), false);
      return;
    }

    renderScene(problem.scene);
    $('answers').replaceChildren();
    const playing = active.status === 'playing';
    for (const [index, choice] of problem.scene.choices.entries()) {
      const button = element('button', 'answer-button', choice);
      button.type = 'button';
      button.setAttribute('aria-label', `Answer ${choice}`);
      button.setAttribute('aria-keyshortcuts', String(index + 1));
      const key = element('span', 'answer-key', index + 1);
      key.setAttribute('aria-hidden', 'true');
      button.append(key);
      if (!playing && problem.answer !== null && choice === problem.answer) button.classList.add('correct-choice');
      mutationButton(button, playing);
      button.addEventListener('click', () => sendEvent('answer', choice));
      $('answers').append(button);
    }
    const feedback = problem.feedback;
    const messages = {
      correct: ['✦', 'You found it!', 'Nice exploring. Your progress is saved.'],
      incorrect: ['↻', 'Let’s try another way.', 'Take another look. You can try again or ask for help.'],
      revealed: ['♡', `The answer is ${problem.answer}.`, 'No star or completion credit for this one. Next, try the same idea with fresh choices.'],
      skipped: ['↻', 'A fresh try is waiting.', 'This one is saved as skipped, with no star or completion credit. The next problem fills the same spot.']
    };
    const [icon, title, message] = messages[feedback] || ['♡', 'Take your time.', 'Choose an answer. You can use keys 1, 2 or 3, or Tab and Enter.'];
    $('feedback').className = `feedback${feedback ? ' ' + feedback : ''}`;
    $('feedback-icon').textContent = icon;
    $('feedback-title').textContent = title;
    $('feedback-message').textContent = message;
    $('help-actions').hidden = !playing;
    $('next-button').hidden = active.status !== 'feedback';
    $('next-button').textContent = feedback === 'revealed' || feedback === 'skipped' ? 'Try again →' : active.completed_count >= active.total_count ? 'Finish →' : 'Next →';
    mutationButton($('next-button'), active.status === 'feedback');
    mutationButton($('reveal-button'), playing);
    mutationButton($('skip-button'), playing);
  }
  function sendEvent(action, choice = null) {
    if (!state || !state.active || !state.active.problem || state.active.status !== 'playing') return;
    mutate('/api/event', { problem_id: state.active.problem.id, action, choice });
  }
  function syncParentSettings() {
    if (!state) return;
    $('earning-auto').checked = state.settings.auto;
    $('earning-per-correct').value = state.settings.per_correct;
  }
  function populateOverride() {
    const previous = $('override-stage').value;
    $('override-stage').replaceChildren();
    for (const level of state.levels) {
      for (const stage of [...(level.stages || []), ...(level.boss ? [level.boss] : [])]) {
        if (!stage.unlocked && !stage.completed && !stage.overridden) {
          const option = element('option', '', `${level.title} · ${stage.title || 'Friendly boss'}`);
          option.value = stage.id;
          $('override-stage').append(option);
        }
      }
    }
    if ([...$('override-stage').options].some(option => option.value === previous)) $('override-stage').value = previous;
    $('override-stage').disabled = !$('override-stage').options.length;
  }
  function parentReason(id) {
    const reason = $(id).value.trim();
    if (!reason) throw new Error('Please add a reason so the audit history is useful.');
    return reason;
  }
  function integer(id) {
    const raw = $(id).value.trim();
    if (!/^-?\d+$/.test(raw) || !Number.isSafeInteger(Number(raw))) throw new Error('Please enter a whole number.');
    return Number(raw);
  }
  function parentForm(formId, handler) {
    $(formId).addEventListener('submit', event => {
      event.preventDefault();
      if (busy || pending || reconciliationRequired) return;
      try { handler(); }
      catch (error) { $('parent-message').textContent = error.message; $('parent-message').classList.add('is-error'); }
    });
  }
  function formatHistory(item) {
    const type = item.type || item.kind || item.action || item.event || 'Saved entry';
    const labels = { answer: 'Answer attempt', attempt: 'Answer attempt', reveal: 'Answer revealed', skip: 'Problem skipped', adjust: 'Manual star adjustment', adjustment: 'Manual star adjustment', earning: 'Earning settings', override: 'Parent override', start: 'Stage started', correct: 'Correct answer', reward: 'Stars earned', star: 'Star audit', stars: 'Star audit', next: 'Progress continued' };
    const title = Array.isArray(item.attempts) ? `Problem #${item.id} · ${item.outcome || 'in progress'}` : labels[type] || String(type).replace(/_/g, ' ');
    const details = [];
    const sources = [item];
    for (const key of ['payload', 'data', 'details']) if (item[key] && typeof item[key] === 'object') sources.push(item[key]);
    const wanted = { stage_id: 'Stage', problem_id: 'Problem', action: 'Action', choice: 'Choice', correct: 'Correct', delta: 'Star change', total: 'Star total', balance: 'Star balance', reason: 'Reason', auto: 'Automatic stars', per_correct: 'Stars per correct', outcome: 'Outcome', feedback: 'Feedback', amount: 'Stars', source: 'Source' };
    for (const source of sources) {
      for (const [key, label] of Object.entries(wanted)) {
        const value = source[key];
        if (value !== undefined && value !== null && ['string', 'number', 'boolean'].includes(typeof value)) {
          const detail = `${label}: ${value}`;
          if (!details.includes(detail)) details.push(detail);
        }
      }
    }
    // Unknown audit fields are still visible rather than silently hiding a parent adjustment.
    if (!details.length) {
      for (const [key, value] of Object.entries(item)) {
        if (!['id', 'type', 'kind', 'created_at', 'timestamp', 'ts'].includes(key) && value !== null && typeof value !== 'object') details.push(`${key.replace(/_/g, ' ')}: ${value}`);
      }
    }
    const li = element('li');
    li.append(element('strong', '', title), element('p', '', details.join('\n') || 'Recorded in the local adventure history.'));
    if (item.scene) {
      const scene = item.scene;
      const description = scene.kind === 'count' ? 'Counting dots' : scene.kind === 'shape' ? 'Straight sides of a shape' : `${scene.a} ${scene.kind === 'add' ? '+' : '−'} ${scene.b}`;
      li.append(element('p', '', description));
    }
    if (Array.isArray(item.attempts)) {
      const attempts = element('ol', 'attempt-list');
      for (const attempt of item.attempts) attempts.append(element('li', '', `Chose ${attempt.choice} · ${attempt.correct ? 'correct' : 'try again'}${attempt.created ? ' · ' + attempt.created : ''}`));
      if (item.attempts.length) li.append(attempts);
      else li.append(element('p', '', 'No answer attempts recorded.'));
    }
    const stamp = item.created_at || item.timestamp || item.ts || item.at || item.created;
    if (stamp) {
      const date = new Date(typeof stamp === 'number' ? (stamp < 1e12 ? stamp * 1000 : stamp) : stamp);
      const time = element('time', '', Number.isNaN(date.getTime()) ? String(stamp) : date.toLocaleString());
      if (!Number.isNaN(date.getTime())) time.dateTime = date.toISOString();
      li.append(time);
    }
    return li;
  }
  function loadHistory(reset = false) {
    if (historyBusy) {
      if (reset) {
        historyResetQueued = true;
        ++historyGeneration; // Discard the pre-save response, including errors.
      }
      return historyRequest;
    }
    historyBusy = true;
    historyRequest = fetchHistory(reset);
    return historyRequest;
  }
  async function fetchHistory(reset) {
    const generation = ++historyGeneration;
    $('history-refresh').disabled = true;
    $('history-more').disabled = true;
    $('history-status').textContent = 'Loading audit history…';
    if (reset) { historyCursor = null; historySeen = new Set(); $('history-list').replaceChildren(); }
    try {
      const result = await api('/api/history' + (historyCursor === null ? '' : `?before=${encodeURIComponent(historyCursor)}`));
      const items = Array.isArray(result) ? result : result.items || result.entries || result.history || result.events;
      if (!Array.isArray(items)) throw new Error('The server returned an unsupported history format.');
      if (generation !== historyGeneration) return;
      for (const [field, id, type] of [['star_audit', 'star-audit-list', 'stars'], ['settings_audit', 'settings-audit-list', 'earning'], ['override_audit', 'override-audit-list', 'override']]) {
        const rows = result[field];
        if (Array.isArray(rows)) {
          $(id).replaceChildren();
          for (const row of rows) $(id).append(formatHistory({ ...row, type }));
          if (!rows.length) $(id).append(element('li', '', 'No records yet.'));
        }
      }
      for (const item of items) {
        const key = `${item.type || item.kind || ''}:${item.id || JSON.stringify(item)}`;
        if (!historySeen.has(key)) { $('history-list').append(formatHistory(item)); historySeen.add(key); }
      }
      const cursor = Array.isArray(result) ? null : result.next_before ?? result.next_cursor ?? result.before ?? null;
      const hasMore = !Array.isArray(result) && (result.has_more !== undefined ? Boolean(result.has_more) : cursor !== null);
      if (hasMore && (cursor === null || String(cursor) === String(historyCursor))) throw new Error('History pagination did not provide a new cursor. Refresh history before continuing.');
      historyCursor = cursor;
      $('history-more').hidden = !hasMore;
      $('history-status').textContent = !historySeen.size ? 'No history yet. Your first discovery can start on the map.' : hasMore ? 'Newest entries shown. Earlier entries are available below.' : 'All available entries are shown.';
    } catch (error) {
      if (generation === historyGeneration) $('history-status').textContent = `History could not be loaded: ${error.message}`;
    } finally {
      historyBusy = false;
      if (historyResetQueued) {
        historyResetQueued = false;
        await loadHistory(true);
      } else {
        $('history-refresh').disabled = false;
        $('history-more').disabled = false;
      }
    }
  }

  $('continue-button').addEventListener('click', () => showView('play'));
  $('pause-button').addEventListener('click', () => showView('map'));
  $('completion-map').addEventListener('click', () => showView('map'));
  $('reveal-button').addEventListener('click', () => sendEvent('reveal'));
  $('skip-button').addEventListener('click', () => sendEvent('skip'));
  $('next-button').addEventListener('click', () => mutate('/api/next', {}));
  $('retry-action').addEventListener('click', () => { if (!uncertainManual) sendPending(); });
  $('refresh-state').addEventListener('click', refresh);
  $('dismiss-uncertain').addEventListener('click', () => {
    if (busy || !uncertainManual) return;
    savePending(null); uncertainManual = false; clearError(); updateControls();
  });
  $('parent-open').addEventListener('click', () => {
    parentReturnFocus = document.activeElement;
    syncParentSettings();
    if (!$('parent-dialog').open) $('parent-dialog').showModal();
    if (pending) { $('parent-message').textContent = pendingMessage(); $('parent-message').classList.add('is-error'); }
    loadHistory(true);
  });
  $('parent-close').addEventListener('click', () => $('parent-dialog').close());
  $('parent-dialog').addEventListener('close', () => { if (parentReturnFocus) parentReturnFocus.focus(); });
  $('history-refresh').addEventListener('click', () => loadHistory(true));
  $('history-more').addEventListener('click', () => loadHistory(false));
  $('stars-mode').addEventListener('change', () => {
    const total = $('stars-mode').value === 'total';
    $('stars-value-label').firstChild.textContent = total ? 'New total' : 'Amount (use − to remove)';
    if (total) $('stars-value').min = '0'; else $('stars-value').removeAttribute('min');
  });
  parentForm('earning-form', () => {
    const perCorrect = integer('earning-per-correct');
    if (perCorrect < 0 || perCorrect > 5) throw new Error('Stars per correct answer must be between 0 and 5.');
    mutate('/api/earning', { auto: $('earning-auto').checked, per_correct: perCorrect, reason: parentReason('earning-reason') }, { idempotent: false });
  });
  parentForm('stars-form', () => {
    const amount = integer('stars-value');
    const isTotal = $('stars-mode').value === 'total';
    if (isTotal && amount < 0) throw new Error('The star total cannot be negative.');
    mutate('/api/stars', { delta: isTotal ? null : amount, total: isTotal ? amount : null, reason: parentReason('stars-reason') }, { idempotent: false });
  });
  parentForm('override-form', () => {
    if (!$('override-stage').value) throw new Error('There are no locked stages available for override.');
    mutate('/api/override', { stage_id: $('override-stage').value, reason: parentReason('override-reason') });
  });
  document.addEventListener('keydown', event => {
    if (event.altKey || event.ctrlKey || event.metaKey || event.repeat || $('parent-dialog').open || busy || pending || reconciliationRequired || view !== 'play') return;
    if (['INPUT', 'SELECT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
    const index = ['1', '2', '3'].indexOf(event.key);
    if (index >= 0) {
      const choice = $('answers').children[index];
      if (choice && !choice.disabled) { event.preventDefault(); choice.click(); }
    }
  });
  window.addEventListener('online', () => { if (!busy) refresh(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden && !busy && state) refresh(); });
  refresh();
})();
