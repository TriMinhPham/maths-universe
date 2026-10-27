/* MathsPlay: deliberately authored, ungraded manipulatives. No engine/storage access. */
'use strict';
(() => {
  const NS = 'http://www.w3.org/2000/svg';
  const topics = {
    'mt_OvyoRo47K-': {title: 'Put groups together', subtitle: 'Move counters into one collection.', icon: '＋', color: '#127663', kind: 'add', a: 3, b: 2},
    'mt_ghF3Vv6taM': {title: 'Take some away', subtitle: 'Lift counters off the plate. What stays?', icon: '−', color: '#a33959', kind: 'remove', a: 5, b: 2},
    'mt_WcfaSfVT33': {title: 'Touch, count, discover', subtitle: 'Give every dot exactly one number.', icon: '●', color: '#4055a8', kind: 'count', n: 4},
    'mt_-hTTat0mBR': {title: 'A fair share', subtitle: 'Share counters between two friends.', icon: '↔', color: '#127663', kind: 'share', n: 8},
    'mt_vKcxX6iNOA': {title: 'Make a half', subtitle: 'Shade quarters and compare with a half.', icon: '½', color: '#924b10', kind: 'fraction', n: 4, target: 2, equivalent: true},
    'mt_ndGqFPWyen': {title: 'Paint equal parts', subtitle: 'Turn a whole into colourful sixths.', icon: '▦', color: '#4055a8', kind: 'fraction', n: 6, target: 2},
    'mt_bfhng6mOuy': {title: 'Shape shapeshifter', subtitle: 'Turn, resize and recolour a triangle.', icon: '△', color: '#a33959', kind: 'shape'},
    'mt_WXW0hjNhph': {title: 'Build a pattern train', subtitle: 'Add tiles. Make the same group repeat.', icon: '◯', color: '#924b10', kind: 'pattern', unit: ['circle', 'triangle', 'square'], seed: 3, length: 9}
  };
  // The keys are actual lesson IDs and zero-based question indices. Quantities are
  // authored against full_math_lessons.json, never inferred from question prose.
  // Deliberately omit questions for which this scaffold would misrepresent the task.
  const questions = {
    'mt_OvyoRo47K-': {
      0: {kind: 'add', a: 2, b: 4}, 1: {kind: 'add', a: 3, b: 2}, 2: {kind: 'add', a: 4, b: 5}
    },
    'mt_ghF3Vv6taM': {
      0: {kind: 'add', a: 2, b: 3}, 1: {kind: 'remove', a: 4, b: 1}, 2: {kind: 'remove', a: 5, b: 2}
    },
    'mt_WcfaSfVT33': {0: {kind: 'count', n: 5}, 2: {kind: 'count', n: 6}},
    'mt_-hTTat0mBR': {0: {kind: 'share', n: 10}, 2: {kind: 'share', n: 18}},
    'mt_vKcxX6iNOA': {0: {kind: 'fraction', n: 5, target: 3}},
    'mt_ndGqFPWyen': {
      0: {kind: 'fraction', n: 5, target: 1}, 1: {kind: 'fraction', n: 4, target: 3},
      2: {kind: 'fraction', n: 6, target: 2, wholeLength: 18}
    },
    'mt_bfhng6mOuy': {1: {kind: 'shape', red: true, angle: 180}},
    'mt_WXW0hjNhph': {0: {kind: 'pattern', unit: ['red', 'blue', 'blue'], seed: 7, length: 9}}
  };
  const own = (o, key) => Object.prototype.hasOwnProperty.call(o, key);
  function node(tag, text, cls) {
    const e = document.createElement(tag);
    if (text !== undefined) e.textContent = text;
    if (cls) e.className = cls;
    return e;
  }
  function svgNode(tag, attrs) {
    const e = document.createElementNS(NS, tag);
    Object.entries(attrs).forEach(([key, val]) => e.setAttribute(key, String(val)));
    return e;
  }
  function picture(shape = 'circle', color = '#187963') {
    const s = svgNode('svg', {viewBox: '0 0 64 64', 'aria-hidden': 'true', focusable: 'false'});
    const attrs = {fill: color, stroke: '#183b4b', 'stroke-width': 3};
    if (shape === 'triangle') s.append(svgNode('polygon', {...attrs, points: '32,8 57,54 7,54'}));
    else if (shape === 'square') s.append(svgNode('rect', {...attrs, x: 10, y: 10, width: 44, height: 44, rx: 3}));
    else s.append(svgNode('circle', {...attrs, cx: 32, cy: 32, r: 23}));
    return s;
  }
  function styles() {
    if (document.getElementById('mp-styles')) return;
    const s = node('style');
    s.id = 'mp-styles';
    s.textContent = `
.mp-root{box-sizing:border-box;width:100%;min-width:0;max-width:760px;margin:12px auto;padding:clamp(10px,3vw,22px);border:2px solid #cbdcdd;border-radius:22px;background:#f5faf6;color:#183b4b;font:500 16px/1.5 system-ui,sans-serif;overflow-wrap:anywhere;text-align:left;color-scheme:light}
.mp-root *{box-sizing:border-box;min-width:0}.mp-root p{margin:8px 0;color:inherit}.mp-kicker{font-size:.8rem;font-weight:800;letter-spacing:.06em;color:#42616c}.mp-objective{font-weight:700}.mp-root button{font:inherit;letter-spacing:normal;text-transform:none;min-height:48px;min-width:48px;border:2px solid #758f98;border-radius:13px;background:#fff;color:#183b4b;padding:9px 12px;cursor:pointer;box-shadow:0 2px 0 #cbdcdd;white-space:normal;line-height:1.3;touch-action:manipulation}.mp-root button:hover{background:#e4f0f1}.mp-root button:focus-visible{outline:3px solid #7849bc;outline-offset:3px}.mp-root button:disabled{opacity:.55;cursor:default}.mp-root button[aria-pressed=true]{background:#d4eee5;border-color:#12634f}.mp-row{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:10px 0}.mp-board{margin:12px 0}.mp-tray{border:2px dashed #a2b9ba;border-radius:16px;padding:10px;margin:10px 0;background:#fff}.mp-tray-label{display:block;font-size:.9rem;font-weight:750;margin-bottom:7px}.mp-tokens{display:flex;flex-wrap:wrap;gap:8px;align-items:center;min-height:54px}.mp-token{position:relative;display:inline-flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;width:52px;min-height:52px;border-radius:12px;font-weight:800}.mp-token svg{display:block;width:34px;height:34px}.mp-root button.mp-token{padding:4px}.mp-removed svg{opacity:.25}.mp-removed:after{content:'−';position:absolute;font-size:2rem;color:#91304a}.mp-number{font-size:.8rem;line-height:1.1}.mp-equation{border-radius:12px;padding:12px;background:#e5edf9;font-weight:800;font-size:1.15rem;text-align:center}.mp-feedback{min-height:2em;font-weight:650;color:#245944!important}.mp-fraction{display:grid;gap:0;border:3px solid #183b4b;border-radius:6px;overflow:hidden;max-width:360px;margin:14px auto;background:white}.mp-root .mp-part{border:1px solid #183b4b;border-radius:0;min-width:0;min-height:64px;box-shadow:none;background:#fff;padding:4px;font-weight:750}.mp-root .mp-part[aria-pressed=true]{background:#9dcbbf}.mp-part-mark{display:block;font-size:1.2rem}.mp-half{width:100%;max-width:360px;height:38px;margin:8px auto;background:linear-gradient(to right,#9dcbbf 50%,#fff 50%);border:3px solid #183b4b;position:relative}.mp-half:after{content:'';position:absolute;left:50%;top:0;height:100%;border-left:2px solid #183b4b}.mp-shape{display:block;width:100%;max-width:260px;height:auto;margin:auto}.mp-pattern-unit{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.mp-pattern-unit svg{width:32px;height:32px}.mp-train{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.mp-car{border:2px solid #a2b9ba;border-radius:12px;background:white;text-align:center;padding:5px;min-height:68px}.mp-car svg{display:block;width:32px;height:32px;margin:auto}.mp-car.mp-empty{border-style:dashed}.mp-step{padding:16px;border-left:4px solid #187963;background:white;border-radius:8px;min-height:100px}.mp-root [hidden]{display:none!important}@media(prefers-reduced-motion:reduce){.mp-root *{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
`;
    document.head.append(s);
  }
  function button(text, key, fn) {
    const b = node('button', text);
    b.type = 'button';
    b.dataset.mpKey = key;
    b.addEventListener('click', fn);
    return b;
  }
  function shell(container, title, question) {
    styles();
    const root = node('section', undefined, 'mp-root');
    root.setAttribute('aria-label', question ? 'Hands-on practice aid' : 'Learning playground');
    root.append(node('span', question ? 'Try it' : 'Play first', 'mp-kicker'));
    const objective = node('p', '', 'mp-objective'), board = node('div', undefined, 'mp-board');
    const equation = node('p', '', 'mp-equation'), feedback = node('p', '', 'mp-feedback');
    feedback.setAttribute('role', 'status');
    feedback.setAttribute('aria-live', 'polite');
    feedback.setAttribute('aria-atomic', 'true');
    const controls = node('div', undefined, 'mp-row');
    root.append(objective, board, equation, feedback, controls);
    container.replaceChildren(root);
    function redraw(fn) {
      const focused = root.contains(document.activeElement) ? document.activeElement.dataset.mpKey : null;
      board.replaceChildren();
      fn();
      if (focused) {
        const replacement = [...root.querySelectorAll('[data-mp-key]')].find(b => b.dataset.mpKey === focused);
        if (replacement && !replacement.disabled) replacement.focus({preventScroll: true});
        else controls.querySelector('button')?.focus({preventScroll: true});
      }
    }
    return {root, objective, board, equation, feedback, controls, redraw};
  }
  function tray(parent, label) {
    const t = node('div', undefined, 'mp-tray'), items = node('div', undefined, 'mp-tokens');
    t.append(node('span', label, 'mp-tray-label'), items);
    parent.append(t);
    return items;
  }
  function token(parent, label, key, fn, color, pressed, caption) {
    const t = fn ? button('', key, fn) : node('span');
    t.className = 'mp-token';
    if (fn) t.setAttribute('aria-label', label);
    else {t.setAttribute('role', 'img'); t.setAttribute('aria-label', label);}
    if (pressed !== undefined) t.setAttribute('aria-pressed', String(pressed));
    t.append(picture('circle', color));
    if (caption !== undefined) t.append(node('span', caption, 'mp-number'));
    parent.append(t);
    return t;
  }
  function counters(ui, c) {
    const moved = new Set();
    const add = c.kind === 'add', count = c.kind === 'count';
    const total = count ? c.n : add ? c.b : c.a;
    ui.objective.textContent = count ? 'Touch each dot. Say its number.' : add ? `Join ${c.b} blue counters to ${c.a} green counters.` : `Take ${c.b} counters away. Tap faded counters to return them.`;
    function render(message) {
      ui.redraw(() => {
        if (add) {
          const joined = tray(ui.board, 'Together'), waiting = tray(ui.board, 'Waiting to join');
          for (let i = 0; i < c.a; i++) token(joined, `Green counter ${i + 1}`, '', null, '#187963');
          for (let i = 0; i < c.b; i++) token(moved.has(i) ? joined : waiting, `${moved.has(i) ? 'Move back' : 'Join'} blue counter ${i + 1}`, `counter-${i}`, () => {moved.has(i) ? moved.delete(i) : moved.add(i); render();}, '#7499dc', moved.has(i));
          ui.equation.textContent = `${c.a} + ${c.b} = ${moved.size === c.b ? c.a + c.b : '?'}`;
          ui.feedback.textContent = message || (moved.size === c.b ? 'Together! Count the whole group to check.' : `${c.b - moved.size} blue ${c.b - moved.size === 1 ? 'counter' : 'counters'} still waiting.`);
        } else {
          const items = tray(ui.board, count ? 'One touch, one number' : 'The plate');
          for (let i = 0; i < total; i++) {
            const selected = moved.has(i);
            const t = token(items, count ? `Dot ${i + 1}${selected ? ', counted as ' + ([...moved].indexOf(i) + 1) : ', not counted'}` : `Counter ${i + 1}, ${selected ? 'taken away; tap to return' : 'on plate; tap to remove'}`, `counter-${i}`, () => {
              if (count && moved.has(i)) {ui.feedback.textContent = 'Already counted. Touch a dot without a number.'; return;}
              moved.has(i) ? moved.delete(i) : moved.add(i); render();
            }, '#187963', count ? undefined : selected, count && selected ? [...moved].indexOf(i) + 1 : undefined);
            if (selected && !count) t.classList.add('mp-removed');
          }
          ui.equation.textContent = count ? `${moved.size} ${moved.size === 1 ? 'dot' : 'dots'} counted` : `${c.a} − ${c.b} = ${moved.size === c.b ? c.a - c.b : '?'}`;
          ui.feedback.textContent = message || (count ? moved.size === total ? `The last number, ${total}, tells how many dots there are.` : 'Touch a dot without a number. Any order works.' : moved.size === c.b ? `You took away ${c.b}. Count what stays.` : moved.size > c.b ? `You took away too many for this story. Put ${moved.size - c.b} back.` : `Take away ${c.b - moved.size} more to match the story.`);
        }
      });
    }
    ui.controls.append(button('Reset', 'reset', () => {moved.clear(); render('Fresh start. Try it another way.');}));
    render();
  }
  function sharing(ui, c) {
    let places = [];
    ui.objective.textContent = `Share all ${c.n} counters equally between two friends. Tap a friend to give them one.`;
    function render(message) {
      ui.redraw(() => {
        const remaining = c.n - places.length, counts = [places.filter(x => x === 0).length, places.filter(x => x === 1).length];
        const pile = tray(ui.board, `${remaining} still to share`);
        for (let i = 0; i < remaining; i++) token(pile, 'Unshared counter', '', null, '#dba04c');
        for (let friend = 0; friend < 2; friend++) {
          const box = node('div', undefined, 'mp-tray');
          const give = button(`Give 1 to ${friend ? 'Bo' : 'Ari'} (${counts[friend]} now)`, `friend-${friend}`, () => {places.push(friend); render();});
          give.disabled = !remaining;
          const items = node('div', undefined, 'mp-tokens');
          for (let i = 0; i < counts[friend]; i++) token(items, `${friend ? 'Bo' : 'Ari'} counter ${i + 1}`, '', null, '#dba04c');
          box.append(give, items); ui.board.append(box);
        }
        const equal = !remaining && counts[0] === counts[1];
        ui.equation.textContent = equal ? `${c.n} ÷ 2 = ${counts[0]} each` : `${counts[0]} + ${counts[1]} + ${remaining} unshared = ${c.n}`;
        ui.feedback.textContent = message || (equal ? 'Both friends have the same amount. Each has half of the whole group.' : !remaining ? 'All shared, but not equally yet. Undo a move and give to the friend with fewer.' : 'Try giving one to each friend in turn. Equal shares have the same number.');
        undo.disabled = places.length === 0;
      });
    }
    const undo = button('Undo last share', 'undo', () => {places.pop(); render();});
    ui.controls.append(button('Reset', 'reset', () => {places = []; render();}), undo);
    render();
  }
  function fractions(ui, c) {
    const shaded = new Set();
    ui.objective.textContent = `Shade ${c.target} of ${c.n} equal parts. Tap again to clear.`;
    function render(message) {
      ui.redraw(() => {
        const whole = node('div', undefined, 'mp-fraction');
        whole.style.gridTemplateColumns = `repeat(${c.wholeLength ? 1 : c.n === 6 ? 3 : c.n === 4 ? 2 : 1},minmax(0,1fr))`;
        if (c.equivalent) whole.style.height = '166px';
        whole.setAttribute('role', 'group'); whole.setAttribute('aria-label', `${c.wholeLength ? 'Vertical strip' : 'One whole'} divided into ${c.n} equal parts`);
        for (let i = 0; i < c.n; i++) {
          const b = button('', `part-${i}`, () => {shaded.has(i) ? shaded.delete(i) : shaded.add(i); render();});
          b.className = 'mp-part'; b.setAttribute('aria-pressed', String(shaded.has(i)));
          b.setAttribute('aria-label', `Part ${i + 1} of ${c.n}, ${shaded.has(i) ? 'shaded' : 'unshaded'}`);
          b.append(node('span', shaded.has(i) ? '●' : '○', 'mp-part-mark'), node('span', `1/${c.n}`));
          whole.append(b);
        }
        ui.board.append(whole);
        if (c.equivalent) {
          ui.board.append(node('p', 'Compare with this same-sized whole: one half shaded.'));
          const half = node('div', undefined, 'mp-half'); half.style.height = '166px'; half.setAttribute('role', 'img'); half.setAttribute('aria-label', 'One of two equal parts shaded: one half'); ui.board.append(half);
        }
        const hit = shaded.size === c.target;
        ui.equation.textContent = `${shaded.size}/${c.n} shaded` + (c.equivalent && hit ? ' = 1/2' : '') + (c.wholeLength && hit ? ` · ${c.wholeLength} ÷ ${c.n} × ${shaded.size} = ${c.wholeLength / c.n * shaded.size} cm` : '');
        if (c.wholeLength) ui.board.append(node('p', `The vertical strip represents ${c.wholeLength} cm. Each part is ${c.wholeLength} ÷ ${c.n} cm.`));
        ui.feedback.textContent = message || (hit ? c.equivalent ? 'Two quarters cover the same amount as one half. Try a different pair.' : `${shaded.size} ${shaded.size === 1 ? 'part is' : 'parts are'} shaded. Each is one ${c.n === 6 ? 'sixth' : c.n === 5 ? 'fifth' : 'quarter'} of the whole.` : `The whole has ${c.n} equal parts. ${shaded.size > c.target ? 'Clear' : 'Shade'} ${Math.abs(c.target - shaded.size)} ${Math.abs(c.target - shaded.size) === 1 ? 'part' : 'parts'} more.`);
      });
    }
    ui.controls.append(button('Reset', 'reset', () => {shaded.clear(); render();}));
    render();
  }
  function shapes(ui, c) {
    let angle = c.angle || 0, small = false, alternate = !!c.red, touched = new Set();
    ui.objective.textContent = 'Turn, resize and recolour the shape. What stays the same?';
    function render() {
      ui.redraw(() => {
        const s = svgNode('svg', {viewBox: '0 0 240 240', role: 'img', 'aria-label': `Closed shape with three straight sides, turned ${angle} degrees`, class: 'mp-shape'});
        s.append(svgNode('circle', {cx: 120, cy: 120, r: 112, fill: '#e5edf9'}));
        const g = svgNode('g', {transform: `translate(120 120) rotate(${angle}) scale(${small ? .65 : 1})`});
        g.append(svgNode('polygon', {points: '0,-77 70,50 -70,50', fill: alternate ? '#ca617a' : '#7a9cdb', stroke: '#183b4b', 'stroke-width': 4}));
        [[0, -77], [70, 50], [-70, 50]].forEach(([x, y]) => g.append(svgNode('circle', {cx: x, cy: y, r: 6, fill: '#183b4b'})));
        s.append(g); ui.board.append(s);
        const row = node('div', undefined, 'mp-row');
        row.append(button('Turn a quarter turn', 'turn', () => {angle = (angle + 90) % 360; touched.add('turn'); render();}), button(small ? 'Make bigger' : 'Make smaller', 'size', () => {small = !small; touched.add('size'); render();}), button('Change colour', 'colour', () => {alternate = !alternate; touched.add('colour'); render();}));
        ui.board.append(row);
        ui.equation.textContent = '3 straight sides + closed = triangle';
        ui.feedback.textContent = touched.size ? `Still a triangle! Its sides stay straight and joined. ${touched.size === 3 ? 'Size, colour and direction do not change its shape family.' : 'Try the other changes too.'}` : 'Look at the three corners. The sides join all the way around.';
      });
    }
    ui.controls.append(button('Reset', 'reset', () => {angle = c.angle || 0; small = false; alternate = !!c.red; touched = new Set(); render();}));
    render();
  }
  function patterns(ui, c) {
    let tiles = Array.from({length: c.seed}, (_, i) => c.unit[i % c.unit.length]);
    const palette = [...new Set(c.unit)];
    const tilePic = kind => picture(kind === 'red' || kind === 'blue' ? 'circle' : kind, kind === 'red' ? '#c65776' : kind === 'blue' ? '#7598da' : '#daa44f');
    ui.objective.textContent = `Build a ${c.length}-tile train. Keep the same repeating group. You can undo and try again.`;
    function render() {
      ui.redraw(() => {
        const unit = node('div', undefined, 'mp-pattern-unit');
        unit.append(node('span', 'Repeating group:'));
        c.unit.forEach(kind => {const p = node('span', kind); p.prepend(tilePic(kind)); unit.append(p);});
        const train = node('div', undefined, 'mp-train');
        for (let i = 0; i < c.length; i++) {
          const car = node('div', undefined, 'mp-car' + (i >= tiles.length ? ' mp-empty' : ''));
          car.setAttribute('role', 'group');
          car.setAttribute('aria-label', `Position ${i + 1}: ${tiles[i] || 'empty'}`);
          if (tiles[i]) car.append(tilePic(tiles[i]));
          car.append(node('span', `${i + 1}. ${tiles[i] || '…'}`, 'mp-number')); train.append(car);
        }
        const row = node('div', undefined, 'mp-row');
        palette.forEach(kind => {const b = button(`Add ${kind}`, `add-${kind}`, () => {tiles.push(kind); render();}); b.disabled = tiles.length === c.length; row.append(b);});
        ui.board.append(unit, train, row);
        const mismatch = tiles.findIndex((kind, i) => kind !== c.unit[i % c.unit.length]);
        ui.equation.textContent = `${c.unit.length} tiles in each repeating group`;
        ui.feedback.textContent = mismatch >= 0 ? `Look at position ${mismatch + 1}. Compare it with the same place in the repeating group. Undo to change your tiles.` : tiles.length === c.length ? 'Your train repeats all the way! Point to each complete group and say its shapes or colours.' : 'Follow the group from its beginning again each time. Add the next tile.';
        undo.disabled = tiles.length <= c.seed;
      });
    }
    const undo = button('Undo last tile', 'undo', () => {tiles.pop(); render();});
    ui.controls.append(button('Reset', 'reset', () => {tiles = Array.from({length: c.seed}, (_, i) => c.unit[i % c.unit.length]); render();}), undo);
    render();
  }
  function fallback(container, lesson) {
    const ex = lesson.worked_example;
    if (!ex || typeof ex.prompt !== 'string' || !Array.isArray(ex.steps) || typeof ex.answer !== 'string') return false;
    const ui = shell(container, 'One step at a time', false);
    const steps = [ex.prompt, ...ex.steps.filter(s => typeof s === 'string'), ex.answer];
    let index = 0;
    ui.objective.textContent = 'Think about this example, then uncover one step at a time.';
    ui.equation.hidden = true;
    const panel = node('div', undefined, 'mp-step'); panel.setAttribute('aria-live', 'polite'); panel.setAttribute('aria-atomic', 'true');
    ui.board.append(panel);
    const back = button('Back', 'back', () => {index--; render();});
    const next = button('Next', 'next', () => {index++; render();});
    function render() {
      panel.textContent = steps[index];
      ui.feedback.textContent = `${index === 0 ? 'Example' : index === steps.length - 1 ? 'Worked answer' : 'Reasoning'} · ${index + 1} of ${steps.length}`;
      back.disabled = index === 0; next.disabled = index === steps.length - 1;
      if (document.activeElement === next && next.disabled) back.focus();
      if (document.activeElement === back && back.disabled) next.focus();
    }
    ui.controls.append(back, next, button('Reset', 'reset', () => {index = 0; render();}));
    render();
    return true;
  }
  function mount(container, config, title, question) {
    const ui = shell(container, title, question);
    if (['add', 'remove', 'count'].includes(config.kind)) counters(ui, config);
    else if (config.kind === 'share') sharing(ui, config);
    else if (config.kind === 'fraction') fractions(ui, config);
    else if (config.kind === 'shape') shapes(ui, config);
    else if (config.kind === 'pattern') patterns(ui, config);
    return true;
  }
  window.MathsPlay = Object.freeze({
    discoveries: Object.freeze(Object.entries(topics).map(([id, t]) => Object.freeze({id, title: t.title, subtitle: t.subtitle, icon: t.icon, color: t.color}))),
    has(topic_id) {return typeof topic_id === 'string' && own(topics, topic_id);},
    mountLesson(container, lesson) {
      if (!container || typeof container.replaceChildren !== 'function' || !lesson) return false;
      if (!own(topics, lesson.topic_id)) return fallback(container, lesson);
      const t = topics[lesson.topic_id];
      return mount(container, t, t.title, false);
    },
    mountQuestion(container, active) {
      if (!container || typeof container.replaceChildren !== 'function' || !active?.problem || active.problem.visual || !Number.isInteger(active.index) || !own(questions, active.topic_id)) return false;
      const map = questions[active.topic_id];
      if (!own(map, active.index)) return false;
      return mount(container, map[active.index], 'Try the idea with objects', true);
    }
  });
})();
