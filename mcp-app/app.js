import { App } from '@modelcontextprotocol/ext-apps';

const app = new App({ name: 'Possibly review', version: '0.1.0' });
const $ = (id) => document.getElementById(id);
let explorationId = null, snapshot = null, revisionId = null, previewRevision = null;
let draftTimer, pollTimer, refreshPromise, previewUrl, exportUrls = [];
let busy = 0, connected = false, sequence = Date.now();
let pendingExplorationId = null;
// Some opaque-origin hosts omit randomUUID even though getRandomValues works.
const requestId = () => Array.from(crypto.getRandomValues(new Uint8Array(16)), value => value.toString(16).padStart(2,'0')).join('');
const reviewerId = `mcp-view-${requestId()}`;

function notice(text = '', error = false) {
  $('notice').textContent = text;
  $('notice').classList.toggle('error', error);
}
function hostStyle(context) {
  if (context?.theme) {
    document.documentElement.style.colorScheme=context.theme;
    document.documentElement.dataset.theme=context.theme;
  }
  for (const [name,value] of Object.entries(context?.styles?.variables || {})) {
    if (name.startsWith('--') && typeof value === 'string') document.documentElement.style.setProperty(name,value);
  }
}
function decode(response) {
  const value = response.structuredContent || JSON.parse(response.content.find(c => c.type === 'text')?.text || '{}');
  if (response.isError || value.status === 'rejected') throw new Error(value.error?.message || response.content?.[0]?.text || 'The request failed.');
  return value;
}
async function call(name, args = {}) {
  if (!connected) throw new Error('The host is not connected yet.');
  return decode(await app.callServerTool({name: `possibly_${name}`, arguments: args}));
}
function grant(action) {
  const fields = [['turns', 1, 20], ['seconds', 1, 3600], ['tools', 1, 100], ['models', 1, 100]];
  const values = fields.map(([id, min, max]) => {
    const value = Number($(id).value);
    if (!Number.isInteger(value) || value < min || value > max) throw new Error(`${id} must be between ${min} and ${max}.`);
    return value;
  });
  return {actions:[action], max_turns:values[0], timeout_seconds:values[1], max_tool_calls:values[2], max_model_calls:values[3], prototype_after_selection:false};
}
function target() {
  if (!explorationId || !revisionId) throw new Error('Open a revision first.');
  return {exploration_id:explorationId, revision_id:revisionId, expected_state_version:snapshot.state_version, request_id:requestId()};
}
async function act(fn, message = 'Saved.') {
  busy++;
  document.querySelectorAll('button').forEach(b => b.disabled = true);
  notice('Working…');
  try { await fn(); await refresh(); notice(message); }
  catch (error) { try { await refresh(); } catch {} notice(error.message, true); }
  finally { busy--; document.querySelectorAll('button').forEach(b => b.disabled = false); updateAvailability(); }
}
function updateAvailability() {
  const active = snapshot?.lifecycle === 'active';
  for (const id of ['select','prototype','save-feedback','refine','finish']) $(id).disabled = busy > 0 || !active || !revisionId;
  $('stop').disabled = busy > 0 || !active;
  $('reopen').disabled = busy > 0 || active || !revisionId;
  $('export').disabled = busy > 0 || !revisionId;
}
function line(tag, text, className) {
  const el = document.createElement(tag); el.textContent = text; if (className) el.className = className; return el;
}
function updateOperations() {
  const area = $('operation-list'); area.replaceChildren();
  for (const op of Object.values(snapshot.operations || {})) {
    const box = line('div', `${op.kind.replaceAll('_',' ')} · ${op.state}`, 'operation');
    if (op.failure) box.append(line('p', typeof op.failure === 'string' ? op.failure : JSON.stringify(op.failure), 'muted'));
    for (const question of op.questions || []) {
      if (question.state !== 'pending') continue;
      const row = line('div', question.prompt, 'question');
      const input = document.createElement('input'); input.setAttribute('aria-label', question.prompt);
      const send = line('button','Answer'); send.onclick = () => act(() => call('answer', {exploration_id:explorationId,operation_id:op.id,question_id:question.id,text:input.value,request_id:requestId()}),'Answer recorded.');
      row.append(input, send); box.append(row);
    }
    area.append(box);
  }
}
async function openRevision(id, save = false) {
  const changed = revisionId !== id || previewRevision === null;
  if (save && revisionId && revisionId !== id) await saveDraft();
  revisionId = id;
  const revision = snapshot.revisions[id];
  if (changed) {
    const reviews = Object.values(snapshot.review_states || {}).sort((a,b) => (b.saved_at || 0)-(a.saved_at || 0));
    $('feedback').value = (snapshot.review_states?.[reviewerId] || reviews.find(review => review.drafts?.[id]))?.drafts?.[id] || '';
  }
  $('revision-note').textContent = `${revision.name || revision.direction_id} · ${revision.kind} · ${id}${revision.superseded ? ' · Superseded' : ''}${snapshot.selected_revision === id ? ' · Chosen' : ''}`;
  document.querySelectorAll('.direction').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.id === id)));
  if (save && snapshot.lifecycle === 'active') await saveDraft();
  if (previewRevision !== id) {
    const expected = id;
    const value = await call('read_artifact', {exploration_id:explorationId, revision_id:id});
    if (revisionId !== expected) return;
    // A generated page gets neither the App SDK nor this bridge, and its own
    // library-enforced CSP denies network access and navigation/form authority.
    const nextUrl = URL.createObjectURL(new Blob([value.result], {type:'text/html'}));
    $('preview').src = nextUrl; $('preview').hidden = false;
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = nextUrl; previewRevision = id;
  }
  updateAvailability();
  publishContext();
}
function refresh() {
  if (!explorationId) return Promise.resolve();
  if (refreshPromise) return refreshPromise;
  const expected = explorationId;
  refreshPromise = (async () => {
    const value = await call('get_exploration', {exploration_id:expected});
    if (explorationId !== expected) return;
    snapshot = value.result;
    $('empty').hidden = true; $('exploration').hidden = false;
    $('intent').textContent = snapshot.brief?.intent || snapshot.context || 'Exploration';
    $('identity').textContent = expected;
    $('lifecycle').textContent = snapshot.lifecycle;
    updateOperations();
    const revisions = Object.values(snapshot.revisions || {});
    $('directions').replaceChildren();
    for (const revision of revisions) {
      const button = line('button', revision.name || revision.direction_id || revision.id, 'direction');
      button.dataset.id = revision.id;
      button.append(line('span', `${revision.kind}${revision.superseded ? ' · superseded' : ''}`));
      button.onclick = () => act(() => openRevision(revision.id, true), 'Review position saved.');
      $('directions').append(button);
    }
    if (!revisionId || !snapshot.revisions[revisionId]) revisionId = snapshot.selected_revision || revisions[0]?.id;
    if (revisionId) await openRevision(revisionId);
    $('review-data').textContent = JSON.stringify({selected_revision:snapshot.selected_revision,decisions:snapshot.decisions,reviews:snapshot.review_states}, null, 2);
    updateAvailability();
  })().finally(() => { refreshPromise = null; });
  return refreshPromise;
}
async function saveDraft() {
  if (!explorationId || snapshot?.lifecycle !== 'active') return;
  await call('save_review_state', {exploration_id:explorationId,revision_id:revisionId || null,view_id:revisionId ? snapshot.revisions[revisionId].direction_id : 'compare',draft:$('feedback').value,reviewer_id:reviewerId,sequence:++sequence,request_id:requestId()});
  publishContext();
}
function publishContext() {
  if (!connected) return;
  app.updateModelContext({structuredContent:{exploration_id:explorationId,viewed_revision_id:revisionId,selected_revision_id:snapshot?.selected_revision || null,feedback_draft:$('feedback').value.slice(0,2000),draft_is_generation_authority:false}}).catch(() => {});
}
async function adopt(id) {
  if (!id) return;
  if (explorationId !== id) { explorationId = id; revisionId = null; previewRevision = null; $('feedback').value = ''; }
  await refresh();
  notice('Reviewing retained exploration.');
}
function download(name, bytes, mime) {
  const url = URL.createObjectURL(new Blob([bytes], {type:mime})); exportUrls.push(url);
  const link = line('a',name); link.href=url; link.download=name; return link;
}
$('refresh').onclick = () => act(refresh, 'Up to date.');
$('open').onclick = () => act(() => adopt($('open-id').value.trim()),'Exploration opened.');
$('start').onclick = () => act(async () => {
  const value = await call('start', {context:$('context').value,request_id:requestId(),grant:grant('explore')});
  await adopt(value.exploration_id);
}, 'Exploration accepted. Progress appears here; you can keep chatting.');
$('select').onclick = () => act(() => call('record_decision',{...target(),action:'select'}),'Choice recorded.');
$('save-feedback').onclick = () => act(() => call('record_decision',{...target(),action:'feedback',text:$('feedback').value}),'Feedback recorded without starting generation.');
$('prototype').onclick = () => act(() => call('make_interactive',{...target(),grant:grant('make_interactive')}),'Prototype work accepted.');
$('refine').onclick = () => act(() => call('refine',{...target(),instruction:$('feedback').value,grant:grant('refine')}),'Refinement accepted.');
$('finish').onclick = () => act(() => call('finish', target()), 'Exploration finished; retained work is still available.');
$('stop').onclick = () => act(() => call('stop',{exploration_id:explorationId,request_id:requestId(),reason:'Stopped from review view'}),'Stop completed.');
$('reopen').onclick = () => act(() => call('reopen',{exploration_id:explorationId,revision_id:revisionId,request_id:requestId()}),'Reopened without new generation.');
$('export').onclick = () => act(async () => {
  const value = await call('export', {exploration_id:explorationId,revision_id:revisionId,request_id:requestId()});
  exportUrls.forEach(url => URL.revokeObjectURL(url)); exportUrls = [];
  const receipt = value.result.receipt;
  $('export-result').replaceChildren(download('prototype.html',receipt.html,'text/html'),document.createTextNode(' · '),download('handoff.json',JSON.stringify(receipt.handoff,null,2),'application/json'));
}, 'Export is ready below. Exporting does not finish the exploration.');
$('feedback').oninput = () => { clearTimeout(draftTimer); draftTimer=setTimeout(() => saveDraft().then(() => notice('Draft saved as context.')).catch(error => notice(error.message,true)),650); };
app.ontoolresult = async response => {
  try { const value=decode(response); if (value.exploration_id) { if (!connected) pendingExplorationId=value.exploration_id; else await adopt(value.exploration_id); } }
  catch (error) { notice(error.message,true); }
};
app.onhostcontextchanged = hostStyle;
app.onteardown = async () => { clearInterval(pollTimer); clearTimeout(draftTimer); if(previewUrl)URL.revokeObjectURL(previewUrl); exportUrls.forEach(url=>URL.revokeObjectURL(url)); return {}; };
try {
  await app.connect(); connected=true;
  hostStyle(app.getHostContext());
  notice('Ready. Open an exploration or start a new one.');
  if (pendingExplorationId) await adopt(pendingExplorationId);
  pollTimer=setInterval(() => { if(explorationId && !busy && !document.hidden)refresh().catch(error=>notice(error.message,true)); },5000);
} catch(error) { notice(`The review view could not connect: ${error.message}`,true); }
