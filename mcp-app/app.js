import { App } from '@modelcontextprotocol/ext-apps';

const MAX_ARTIFACT_BYTES = 1_000_000;
const MAX_HYDRATED_ARTIFACTS = 24;
const MAX_CONCURRENT_READS = 4;
const app = new App({ name: 'Possibly review', version: '0.1.0' });

const artifacts = new Map();
const artifactReads = new Map();
const localPending = new Map();
let desiredAttachment = null;
let displayedAttachment = null;
let presentedState = null;
let observedState = null;
const terminalDiagnostics = new Map();
let tornDown = false;
let attachmentEpoch = 0;
let hostContext = {};
let mediaQuery = null;
let mediaListener = null;
let mediaPoll = null;
let controllerStarted = false;
let attachmentIntent = null;
const knownReviewers = new Map();
let attachmentRequestEpoch = 0;

function attachmentNotice(message) {
  document.querySelector('#notice').textContent = message;
}

const requestId = () =>
  Array.from(crypto.getRandomValues(new Uint8Array(16)), value => value.toString(16).padStart(2, '0')).join('');

function responseValue(response) {
  const text = response.content?.find(item => item.type === 'text')?.text || '{}';
  return response.structuredContent || JSON.parse(text);
}

function decode(response) {
  const value = responseValue(response);
  if (response.isError || value.error) {
    const failure = new Error(value.error?.message || response.content?.[0]?.text || 'The request failed.');
    failure.code = value.error?.code;
    failure.currentStateVersion = value.error?.current_state_version;
    failure.definite = true;
    throw failure;
  }
  return value;
}

async function tool(name, args = {}) {
  // A rejected Promise has no server result. An MCP error result is a definite
  // domain response and must never be turned into transport uncertainty.
  return decode(await app.callServerTool({ name: `possibly_${name}`, arguments: args }));
}

function currentTheme() {
  const theme = hostContext?.theme;
  return theme === 'dark' || theme === 'light'
    ? theme
    : matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light';
}

function applyHostContext(delta = {}) {
  hostContext = { ...hostContext, ...delta, styles: { ...hostContext.styles, ...delta.styles } };
  document.documentElement.dataset.hostTheme = currentTheme();
  const fallback = !['light', 'dark'].includes(hostContext.theme);
  document.documentElement.dataset.hostThemeSource = fallback ? 'media' : '';
  if (fallback && !mediaQuery) {
    mediaQuery = matchMedia('(prefers-color-scheme: dark)');
    mediaListener = () => {
      if (!['light', 'dark'].includes(hostContext.theme)) {
        document.documentElement.dataset.hostTheme = currentTheme();
      }
    };
    mediaQuery.addEventListener('change', mediaListener);
    // A few opaque-frame hosts emulate media changes without dispatching the
    // media-query event. This bounded listener only updates System appearance.
    mediaPoll = setInterval(mediaListener, 250);
  }
  document.dispatchEvent(new Event('possibly-host-context'));
}

function attachmentFrom(value) {
  if (value?.operation !== 'open_review') return null;
  const result = value?.result || value;
  const receipt = result?.receipt || result;
  const attachment = receipt?.attachment || result?.attachment;
  const explorationId =
    attachment?.exploration_id || receipt?.exploration_id || value?.exploration_id || result?.id;
  const reviewerId = attachment?.reviewer_id || receipt?.reviewer_id || value?.reviewer_id;
  if (!explorationId || !reviewerId || typeof explorationId !== 'string' || typeof reviewerId !== 'string') {
    return null;
  }
  return { exploration_id: explorationId, reviewer_id: reviewerId };
}

function attachmentRequest(value) {
  const result = value?.result || value;
  const explorationId = value?.exploration_id || result?.id || result?.exploration_id;
  const reviewerId = value?.reviewer_id || result?.reviewer_id || null;
  return typeof explorationId === 'string' ? { exploration_id: explorationId, reviewer_id: reviewerId } : null;
}

async function requestAttachment(value) {
  if (!['get_exploration', 'get_revision'].includes(value?.operation)) {
    if (!controllerStarted) attachmentNotice('Open a review with possibly_open_review, possibly_get_exploration, or possibly_get_revision.');
    return;
  }
  const request = attachmentRequest(value);
  if (!request) throw new Error('The review result does not identify its exploration.');
  const revision = value.operation === 'get_revision' ? value.result : null;
  if (revision && (typeof revision.id !== 'string' || typeof revision.direction_id !== 'string')) {
    throw new Error('The review result does not identify its revision and direction.');
  }
  // An exact-revision preview gets an independent view; opening it cannot retarget
  // or overwrite drafts in an already-retained review identity.
  const reviewerId = revision ? null : request.reviewer_id || knownReviewers.get(request.exploration_id) || null;
  const key = `${request.exploration_id}:${revision?.id || request.reviewer_id || 'new'}`;
  // Tool-result notifications carry no unique navigation-event ID. Consecutive
  // identical results are a retry/delivery duplicate; A -> B -> A is new intent.
  if (attachmentIntent?.key !== key) {
    attachmentIntent = {
      key, epoch: ++attachmentRequestEpoch, inFlight: false, completed: false,
      openArgs: {
        exploration_id: request.exploration_id,
        reviewer_id: reviewerId,
        request_id: `open-${requestId()}`,
      },
      viewRequestId: `view-${requestId()}`,
      viewArgs: null,
    };
  }
  const intent = attachmentIntent;
  if (intent.inFlight || intent.completed) return;
  intent.inFlight = true;
  const current = () => !tornDown && intent.epoch === attachmentRequestEpoch;
  try {
    // Keep the same request and exact arguments after uncertain transport failure.
    // A receipt may already be committed even when the App never received it.
    const opened = await tool('open_review', intent.openArgs);
    if (!current()) return;
    if (revision) {
      const receipt = opened.result.receipt;
      intent.viewArgs ||= {
        exploration_id: request.exploration_id,
        reviewer_id: receipt.reviewer_id,
        view_id: revision.direction_id,
        view_revision_id: revision.id,
        revision_id: revision.id,
        sequence: receipt.review.sequence + 1,
        request_id: intent.viewRequestId,
      };
      await tool('save_review_state', intent.viewArgs);
      if (!current()) return;
    }
    attachmentNotice('');
    adoptRequestedAttachment(opened);
    startNativeController();
    intent.completed = true;
  } catch (cause) {
    if (current()) attachmentNotice(`Review unavailable. ${cause.message}`);
  } finally {
    intent.inFlight = false;
  }
}

function adoptRequestedAttachment(value) {
  if (tornDown) return;
  const attachment = attachmentFrom(value);
  if (!attachment) return;
  knownReviewers.set(attachment.exploration_id, attachment.reviewer_id);
  desiredAttachment = attachment;
  attachmentEpoch += 1;
  observedState = null;
  terminalDiagnostics.clear();
  if (controllerStarted) document.dispatchEvent(new Event('possibly-exploration'));
}

function attachmentKey(attachment = displayedAttachment) {
  return attachment ? `${attachment.exploration_id}:${attachment.reviewer_id}` : '';
}

function stable(value) {
  if (Array.isArray(value)) return `[${value.map(stable).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value)
      .sort()
      .map(key => `${JSON.stringify(key)}:${stable(value[key])}`)
      .join(',')}}`;
  }
  return JSON.stringify(value);
}

function mutationSignature(path, payload) {
  const copy = { ...payload };
  delete copy.request_id;
  // This key selects a retained uncertain intent; it never rewrites the
  // original payload. A poll may observe a newer state version between loss and
  // retry, so the newly rendered form's optimistic version is not intent
  // identity.
  delete copy.expected_state_version;
  return `${path}:${stable(copy)}`;
}

function pendingFrom(snapshot, attachment) {
  const retained = snapshot.review_states?.[attachment.reviewer_id]?.pending_mutations || {};
  const pending = new Map(Object.entries(retained).map(([id, intent]) => [id, intent]));
  for (const [id, intent] of localPending) {
    if (intent.payload?.exploration_id === attachment.exploration_id) pending.set(id, intent);
  }
  return pending;
}

function hasPendingMutation(path, data) {
  if (!displayedAttachment || data?.exploration_id !== displayedAttachment.exploration_id) return false;
  return [...pendingFrom(presentedState || {}, displayedAttachment).values()].some(
    intent => intent.path === path && mutationSignature(path, intent.payload) === mutationSignature(path, data),
  );
}

function assertCurrent(epoch, attachment) {
  if (tornDown) throw new Error('This review view has closed. Retained work was not cancelled.');
  if (
    epoch !== attachmentEpoch ||
    desiredAttachment?.exploration_id !== attachment.exploration_id ||
    desiredAttachment?.reviewer_id !== attachment.reviewer_id
  ) {
    const stale = new Error('A newer review attachment arrived while this view was loading.');
    stale.staleAttachment = true;
    throw stale;
  }
}

async function readArtifact(explorationId, revisionId) {
  const key = `${explorationId}:${revisionId}`;
  if (artifacts.has(key)) return artifacts.get(key);
  if (artifactReads.has(key)) return artifactReads.get(key);
  const read = tool('read_artifact', {
    exploration_id: explorationId,
    revision_id: revisionId,
    max_bytes: MAX_ARTIFACT_BYTES,
  })
    .then(response => {
      const html = response.result;
      if (typeof html !== 'string' || new TextEncoder().encode(html).byteLength > MAX_ARTIFACT_BYTES) {
        throw new Error('The prototype is too large for this portable review view.');
      }
      artifacts.set(key, html);
      return html;
    })
    .finally(() => artifactReads.delete(key));
  artifactReads.set(key, read);
  return read;
}

async function hydrate(snapshot, attachment, epoch) {
  const revisions = snapshot.revisions || {};
  const saved = snapshot.review_states?.[attachment.reviewer_id] || {};
  const savedRevision = Object.hasOwn(saved, 'view_revision_id') ? saved.view_revision_id : saved.revision_id;
  const displayedRevision = savedRevision || snapshot.selected_revision;
  const displayedDirection = revisions[displayedRevision]?.direction_id;
  const needed = Object.keys(revisions).filter(
    id => !revisions[id].parent || revisions[id].direction_id === displayedDirection || id === savedRevision,
  );
  if (needed.length > MAX_HYDRATED_ARTIFACTS) {
    // Roots and the actually retained view win; other history is fetched on
    // history navigation by ensureRevision(), never silently retargeted.
    const roots = needed.filter(id => !revisions[id].parent);
    const branch = needed.filter(id => revisions[id].direction_id === displayedDirection);
    const ids = [...new Set([...roots, ...branch, savedRevision].filter(Boolean))].slice(-MAX_HYDRATED_ARTIFACTS);
    return hydrateIds(snapshot, attachment, epoch, ids);
  }
  return hydrateIds(snapshot, attachment, epoch, needed);
}

async function hydrateIds(snapshot, attachment, epoch, ids) {
  const queue = [...ids];
  async function worker() {
    while (queue.length) {
      const id = queue.shift();
      assertCurrent(epoch, attachment);
      try {
        snapshot.revisions[id].html = await readArtifact(attachment.exploration_id, id);
      } catch (cause) {
        snapshot.revisions[id].html =
          '<!doctype html><title>Preview unavailable</title><p>Preview unavailable in this portable view.</p>';
        snapshot.revisions[id].artifact_error = cause.message;
      }
      assertCurrent(epoch, attachment);
    }
  }
  await Promise.all(Array.from({ length: Math.min(MAX_CONCURRENT_READS, ids.length) }, worker));
}

async function state() {
  if (!desiredAttachment) {
    return {
      id: 'unattached',
      lifecycle: 'stopped',
      state_version: 0,
      context: 'No retained review attachment has been supplied by this host.',
      revisions: {},
      decisions: [],
      operations: {},
      review_states: {},
    };
  }
  const attachment = { ...desiredAttachment };
  const epoch = attachmentEpoch;
  try {
    const snapshot = (await tool('get_exploration', { exploration_id: attachment.exploration_id })).result;
    assertCurrent(epoch, attachment);
    if (!snapshot.review_states?.[attachment.reviewer_id]) {
      throw new Error('The host supplied a review attachment that is not retained for this exploration.');
    }
    await hydrate(snapshot, attachment, epoch);
    assertCurrent(epoch, attachment);
    snapshot.review_attachment = attachment;
    displayedAttachment = attachment;
    observedState = snapshot;
    return snapshot;
  } catch (cause) {
    if (cause.staleAttachment) return state();
    throw cause;
  }
}

async function ensureRevision(revisionId) {
  if (!displayedAttachment || !revisionId || !presentedState?.revisions?.[revisionId]) return;
  const attachment = { ...displayedAttachment };
  const epoch = attachmentEpoch;
  try {
    presentedState.revisions[revisionId].html = await readArtifact(attachment.exploration_id, revisionId);
    assertCurrent(epoch, attachment);
  } catch (cause) {
    presentedState.revisions[revisionId].html =
      '<!doctype html><title>Preview unavailable</title><p>Preview unavailable in this portable view.</p>';
    presentedState.revisions[revisionId].artifact_error = cause.message;
  }
}

function actionTarget(data) {
  if (!displayedAttachment) throw new Error('Wait for the retained review attachment to finish loading.');
  if (data?.exploration_id !== displayedAttachment.exploration_id) {
    throw new Error('This action belongs to a view that is no longer displayed.');
  }
  if (data?.reviewer_id !== displayedAttachment.reviewer_id) {
    throw new Error('This action belongs to a different retained review identity.');
  }
  return displayedAttachment;
}

async function acknowledge(attachment, mutation) {
  try {
    await tool('acknowledge_review_intent', {
      exploration_id: attachment.exploration_id,
      reviewer_id: attachment.reviewer_id,
      mutation_request_id: mutation.request_id,
      request_id: `ack-${mutation.request_id}`,
    });
    localPending.delete(mutation.request_id);
  } catch {
    // The accepted receipt remains durable. Leave its exact retry intent intact
    // until an acknowledgement reaches the library; never infer it from a read.
  }
}

async function dispatchMutation(path, data) {
  const attachment = actionTarget(data);
  const snapshot = window.state;
  const signature = mutationSignature(path, data);
  const pending = [...pendingFrom(snapshot || {}, attachment).values()];
  const matching = pending.find(intent => intent.path === path && mutationSignature(path, intent.payload) === signature);
  const competing = pending.find(intent => intent.path === path && intent.payload?.exploration_id === data.exploration_id);
  if (competing && !matching) {
    throw new Error('The previous action has an unknown outcome. Retry its original inputs before submitting different work.');
  }
  const request = matching ? matching.payload : { ...data };
  const intent = matching || { request_id: request.request_id, path, payload: request };
  localPending.set(intent.request_id, intent);
  try {
    const result = await dispatch(path, request);
    // The domain receipt is already authoritative. Clearing the review-side
    // retry record is best-effort and must not postpone the truthful success
    // notice behind an unrelated acknowledgement round trip.
    void acknowledge(attachment, intent);
    return result;
  } catch (cause) {
    if (cause.definite) localPending.delete(intent.request_id);
    throw cause;
  }
}

async function providerAction(data) {
  const kind = data.kind || 'test';
  if (!['test', 'models', 'login'].includes(kind)) throw new Error('Unknown provider action.');
  const attachment = actionTarget({
    exploration_id: data.exploration_id || displayedAttachment?.exploration_id,
    reviewer_id: data.reviewer_id || displayedAttachment?.reviewer_id,
  });
  return (
    await tool('start_provider_job', {
      ...data,
      kind,
      exploration_id: attachment.exploration_id,
      reviewer_id: attachment.reviewer_id,
      authorize_provider_action: true,
      request_id: data.request_id || requestId(),
    })
  ).result;
}

async function readExport(explorationId, requestId, exportKind) {
  let offset = 0;
  let output = '';
  while (true) {
    const chunk = (
      await tool('read_export_chunk', {
        exploration_id: explorationId,
        request_id: requestId,
        export_kind: exportKind,
        offset,
        max_bytes: 65_536,
      })
    ).result;
    output += chunk.data;
    offset += new TextEncoder().encode(chunk.data).byteLength;
    if (chunk.complete) return exportKind === 'html' ? output : JSON.parse(output);
  }
}

async function dispatch(path, data) {
  if (path === '/state') return state();
  if (path === '/settings' && !data) return (await tool('provider_settings')).result;
  if (path === '/provider-job' && !data) {
    if (!displayedAttachment) return { status: 'idle', messages: [] };
    return (
      await tool('provider_job', {
        exploration_id: displayedAttachment.exploration_id,
        reviewer_id: displayedAttachment.reviewer_id,
      })
    ).result;
  }
  if (path === '/progress') {
    // The native controller has just read /state. Reuse that snapshot instead
    // of doubling state reads, and retain the final diagnostics for each epoch.
    if (!displayedAttachment || !observedState) return [];
    const attachment = { ...displayedAttachment }, epoch = attachmentEpoch;
    assertCurrent(epoch, attachment);
    const operations = Object.values(observedState.operations || {})
      .filter(operation => operation.kind === 'explore').slice(0, MAX_HYDRATED_ARTIFACTS);
    const retained = new Set(operations.map(operation => operation.id));
    for (const id of terminalDiagnostics.keys()) if (!retained.has(id)) terminalDiagnostics.delete(id);
    const rows = new Array(operations.length), queue = operations.map((operation, index) => ({ operation, index }));
    async function worker() {
      while (queue.length) {
        assertCurrent(epoch, attachment);
        const { operation, index } = queue.shift(), signature = stable(operation);
        const terminal = ['succeeded', 'failed', 'cancelled', 'interrupted'].includes(operation.state);
        const cached = terminalDiagnostics.get(operation.id);
        if (terminal && cached?.signature === signature) { rows[index] = cached.result; continue; }
        const result = (await tool('operation_diagnostics', {
          exploration_id: attachment.exploration_id, operation_id: operation.id,
        })).result;
        assertCurrent(epoch, attachment);
        rows[index] = result;
        if (terminal) terminalDiagnostics.set(operation.id, { signature, result });
        else terminalDiagnostics.delete(operation.id);
      }
    }
    await Promise.all(Array.from({ length: Math.min(MAX_CONCURRENT_READS, operations.length) }, worker));
    return rows;
  }
  if (path === '/settings') {
    if (!displayedAttachment) throw new Error('Wait for the retained review attachment to finish loading.');
    const attachment = displayedAttachment;
    return (
      await tool('configure_provider', {
        ...data,
        exploration_id: attachment.exploration_id,
        authorize_provider_action: true,
      })
    ).result;
  }
  if (path === '/provider-job') return providerAction(data);
  if (path === '/decision') {
    return (await tool('record_decision', data)).result;
  }
  if (path === '/review-state') {
    const attachment = actionTarget(data);
    return (
      await tool('save_review_state', {
        ...data,
        exploration_id: attachment.exploration_id,
        reviewer_id: attachment.reviewer_id,
      })
    ).result;
  }
  if (path === '/export') {
    const result = (await tool('export', data)).result;
    const receipt = result.receipt || {};
    receipt.html = await readExport(data.exploration_id, data.request_id, 'html');
    receipt.handoff = await readExport(data.exploration_id, data.request_id, 'handoff');
    return result;
  }
  if (path === '/answer') return (await tool('answer', data)).result;
  throw new Error('Not found.');
}

window.PossiblyDashboardTransport = {
  async request(path, data) {
    if (['/decision', '/answer', '/export'].includes(path)) return dispatchMutation(path, data);
    return dispatch(path, data);
  },
};

function viewedRevision(state, active, versions) {
  if (!state || active === 'explore') return null;
  if (versions?.[active]) return versions[active];
  return Object.values(state.revisions || {})
    .filter(revision => revision.direction_id === active && !revision.superseded)
    .at(-1)?.id || null;
}

function startNativeController() {
  if (tornDown || controllerStarted || !desiredAttachment) return;
  controllerStarted = true;
  window.PossiblyReviewAttachment = { ...desiredAttachment };
  window.PossiblyDashboardStart?.();
}

function teardown() {
  tornDown = true;
  clearInterval(mediaPoll);
  if (mediaQuery && mediaListener) mediaQuery.removeEventListener('change', mediaListener);
  return window.PossiblyDashboardTeardown?.();
}

(async () => {
  app.ontoolresult = response => {
    try {
      const value = decode(response);
      if (attachmentFrom(value)) {
        attachmentRequestEpoch += 1;
        attachmentIntent = null;
        attachmentNotice('');
        adoptRequestedAttachment(value);
        startNativeController();
      } else {
        requestAttachment(value).catch(cause => attachmentNotice(`Review unavailable. ${cause.message}`));
      }
    } catch (cause) {
      // A native controller, once started, owns user-visible tool errors.
      if (!controllerStarted) attachmentNotice(`Review unavailable. ${cause.message}`);
    }
  };
  app.onhostcontextchanged = applyHostContext;
  app.onteardown = async () => {
    await teardown();
    return {};
  };
  window.PossiblyDashboardAdapter = {
    // Optional, namespaced MCP host extension. Native document visibility is
    // also respected; hosts without this extension retain normal behavior.
    isVisible: () => hostContext['com.microsoft.amplifier/visibility'] !== false,
    reviewerId: () => desiredAttachment?.reviewer_id || displayedAttachment?.reviewer_id || null,
    ensureRevision,
    hasPendingMutation,
    publish: ({ state, active, versions, drafts, reviewer, pending }) => {
      presentedState = state;
      app
        .updateModelContext({
          structuredContent: {
            exploration_id: state?.id || displayedAttachment?.exploration_id || null,
            viewed_revision_id: viewedRevision(state, active, versions),
            selected_revision_id: state?.selected_revision || null,
            view_id: active === 'explore' ? 'compare' : active || null,
            reviewer_id: reviewer,
            feedback_draft: (drafts || {})[viewedRevision(state, active, versions) || 'overall']?.slice(0, 2000) || '',
            draft_is_generation_authority: false,
            pending_mutation: Boolean(pending || localPending.size),
          },
        })
        .catch(() => {});
    },
  };
  await app.connect();
  applyHostContext(app.getHostContext() || {});
  startNativeController();
})();
