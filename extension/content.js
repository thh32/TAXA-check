/* TAXA-check content script
 * Complete replacement for extension/content.js
 */
(() => {
  'use strict';

  const LORN_KEY = 'taxacheckHighlightAllLoRN';
  const SCANNING_KEY = 'taxacheckScanningEnabled';
  const REMOTE_NAMES_KEY = 'taxacheckRemoteNames';
  const REMOTE_EPITHETS_KEY = 'taxacheckRemoteEpithets';

  const BLOCKED = new Set([
    'species',
    'sp',
    'spp',
    'genus',
    'genera',
    'family',
    'families',
    'order',
    'class',
    'phylum',
    'kingdom',
    'domain',
    'bacterium',
    'bacteria',
    'archaeon',
    'archaea',
    'organism',
    'microorganism',
    'microbe',
    'strain',
    'isolate',
    'uncultured',
    'unclassified',
    'unknown',
    'candidate',
    'candidatus',
    'not',
    'assigned'
  ]);

  const COMMON_FIRST_WORDS = new Set([
    'a',
    'an',
    'the',
    'and',
    'or',
    'but',
    'nor',
    'so',
    'yet',
    'as',
    'at',
    'by',
    'for',
    'from',
    'in',
    'into',
    'of',
    'on',
    'onto',
    'to',
    'upon',
    'via',
    'with',
    'without',
    'after',
    'before',
    'between',
    'during',
    'following',
    'through',
    'throughout',
    'under',
    'until',
    'within',
    'across',
    'against',
    'along',
    'among',
    'around',
    'behind',
    'below',
    'beneath',
    'beside',
    'beyond',
    'near',
    'over',
    'past',
    'toward',
    'towards',
    'this',
    'that',
    'these',
    'those',
    'there',
    'here',
    'then',
    'than',
    'when',
    'where',
    'while',
    'which',
    'what',
    'who',
    'whom',
    'whose',
    'why',
    'how',
    'all',
    'another',
    'any',
    'both',
    'each',
    'either',
    'enough',
    'every',
    'few',
    'fewer',
    'least',
    'less',
    'many',
    'more',
    'most',
    'much',
    'neither',
    'no',
    'none',
    'other',
    'others',
    'several',
    'some',
    'such',
    'also',
    'although',
    'because',
    'however',
    'if',
    'otherwise',
    'since',
    'therefore',
    'though',
    'thus',
    'unless',
    'whereas',
    'whether',
    'its',
    'our',
    'their',
    'your',
    'his',
    'her',
    'my',
    'only',
    'same',
    'different',
    'new',
    'old',
    'first',
    'second',
    'third',
    'last',
    'next',
    'previous',
    'current',
    'minimum',
    'maximum',
    'mean',
    'median',
    'average',
    'total',
    'relative',
    'absolute',
    'general',
    'overall',
    'additional',
    'individual',
    'significant',
    'significantly',
    'manage',
    'accept',
    'reject',
    'allow',
    'decline',
    'save',
    'close',
    'open',
    'view',
    'read',
    'learn',
    'show',
    'hide',
    'change',
    'choose',
    'select',
    'enable',
    'disable',
    'cookie',
    'cookies',
    'privacy',
    'settings',
    'preferences',
    'account',
    'login',
    'continue',
    'subscribe'
  ]);

  const MONO_RANKS = new Set([
    'domain',
    'realm',
    'kingdom',
    'subkingdom',
    'infrakingdom',
    'phylum',
    'subphylum',
    'superphylum',
    'class',
    'subclass',
    'superclass',
    'order',
    'suborder',
    'family',
    'subfamily',
    'tribe',
    'subtribe',
    'genus',
    'subgenus'
  ]);

  const SKIP_SELECTOR = [
    'script',
    'style',
    'noscript',
    'textarea',
    'input',
    'select',
    'option',
    'code',
    'pre',
    'svg',
    'canvas',
    '.tc-hit',
    '#tc-tip'
  ].join(',');

  const FULL =
    /\b([A-Z][a-z-]{2,})[\s\u00a0\u2009\u202f]+([a-z][a-z-]{1,})\b/g;

  const ABBR =
    /\b([A-Z])\.[\s\u00a0\u2009\u202f]*([a-z][a-z-]{1,})\b/g;

  const MONO =
    /\b[A-Z][A-Za-z-]{2,}\b/g;

  const NOT_ASSIGNED =
    /\bnot\s+assigned\s+to\s+(?:domain|kingdom|phylum|class|order|family|genus|species|subspecies)\b/i;

  const LORN_STATUS =
    /(?:taxonomic(?:ally)?\s+suspend(?:ed|sion)|not\s+recommended\s+for\s+(?:human\s+or\s+veterinary\s+)?medical\s+use|recommended\s+for\s+(?:human\s+or\s+veterinary\s+)?medical\s+use|\bLoRN\b)/i;

  const LORN_DISPLACED =
    /(?:taxonomic(?:ally)?\s+suspend(?:ed|sion)|not\s+recommended\s+for\s+(?:human\s+or\s+veterinary\s+)?medical\s+use)/i;

  let names = null;
  let epithets = null;
  let tip = null;
  let lornGreen = false;
  let scanningEnabled = true;
  let databaseReady = false;
  let hideTimer = null;
  let rescanTimer = null;
  let observer = null;

  function escapeHtml(value) {
    return String(value ?? '').replace(
      /[&<>"']/g,
      character => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      })[character]
    );
  }

  function commonFirstWord(value) {
    return COMMON_FIRST_WORDS.has(
      String(value || '')
        .trim()
        .replace(/^[“”"'‘’]+|[“”"'‘’,;:.!?]+$/g, '')
        .toLowerCase()
    );
  }

  function installRuntimeStyles() {
    if (document.getElementById('tc-runtime-style')) {
      return;
    }

    const style = document.createElement('style');
    style.id = 'tc-runtime-style';

    style.textContent = `
      .tc-lorn-green {
        color: #173600 !important;
        background: #9cff57 !important;
        box-shadow: inset 0 -1px 0 rgba(23, 54, 0, 0.22) !important;
      }

      .tc-lorn-banner {
        margin: 4px 0 11px;
        padding: 10px 12px;
        border-left: 4px solid #60b52a;
        border-radius: 7px;
        background: #efffe4;
        color: #244413;
      }

      .tc-lorn-label {
        display: inline-block;
        margin-bottom: 5px;
        padding: 3px 8px;
        border-radius: 999px;
        background: #9cff57;
        color: #173600;
        font-weight: 750;
        font-size: 11px;
      }
    `;

    document.documentElement.appendChild(style);
  }

  async function fetchBundledJson(filename) {
    const response = await fetch(
      chrome.runtime.getURL('generated/' + filename)
    );

    if (!response.ok) {
      throw new Error(
        filename + ' HTTP ' + response.status
      );
    }

    return response.json();
  }

  async function load() {
    const stored = await chrome.storage.local.get({
      [LORN_KEY]: false,
      [SCANNING_KEY]: true,
      [REMOTE_NAMES_KEY]: null,
      [REMOTE_EPITHETS_KEY]: null
    });

    lornGreen = Boolean(stored[LORN_KEY]);
    scanningEnabled = stored[SCANNING_KEY] !== false;

    if (
      stored[REMOTE_NAMES_KEY] &&
      stored[REMOTE_EPITHETS_KEY]
    ) {
      names = stored[REMOTE_NAMES_KEY];
      epithets = stored[REMOTE_EPITHETS_KEY];
    } else {
      [names, epithets] = await Promise.all([
        fetchBundledJson('names.json'),
        fetchBundledJson('epithets.json')
      ]);
    }

    databaseReady = Boolean(names && epithets);
  }

  function monomial(record) {
    const ranks = Array.isArray(record?.rank)
      ? record.rank
      : [record?.rank];

    return ranks.some(rank =>
      MONO_RANKS.has(
        String(rank || '').toLowerCase()
      )
    );
  }

  function lornHistories(record) {
    return (record?.history || []).filter(history =>
      history?.source === 'LPSN' &&
      LORN_STATUS.test(
        String(history.status || '')
      )
    );
  }

  function displacedLoRN(record) {
    return lornHistories(record).find(history =>
      LORN_DISPLACED.test(
        String(history.status || '')
      )
    );
  }

  function isLoRN(record) {
    return (
      lornHistories(record).length > 0 ||
      Boolean(record?.lorn_medically_relevant) ||
      (
        Array.isArray(record?.lorn_descendants) &&
        record.lorn_descendants.length > 0
      )
    );
  }

  function recommendedLoRNName(record) {
    if (
      Array.isArray(record?.lorn_descendants) &&
      record.lorn_descendants.length
    ) {
      const genera = [
        ...new Set(
          record.lorn_descendants
            .map(item => item.recommended_genus)
            .filter(Boolean)
        )
      ];

      return genera.length
        ? genera.join(', ')
        : record.name;
    }

    const histories = lornHistories(record);

    const displaced = histories.find(history =>
      LORN_DISPLACED.test(
        String(history.status || '')
      )
    );

    if (displaced?.correct_name) {
      return displaced.correct_name;
    }

    const recommended = histories.find(history =>
      /recommended\s+for\s+(?:human\s+or\s+veterinary\s+)?medical\s+use/i
        .test(String(history.status || '')) &&
      !/not\s+recommended/i
        .test(String(history.status || ''))
    );

    return (
      recommended?.correct_name ||
      recommended?.display_name ||
      record?.name ||
      ''
    );
  }

  function visualState(record) {
    if (lornGreen && isLoRN(record)) {
      return 'lorn-green';
    }

    if (displacedLoRN(record)) {
      return 'lpsn';
    }

    return record?.state || 'ambiguous';
  }

  function applyVisualClass(span) {
    if (!span?.__tc) {
      return;
    }

    for (const className of [...span.classList]) {
      if (
        className.startsWith('tc-') &&
        className !== 'tc-hit'
      ) {
        span.classList.remove(className);
      }
    }

    span.classList.add(
      'tc-' + visualState(span.__tc)
    );
  }

  function refreshVisuals() {
    document
      .querySelectorAll('.tc-hit')
      .forEach(applyVisualClass);
  }

  function find(t) {
    if (
      !scanningEnabled ||
      !databaseReady ||
      !names ||
      !epithets
    ) {
      return [];
    }

    const out = [];
    let match;

    FULL.lastIndex = 0;

    while ((match = FULL.exec(t))) {
      const first = match[1];

      const epithet = match[2]
        .toLowerCase()
        .replace(/\.$/, '');

      if (
        commonFirstWord(first) ||
        BLOCKED.has(epithet)
      ) {
        continue;
      }

      const key = match[0]
        .replace(
          /[\s\u00a0\u2009\u202f]+/g,
          ' '
        )
        .toLowerCase();

      const exact = names[key];

      const candidates = (
        epithets[epithet] || []
      ).filter(candidate =>
        !NOT_ASSIGNED.test(
          String(candidate)
        )
      );

      if (
        exact &&
        !NOT_ASSIGNED.test(
          String(exact.name || key)
        )
      ) {
        out.push({
          s: match.index,
          e: match.index + match[0].length,
          x: exact
        });
      } else if (candidates.length) {
        out.push({
          s: match.index,
          e: match.index + match[0].length,
          x: {
            name: match[0],
            state: 'ambiguous',
            candidate_keys: candidates
          }
        });
      }
    }

    ABBR.lastIndex = 0;

    while ((match = ABBR.exec(t))) {
      const epithet = match[2]
        .toLowerCase()
        .replace(/\.$/, '');

      if (
        BLOCKED.has(epithet) ||
        out.some(item =>
          match.index < item.e &&
          match.index + match[0].length > item.s
        )
      ) {
        continue;
      }

      const initial = match[1].toLowerCase();

      const allCandidates = (
        epithets[epithet] || []
      ).filter(candidate =>
        !NOT_ASSIGNED.test(
          String(candidate)
        )
      );

      const matchingCandidates =
        allCandidates.filter(candidate =>
          String(candidate)
            .toLowerCase()
            .startsWith(initial + ' ')
        );

      if (
        matchingCandidates.length === 1 &&
        names[matchingCandidates[0]]
      ) {
        out.push({
          s: match.index,
          e: match.index + match[0].length,
          x: names[matchingCandidates[0]]
        });
      } else if (
        matchingCandidates.length > 1
      ) {
        out.push({
          s: match.index,
          e: match.index + match[0].length,
          x: {
            name: match[0],
            state: 'ambiguous',
            candidate_keys: matchingCandidates,
            abbreviation: true
          }
        });
      } else if (allCandidates.length) {
        out.push({
          s: match.index,
          e: match.index + match[0].length,
          x: {
            name: match[0],
            state: 'ambiguous',
            candidate_keys: allCandidates,
            abbreviation: true,
            initial_mismatch: true,
            written_initial: match[1],
            epithet: match[2]
          }
        });
      }
    }

    MONO.lastIndex = 0;

    while ((match = MONO.exec(t))) {
      if (
        out.some(item =>
          match.index < item.e &&
          match.index + match[0].length > item.s
        )
      ) {
        continue;
      }

      const record =
        names[match[0].toLowerCase()];

      if (
        record &&
        monomial(record) &&
        !NOT_ASSIGNED.test(
          String(record.name || match[0])
        )
      ) {
        out.push({
          s: match.index,
          e: match.index + match[0].length,
          x: record
        });
      }
    }

    return out
      .sort(
        (left, right) =>
          left.s - right.s ||
          right.e - left.e
      )
      .filter(
        (item, index, array) =>
          index === 0 ||
          item.s >= array[index - 1].e
      );
  }

  function usableTextNode(node) {
    return Boolean(
      node?.nodeType === Node.TEXT_NODE &&
      node.nodeValue?.trim() &&
      node.parentElement &&
      !node.parentElement.closest(
        SKIP_SELECTOR
      )
    );
  }

  function scanNode(node) {
    if (
      !scanningEnabled ||
      !databaseReady ||
      !usableTextNode(node)
    ) {
      return;
    }

    const t = node.nodeValue;
    const hits = find(t);

    if (!hits.length) {
      return;
    }

    const fragment =
      document.createDocumentFragment();

    let cursor = 0;

    for (const hit of hits) {
      fragment.append(
        t.slice(cursor, hit.s)
      );

      const span =
        document.createElement('span');

      span.className = 'tc-hit';
      span.textContent =
        t.slice(hit.s, hit.e);
      span.__tc = hit.x;

      applyVisualClass(span);
      fragment.append(span);

      cursor = hit.e;
    }

    fragment.append(
      t.slice(cursor)
    );

    node.replaceWith(fragment);
  }

  function scan(root = document) {
    if (
      !scanningEnabled ||
      !databaseReady ||
      !root
    ) {
      return;
    }

    if (root.nodeType === Node.TEXT_NODE) {
      scanNode(root);
      return;
    }

    const walker =
      document.createTreeWalker(
        root,
        NodeFilter.SHOW_TEXT
      );

    const nodes = [];

    while (walker.nextNode()) {
      nodes.push(walker.currentNode);
    }

    nodes.forEach(scanNode);
  }

  function blockTextParts(block) {
    const walker =
      document.createTreeWalker(
        block,
        NodeFilter.SHOW_TEXT,
        {
          acceptNode(node) {
            if (
              usableTextNode(node) ||
              node.parentElement?.closest('.tc-hit')
            ) {
              return NodeFilter.FILTER_ACCEPT;
            }

            return NodeFilter.FILTER_REJECT;
          }
        }
      );

    const raw = [];

    while (walker.nextNode()) {
      raw.push(walker.currentNode);
    }

    let t = '';
    let cursor = 0;
    const parts = [];

    for (const node of raw) {
      const value = node.nodeValue || '';

      if (!value) {
        continue;
      }

      const left = t.slice(-1);
      const right = value.charAt(0);

      const leftSeparates =
        /[\s\u00a0\u2009\u202f([{/=.\-]/
          .test(left);

      const rightSeparates =
        /[\s\u00a0\u2009\u202f,.;:!?)}\]\/=.\-]/
          .test(right);

      if (
        t &&
        !leftSeparates &&
        !rightSeparates
      ) {
        t += ' ';
        cursor += 1;
      }

      const start = cursor;

      t += value;
      cursor += value.length;

      parts.push({
        node,
        start,
        end: cursor
      });
    }

    return {
      t,
      parts
    };
  }

  function wrapMappedPart(
    part,
    start,
    end,
    record
  ) {
    const localStart =
      start - part.start;

    const localEnd =
      end - part.start;

    if (localStart >= localEnd) {
      return;
    }

    const holder =
      part.node.parentElement
        ?.closest('.tc-hit');

    if (holder) {
      holder.__tc = record;
      applyVisualClass(holder);
      return;
    }

    const value = part.node.nodeValue;

    const fragment =
      document.createDocumentFragment();

    fragment.append(
      value.slice(0, localStart)
    );

    const span =
      document.createElement('span');

    span.className = 'tc-hit';

    span.textContent =
      value.slice(
        localStart,
        localEnd
      );

    span.__tc = record;
    applyVisualClass(span);

    fragment.append(span);

    fragment.append(
      value.slice(localEnd)
    );

    part.node.replaceWith(fragment);
  }

  function reconcileBlock(block) {
    if (
      !scanningEnabled ||
      !databaseReady ||
      !block ||
      block.closest?.('#tc-tip') ||
      block.dataset.tcReconciling === '1'
    ) {
      return;
    }

    block.dataset.tcReconciling = '1';

    try {
      const mapped =
        blockTextParts(block);

      const hits = find(mapped.t).filter(
        hit => {
          const ranks =
            Array.isArray(hit.x?.rank)
              ? hit.x.rank
              : [hit.x?.rank];

          return (
            hit.x?.state === 'ambiguous' ||
            ranks.some(rank =>
              [
                'species',
                'subspecies',
                'variety',
                'form'
              ].includes(
                String(rank || '')
                  .toLowerCase()
              )
            )
          );
        }
      );

      for (
        const hit of hits.sort(
          (left, right) =>
            right.s - left.s
        )
      ) {
        for (
          const part of
                    Math.max(
              hit.s,
              part.start
            );

          const end =
            Math.min(
              hit.e,
              part.end
            );

          if (start < end) {
            wrapMappedPart(
              part,
              start,
              end,
              hit.x
            );
          }
        }
      }
    } finally {
      delete block.dataset.tcReconciling;
    }
  }

  function reconcileVisibleBlocks() {
    if (
      !scanningEnabled ||
      !databaseReady
    ) {
      return;
    }

    const selector = [
      'p',
      'li',
      'dd',
      'dt',
      'td',
      'th',
      'figcaption',
      'h1',
      'h2',
      'h3',
      'h4',
      'h5',
      'h6',
      '[role="heading"]',
      '[role="paragraph"]',
      '[role="textbox"]',
      '[contenteditable="true"]'
    ].join(',');

    for (
      const block of
        document.querySelectorAll(selector)
    ) {
      const rectangle =
        block.getBoundingClientRect();

      if (
        rectangle.width > 0 &&
        rectangle.height > 0 &&
        rectangle.bottom > -300 &&
        rectangle.top < innerHeight + 300
      ) {
        reconcileBlock(block);
      }
    }
  }

  function clearTaxaCheckAnnotations() {
    closeTip();

    for (
      const hit of [
        ...document.querySelectorAll(
          '.tc-hit'
        )
      ]
    ) {
      hit.replaceWith(
        document.createTextNode(
          hit.textContent || ''
        )
      );
    }

    document.body?.normalize();
  }

  function rescanTaxaCheck() {
    if (
      !scanningEnabled ||
      !databaseReady
    ) {
      return;
    }

    scan(document);
    reconcileVisibleBlocks();
  }

  function queueRescan(delay = 60) {
    if (
      !scanningEnabled ||
      !databaseReady
    ) {
      return;
    }

    clearTimeout(rescanTimer);

    rescanTimer = setTimeout(
      rescanTaxaCheck,
      delay
    );
  }

  function lineage(history) {
    const values =
      history?.classification;

    if (
      !Array.isArray(values) ||
      !values.length
    ) {
      return '';
    }

    return values
      .map(value =>
        escapeHtml(
          typeof value === 'string'
            ? value
            : (
                value.name ||
                value.full_name ||
                ''
              )
        )
      )
      .filter(Boolean)
      .join(' › ');
  }

  function sourceMarkup(history) {
    const seqcode =
      history.source ===
      'SeqCode Registry';

    const code =
      seqcode
        ? 'SeqCode'
        : 'ICNP';

    const label =
      seqcode
        ? 'SeqCode Registry'
        : 'LPSN';

    const url =
      String(
        history.source_url || ''
      );

    if (!url) {
      return (
        escapeHtml(code) +
        ' · ' +
        escapeHtml(label)
      );
    }

    return (
      escapeHtml(code) +
      ' · ' +
      '<a class="tc-source-link" ' +
      'href="' + escapeHtml(url) + '" ' +
      'target="_blank" ' +
      'rel="noopener noreferrer">' +
      escapeHtml(label) +
      '</a>'
    );
  }

  function ordinaryHeading(record) {
    if (record.state === 'conflict') {
      return 'Conflicting treatments';
    }

    if (record.state === 'ambiguous') {
      return 'Manual evaluation required';
    }

    if (record.state === 'superseded') {
      return (
        'Superseded or redirected ' +
        'in at least one source'
      );
    }

    if (record.state === 'both') {
      return (
        'Recognized under ICNP ' +
        'and SeqCode'
      );
    }

    if (record.state === 'seqcode') {
      return 'SeqCode Registry name';
    }

    if (
      record.state ===
      'seqcode-unverified'
    ) {
      return (
        'SeqCode Registry entry; ' +
        'validity unavailable'
      );
    }

    return 'LPSN name';
  }

  function cancelHide() {
    if (hideTimer !== null) {
      clearTimeout(hideTimer);
      hideTimer = null;
    }
  }

  function closeTip() {
    cancelHide();
    tip?.remove();
    tip = null;
  }

  function scheduleHide(delay = 75) {
    cancelHide();

    hideTimer = setTimeout(() => {
      const hovered =
        document.querySelector(
          '.tc-hit:hover,#tc-tip:hover'
        );

      if (!hovered) {
        closeTip();
      }
    }, delay);
  }

  function show(element, event) {
    if (
      !scanningEnabled ||
      !element?.__tc
    ) {
      return;
    }

    closeTip();

    const record = element.__tc;
    const displaced =
      displacedLoRN(record);

    const recommended =
      recommendedLoRNName(record);

    const lorn =
      isLoRN(record);

    const genusOnly =
      Boolean(
        record.lorn_medically_relevant
      ) &&
      !lornHistories(record).length;

    const heading = displaced
      ? (
          'Taxonomically suspended due to ' +
          'a previous name being recommended ' +
          'for medical use (LoRN), while this ' +
          'name may better represent accurate ' +
          'taxonomic placement.'
        )
      : ordinaryHeading(record);

    tip = document.createElement('div');
    tip.id = 'tc-tip';

    let html =
      '<div class="title">' +
      escapeHtml(record.name) +
      '</div>';

    if (lornGreen && lorn) {
      html +=
        '<div class="tc-lorn-label">' +
        'LoRN highlighted' +
        '</div>';

      if (genusOnly) {
        html +=
          '<div class="tc-lorn-banner">' +
          '<b>Medically relevant ' +
          'LoRN-associated genus</b><br>' +
          'This genus contains ' +
          'LoRN-associated names.';

        if (recommended) {
          html +=
            '<br><b>Recommended medical ' +
            'genus name(s):</b> <i>' +
            escapeHtml(recommended) +
            '</i>';
        }

        html += '</div>';
      } else {
        html +=
          '<div class="tc-lorn-banner">' +
          '<b>LoRN recommended name:</b> ' +
          '<i>' +
          escapeHtml(
            recommended || record.name
          ) +
          '</i></div>';
      }
    }

    html +=
      '<div class="flag">' +
      escapeHtml(heading) +
      '</div>';

    if (displaced) {
      html +=
        '<div class="taxonomy">' +
        'This LPSN name is not recommended ' +
        'for medical use under LoRN.';

      if (recommended) {
        html +=
          '<br><b>LoRN recommended name:</b> ' +
          '<i>' +
          escapeHtml(recommended) +
          '</i>';
      }

      html +=
        '<br>The recommendation reflects ' +
        'medical-use considerations and ' +
        'practical name stability, not ' +
        'greater taxonomic accuracy.' +
        '</div>';
    }

    if (record.candidate_keys) {
      if (record.initial_mismatch) {
        html +=
          '<div class="taxonomy">' +
          '<b>Ambiguous abbreviation:</b> ' +
          'no genus beginning with <i>' +
          escapeHtml(
            record.written_initial
          ) +
          '.</i> was found for the epithet ' +
          '<i>' +
          escapeHtml(record.epithet) +
          '</i>. The names below share the ' +
          'epithet but do not match the ' +
          'written genus initial.' +
          '</div>';
      }

      html +=
        '<div>Possible written names:</div>' +
        '<ul>';

      for (
        const key of
          record.candidate_keys.slice(0, 50)
      ) {
        html +=
          '<li><i>' +
          escapeHtml(
            names[key]?.name || key
          ) +
          '</i></li>';
      }

      html += '</ul>';
    } else {
      for (
        const history of
          record.history || []
      ) {
        const recordDisplaced =
          history.source === 'LPSN' &&
          LORN_DISPLACED.test(
            String(history.status || '')
          );

        html +=
          '<div class="source">' +
          sourceMarkup(history) +
          '</div>';

        html +=
          '<div>Rank: ' +
          escapeHtml(
            history.rank ||
            'not supplied'
          ) +
          '</div>';

        html +=
          '<div>Status: ' +
          escapeHtml(
            history.status ||
            'not supplied'
          ) +
          '</div>';

        if (
          recordDisplaced &&
          history.correct_name
        ) {
          html +=
            '<div><b>LoRN recommended ' +
            'name:</b> <i>' +
            escapeHtml(
              history.correct_name
            ) +
            '</i></div>';
        } else if (
          history.superseded &&
          history.correct_name &&
          String(history.correct_name)
            .toLowerCase() !==
          String(record.name)
            .toLowerCase()
        ) {
          html +=
            '<div><b>Correct name:</b> <i>' +
            escapeHtml(
              history.correct_name
            ) +
            '</i></div>';
        }

        if (
          history.source !==
          'SeqCode Registry'
        ) {
          const validity =
            history.validly_published === ''
              ? 'not supplied'
              : history.validly_published;

          html +=
            '<div>Validly published: ' +
            escapeHtml(validity) +
            '</div>';
        }

        const classification =
          lineage(history);

        if (classification) {
          html +=
            '<div class="taxonomy">' +
            classification +
            '</div>';
        }
      }
    }

    tip.innerHTML = html;
    document.documentElement.append(tip);

    move(event);
  }

  function move(event) {
    if (!tip || !event) {
      return;
    }

    const rectangle =
      tip.getBoundingClientRect();

    tip.style.left =
      Math.max(
        8,
        Math.min(
          innerWidth -
            rectangle.width -
            8,
          event.clientX + 12
        )
      ) + 'px';

    tip.style.top =
      Math.max(
        8,
        Math.min(
          innerHeight -
            rectangle.height -
            8,
          event.clientY + 12
        )
      ) + 'px';
  }

  function startObserver() {
    observer = new MutationObserver(
      mutations => {
        if (
          !scanningEnabled ||
          !databaseReady
        ) {
          return;
        }

        for (const mutation of mutations) {
          if (
            mutation.type ===
            'characterData'
          ) {
            scanNode(mutation.target);
          }

          for (
            const node of
              mutation.addedNodes
          ) {
            if (
              node.nodeType ===
              Node.TEXT_NODE
            ) {
              scanNode(node);
            } else if (
              node.nodeType ===
                Node.ELEMENT_NODE &&
              !node.closest?.('.tc-hit')
            ) {
              scan(node);
            }
          }
        }

        queueRescan(50);
      }
    );

    observer.observe(
      document.documentElement,
      {
        subtree: true,
        childList: true,
        characterData: true
      }
    );
  }

  installRuntimeStyles();

  load()
    .then(() => {
      if (scanningEnabled) {
        rescanTaxaCheck();
      }

      startObserver();

      chrome.storage.onChanged.addListener(
        (changes, area) => {
          if (area !== 'local') {
            return;
          }

          if (changes[LORN_KEY]) {
            lornGreen = Boolean(
              changes[LORN_KEY].newValue
            );

            if (scanningEnabled) {
              refreshVisuals();
            }

            closeTip();
          }

          if (changes[SCANNING_KEY]) {
            scanningEnabled =
              changes[SCANNING_KEY]
                .newValue !== false;

            if (scanningEnabled) {
              rescanTaxaCheck();
            } else {
              clearTaxaCheckAnnotations();
            }
          }

          if (
            changes[REMOTE_NAMES_KEY] ||
            changes[REMOTE_EPITHETS_KEY]
          ) {
            window.location.reload();
          }
        }
      );

      document.addEventListener(
        'pointerover',
        event => {
          const hit =
            event.target.closest?.(
              '.tc-hit'
            );

          if (hit) {
            show(hit, event);
          } else if (
            event.target.closest?.(
              '#tc-tip'
            )
          ) {
            cancelHide();
          }
        },
        true
      );

      document.addEventListener(
        'pointermove',
        event => {
          if (!tip) {
            return;
          }

          move(event);

          const under =
            document.elementFromPoint(
              event.clientX,
              event.clientY
            );

          if (
            under?.closest?.(
              '.tc-hit,#tc-tip'
            )
          ) {
            cancelHide();
          } else {
            scheduleHide(55);
          }
        },
        {
          passive: true,
          capture: true
        }
      );

      document.addEventListener(
        'pointerout',
        event => {
          if (
            event.target.closest?.(
              '.tc-hit,#tc-tip'
            )
          ) {
            scheduleHide();
          }
        },
        true
      );

      document.addEventListener(
        'scroll',
        () => {
          closeTip();
          queueRescan(90);
        },
        {
          passive: true,
          capture: true
        }
      );

      document.addEventListener(
        'input',
        () => queueRescan(90),
        true
      );

      document.addEventListener(
        'keyup',
        () => queueRescan(90),
        true
      );

      document.addEventListener(
        'selectionchange',
        () => queueRescan(120)
      );

      document.addEventListener(
        'visibilitychange',
        () => {
          if (!document.hidden) {
            queueRescan(20);
          }
        }
      );

      window.addEventListener(
        'focus',
        () => queueRescan(20)
      );

      window.addEventListener(
        'blur',
        closeTip
      );

      document.addEventListener(
        'keydown',
        event => {
          if (event.key === 'Escape') {
            closeTip();
          }
        }
      );

      setInterval(() => {
        if (
          scanningEnabled &&
          databaseReady &&
          !document.hidden
        ) {
          reconcileVisibleBlocks();
        }
      }, 1500);
    })
    .catch(error => {
      console.error(
        'TAXA-check initialization failed:',
        error
      );
    });
})();
