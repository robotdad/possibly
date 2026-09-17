import { html, nothing, css, unsafeCSS } from "lit";
import { repeat } from "lit/directives/repeat.js";
import { A2uiLitElement, A2uiController, A2uiSurface } from "@a2ui/lit/v0_9";
import { MessageProcessor } from "@a2ui/web_core/v0_9";
import {
  catalog,
  catalogId,
  Layout,
  Input,
  Tab,
  Picker,
  Preview,
  Thumbnail,
  Text,
} from "./catalog.js";
import styles from "./workspace.css";

const hosts = new WeakMap();
class ReviewElement extends A2uiLitElement {
  static styles = [
    unsafeCSS(styles),
    css`
      :host {
        display: block;
        min-width: 0;
      }
      .stack {
        display: flex;
        flex-direction: column;
        gap: 14px;
      }
      .actions {
        align-items: center;
        margin: 0;
        gap: 10px;
      }
      .content,
      .panel {
        display: flex;
        flex-direction: column;
        gap: 14px;
      }
      .workspace > *,
      .grid > *,
      .compare-grid > * {
        min-width: 0;
      }
      .compare-grid:has(> :only-child) {
        grid-template-columns: minmax(0, 1fr);
      }
      .workspace.focus > :last-child {
        display: none;
      }
      h4 {
        margin: 0;
        font:
          500 22px/1.3 Georgia,
          serif;
      }
      button[role="tab"][aria-selected="true"] {
        background: var(--accent, #294f3d);
        color: var(--on-accent, #fff);
      }
      .preview {
        margin: 0;
      }
      textarea {
        min-height: 110px;
      }
      button {
        font: inherit;
      }
      .feedback-text {
        white-space: pre-wrap;
      }
      dialog {
        position: fixed;
      }
      .card {
        height: 100%;
      }
      .overall-feedback {
        margin: 12px 0;
      }
    `,
  ];
  createController() {
    return new A2uiController(this, this.constructor.api);
  }
  get host() {
    return hosts.get(this.context?.dataContext.surface);
  }
  emit(name, context = {}) {
    return this.context.dataContext.surface.dispatchAction(
      { event: { name, context } },
      this.context.componentModel.id,
    );
  }
}
// Native text semantics without an optional Markdown runtime; all text remains escaped.
class ReviewText extends ReviewElement {
  static api = Text;
  render() {
    const p = this.controller?.props;
    if (!p) return nothing;
    const value = p.text || "";
    switch (p.variant) {
      case "h1":
        return html`<h1>${value}</h1>`;
      case "h2":
        return html`<h2>${value}</h2>`;
      case "h3":
        return html`<h3>${value}</h3>`;
      case "h4":
        return html`<h4>${value}</h4>`;
      case "h5":
        return html`<h5>${value}</h5>`;
      case "caption":
        return html`<small>${value}</small>`;
      default:
        return html`<span class="feedback-text">${value}</span>`;
    }
  }
}
class ReviewLayout extends ReviewElement {
  static api = Layout;
  render() {
    const p = this.controller?.props;
    if (!p) return nothing;
    const children = repeat(
      p.children || [],
      (c) => (typeof c === "string" ? c : c.id),
      (c) => this.renderNode(c),
    );
    if (p.kind === "details")
      return html`<details ?open=${p.expanded}>
        <summary>${p.label}</summary>
        <div class="stack">${children}</div>
      </details>`;
    if (p.kind === "dialog")
      return html`<dialog
        class="preview-dialog"
        aria-label=${p.label}
        @cancel=${(e) => {
          e.preventDefault();
          this.emit("close_preview");
        }}
      >
        <div class="stack">${children}</div>
      </dialog>`;
    if (p.kind === "tabs")
      return html`<nav role="tablist" aria-label=${p.label}>${children}</nav>`;
    const cls =
      {
        overall: "overall-feedback",
        compare: "compare-grid",
        focused: "workspace focus",
      }[p.kind] || p.kind;
    return html`<div class=${cls}>${children}</div>`;
  }
  updated() {
    const dialog = this.renderRoot.querySelector("dialog");
    if (dialog && !dialog.open) dialog.showModal();
  }
}
class ReviewInput extends ReviewElement {
  static api = Input;
  render() {
    const p = this.controller?.props;
    if (!p) return nothing;
    return html` <label for="input">${p.label}</label
      ><textarea
        id="input"
        .value=${p.value || ""}
        ?disabled=${p.disabled}
        @input=${(e) => {
          p.setValue(e.target.value);
          p.onChange?.();
        }}
      ></textarea>`;
  }
}
class ReviewTab extends ReviewElement {
  static api = Tab;
  render() {
    const p = this.controller?.props;
    return p
      ? html`<button
          class="secondary"
          role="tab"
          aria-selected=${String(p.selected)}
          @click=${p.action}
        >
          ${p.label}
        </button>`
      : nothing;
  }
}
class RevisionPicker extends ReviewElement {
  static api = Picker;
  render() {
    const p = this.controller?.props;
    return p
      ? html`<select
          class="version"
          aria-label=${p.label}
          .value=${p.value}
          @change=${(e) =>
            this.emit("version", { revision_id: e.target.value })}
        >
          ${p.options.map(
            (o) =>
              html`<option value=${o.value} ?selected=${o.value === p.value}>
                ${o.label}
              </option>`,
          )}
        </select>`
      : nothing;
  }
}
// Defense in depth: apply the same offline policy even when a host supplies artifact bytes.
const prototypeCSP =
  "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; font-src data:; media-src data:; connect-src 'none'; frame-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'";
function previewDocument(source, scheme) {
  const doc = new DOMParser().parseFromString(source, "text/html");
  const policy = doc.createElement("meta");
  policy.httpEquiv = "Content-Security-Policy";
  policy.content = prototypeCSP;
  doc.head.prepend(policy);
  for (const style of doc.querySelectorAll("style"))
    style.textContent = style.textContent.replace(
      /\(prefers-color-scheme\s*:\s*(dark|light)\)/gi,
      (_, value) =>
        value.toLowerCase() === scheme ? "(min-width:0px)" : "(max-width:0px)",
    );
  const style = doc.createElement("style");
  style.textContent = `:root{color-scheme:only ${scheme}!important}`;
  doc.head.append(style);
  return "<!doctype html>" + doc.documentElement.outerHTML;
}
class PrototypePreview extends ReviewElement {
  static api = Preview;
  static properties = { document: { state: true }, error: { state: true } };
  render() {
    const p = this.controller?.props;
    if (!p) return nothing;
    return html`<div class="preview">
      <div class="preview-label">
        <span>${p.width} × ${p.height} · ${p.colorScheme} · simulated</span>
        <select
          aria-label=${p.title + " preview size"}
          @change=${(e) => {
            this.actual = e.target.value === "actual";
            this.resize();
          }}
        >
          <option value="fit">Fit to panel</option>
          <option value="actual">Actual size (scroll)</option>
        </select>
        ${p.onExpand
          ? html`<button class="secondary" @click=${p.onExpand}>
              Open large preview
            </button>`
          : nothing}
      </div>
      ${this.error
        ? html`<p role="alert">
            ${this.error}
            <button
              @click=${() => {
                this.key = null;
                this.requestUpdate();
              }}
            >
              Retry preview
            </button>
          </p>`
        : nothing}
      <div class="preview-stage">
        ${this.document === undefined
          ? html`<p>Loading preview…</p>`
          : html`<iframe
              sandbox="allow-scripts"
              referrerpolicy="no-referrer"
              title=${p.title + " preview"}
              .srcdoc=${this.document}
            ></iframe>`}
      </div>
    </div>`;
  }
  updated() {
    const p = this.controller?.props;
    if (!p) return;
    const key = p.revisionId + "-" + p.colorScheme;
    if (this.key !== key) {
      this.key = key;
      this.document = undefined;
      this.error = null;
      this.host
        .artifact(p.revisionId)
        .then((data) => {
          if (this.key === key) {
            this.document = previewDocument(data.html, p.colorScheme);
          }
        })
        .catch((e) => {
          if (this.key === key) this.error = e.message;
        });
    }
    if (!this.observer) {
      this.observer = new ResizeObserver(() => this.resize());
      this.observer.observe(this);
    }
    this.resize();
  }
  resize() {
    const p = this.controller?.props,
      stage = this.renderRoot.querySelector(".preview-stage"),
      frame = this.renderRoot.querySelector("iframe");
    if (!frame || !p) return;
    const scale = this.actual ? 1 : Math.min(1, stage.clientWidth / p.width);
    frame.style.width = p.width + "px";
    frame.style.height = p.height + "px";
    frame.style.transform = `scale(${scale})`;
    frame.style.colorScheme = p.colorScheme;
    stage.style.height = Math.min(p.height * scale, innerHeight * 0.78) + "px";
  }
  disconnectedCallback() {
    super.disconnectedCallback();
    this.observer?.disconnect();
    this.observer = null;
    this.key = null;
  }
}
class RevisionThumbnail extends ReviewElement {
  static api = Thumbnail;
  static properties = { image: { state: true }, failed: { state: true } };
  render() {
    const p = this.controller?.props;
    return p
      ? html`<button
          class="thumbnail-button secondary"
          style="width:100%;padding:0;border:0"
          aria-label=${"Open " + p.title + " preview"}
          @click=${p.action}
        >
          ${this.image
            ? html`<img
                class="thumbnail"
                src=${this.image}
                alt=${p.title + " initial screen"}
              />`
            : html`<div class="empty">
                ${this.failed ? "Open interactive preview" : "Loading concept…"}
              </div>`}
        </button>`
      : nothing;
  }
  updated() {
    const p = this.controller?.props;
    if (!p || this.key === p.revisionId) return;
    this.key = p.revisionId;
    this.host
      .thumbnail(p.revisionId)
      .then((data) => {
        this.image = data.thumbnail;
        this.failed = !data.thumbnail;
      })
      .catch(() => {
        this.failed = true;
      });
  }
}
for (const cls of [
  ReviewText,
  ReviewLayout,
  ReviewInput,
  ReviewTab,
  RevisionPicker,
  PrototypePreview,
  RevisionThumbnail,
])
  customElements.define(cls.api.tagName, cls);
// Import is intentionally referenced so bundlers retain its registration.
void A2uiSurface;
const theme = `
  :host{display:block;--a2ui-color-primary:var(--accent,#294f3d);--a2ui-color-on-primary:var(--on-accent,#fff);
  --a2ui-color-on-background:var(--text,#24322d);--a2ui-color-surface:var(--panel,#fffef9);
  --a2ui-color-on-surface:var(--text,#24322d);--a2ui-color-on-secondary:var(--text,#24322d);
  --a2ui-color-secondary-hover:var(--soft,#e9eee3);--a2ui-color-primary-hover:var(--accent,#294f3d);
  --a2ui-color-border:var(--line,#d7dcd0);--a2ui-text-caption-color:var(--muted,#5b685d);
  --a2ui-button-margin:0;--a2ui-button-padding:9px 14px;--a2ui-button-border-radius:7px;
  --a2ui-font-family-title:var(--review-heading-font,Georgia,serif);--a2ui-column-gap:18px;--a2ui-font-size-xl:30px;--a2ui-font-size-l:22px;
  --a2ui-font-size-m:16px;--a2ui-font-size-s:14px;--a2ui-font-size-xs:12px}
`;
class ReviewSurface extends A2uiSurface {
  static styles = css`
    ${unsafeCSS(theme)}
  `;
}
customElements.define("possibly-review-surface", ReviewSurface);

/** Mount in any host. All IO is injected; no global token, URLs, or process ownership. */
export function mountReview(container, options) {
  let disposed = false,
    timer,
    refreshing,
    again = false,
    snapshot,
    surface,
    element,
    previewInvoker;
  let view = { ...options.initialView },
    sequence = Date.now(),
    saveChain = Promise.resolve(),
    actionChain = Promise.resolve();
  const componentBytes = new Map(),
    artifacts = new Map(),
    thumbnails = new Map();
  const notice = options.onNotice || (() => {}),
    status = options.onSaveStatus || (() => {});
  const reviewerId = options.reviewerId || crypto.randomUUID();
  const cached = (cache, fn, id) => {
    if (!cache.has(id))
      cache.set(
        id,
        Promise.resolve()
          .then(() => fn(id))
          .catch((e) => {
            cache.delete(id);
            throw e;
          }),
      );
    return cache.get(id);
  };
  const host = {
    artifact: (id) => cached(artifacts, options.loadArtifact, id),
    thumbnail: (id) => cached(thumbnails, options.loadThumbnail, id),
  };
  const processor = new MessageProcessor(
    [catalog],
    (action) => handle(action),
    { version: "v0.9.1" },
  );
  const localNames = new Set([
    "discuss",
    "navigate",
    "version",
    "focus",
    "preview",
    "close_preview",
    "mark",
    "compare",
  ]);
  function apply(next) {
    if (next.protocol !== "v0.9.1" || next.catalog_id !== catalogId)
      throw Error(
        "Unsupported review protocol or catalog. Update the host renderer.",
      );
    const fresh = !surface || surface.id !== next.surface_id;
    if (fresh) {
      if (surface)
        processor.processMessages([
          { version: "v0.9.1", deleteSurface: { surfaceId: surface.id } },
        ]);
      processor.processMessages([next.messages[0]]);
      surface = processor.model.getSurface(next.surface_id);
      hosts.set(surface, host);
      surface.onError.subscribe((error) =>
        notice("Review error: " + error.message),
      );
      componentBytes.clear();
      processor.processMessages([next.messages[1]]);
      element = document.createElement("possibly-review-surface");
      element.surface = surface;
      container.replaceChildren(element);
    }
    // Backend reads hydrate drafts only on first mount. Local edits own this model until submission.
    const components = next.messages.find((m) => m.updateComponents)
      .updateComponents.components;
    const changed = components.filter((c) => {
      const bytes = JSON.stringify(c);
      if (componentBytes.get(c.id) === bytes) return false;
      componentBytes.set(c.id, bytes);
      return true;
    });
    if (changed.length)
      processor.processMessages([
        {
          version: "v0.9.1",
          updateComponents: { surfaceId: surface.id, components: changed },
        },
      ]);
    snapshot = next;
    view = { ...next.view };
    sequence = Math.max(sequence, next.sequence);
    options.onSnapshot?.(next);
  }
  function refresh() {
    if (disposed) return Promise.resolve();
    if (refreshing) {
      again = true;
      return refreshing;
    }
    // All observers await the same drain, including a view change during a poll.
    refreshing = (async () => {
      do {
        again = false;
        try {
          const requested = JSON.stringify(view);
          const next = await options.loadSurface({ ...view });
          if (disposed) return;
          if (requested !== JSON.stringify(view)) {
            again = true;
            continue;
          }
          apply(next);
        } catch (e) {
          notice(
            "Connection unavailable. Accepted decisions remain stored. " +
              e.message,
          );
        }
      } while (again && !disposed);
    })().finally(() => {
      refreshing = undefined;
    });
    return refreshing;
  }
  async function rememberView() {
    if (!snapshot || snapshot.lifecycle !== "active") return;
    const revision_id = snapshot.revision_id || "";
    await handle({
      name: "draft",
      surfaceId: surface.id,
      sourceComponentId: "review-navigation",
      timestamp: new Date().toISOString(),
      context: {
        view_id: view.direction_id || "compare",
        revision_id,
        text:
          surface.dataModel.get("/drafts/" + (revision_id || "overall")) || "",
      },
    });
  }
  async function handle(action) {
    if (disposed) return;
    const c = action.context || {},
      name = action.name;
    if (name === "discuss") {
      options.onDiscuss?.(c);
      return;
    }
    if (localNames.has(name)) {
      if (name === "preview" || name === "compare") {
        previewInvoker = document.activeElement;
        while (previewInvoker?.shadowRoot?.activeElement)
          previewInvoker = previewInvoker.shadowRoot.activeElement;
      }
      if (name === "navigate")
        view = {
          ...view,
          direction_id: c.direction_id,
          revision_id: "",
          preview: [],
        };
      if (name === "version") view = { ...view, revision_id: c.revision_id };
      if (name === "focus") view = { ...view, focused: !view.focused };
      if (name === "preview") view = { ...view, preview: [c.revision_id] };
      if (name === "close_preview") view = { ...view, preview: [] };
      if (name === "compare")
        view = { ...view, preview: [...(view.comparing || [])] };
      if (name === "mark") {
        const ids = new Set(view.comparing || []);
        if (ids.has(c.revision_id)) ids.delete(c.revision_id);
        else if (ids.size < 2) ids.add(c.revision_id);
        else return notice("Remove one concept before adding another.");
        view = { ...view, comparing: [...ids] };
      }
      await refresh();
      if (name === "close_preview")
        requestAnimationFrame(() => {
          if (!disposed && previewInvoker?.isConnected) previewInvoker.focus();
        });
      if (name === "navigate" || name === "version") await rememberView();
      return;
    }
    const payload = {
      action,
      request_id: crypto.randomUUID(),
      reviewer_id: reviewerId,
      sequence: ++sequence,
    };
    if (name === "draft") {
      status("Saving draft…");
      saveChain = saveChain
        .catch(() => {})
        .then(() => options.sendAction(payload));
      try {
        await saveChain;
        status("Draft saved");
      } catch (e) {
        status("Draft not saved: " + e.message);
      }
      return;
    }
    // Preserve ordering with in-flight autosaves; never turn a UI gesture into a generation grant.
    actionChain = actionChain
      .catch(() => {})
      .then(async () => {
        await saveChain.catch(() => {});
        try {
          const result = await options.sendAction(payload);
          if (name === "select")
            view = { ...view, ...result.view, revision_id: "", preview: [] };
          if (["feedback", "brief_correction"].includes(name)) {
            const path = "/drafts/" + (c.revision_id || "overall");
            // Do not clear text typed after the submitted text was captured.
            if (surface.dataModel.get(path) === c.text) {
              surface.dataModel.set(path, "");
              await handle({
                ...action,
                name: "draft",
                context: {
                  revision_id: c.revision_id || "",
                  view_id: view.direction_id || "compare",
                  text: "",
                },
              });
            }
          }
          if (name === "export") {
            const kind = c.format || "html";
            const body =
              kind === "html"
                ? result.receipt.html
                : JSON.stringify(result.receipt.handoff, null, 2);
            if (options.onExport)
              await options.onExport({
                format: kind,
                body,
                revisionId: c.revision_id,
              });
            else {
              const url = URL.createObjectURL(
                new Blob([body], {
                  type: kind === "html" ? "text/html" : "application/json",
                }),
              );
              const a = document.createElement("a");
              a.href = url;
              a.download = kind === "html" ? "prototype.html" : "handoff.json";
              a.click();
              setTimeout(() => URL.revokeObjectURL(url), 1000);
            }
          }
          await refresh();
          if (name === "select") await rememberView();
          notice(
            name === "export"
              ? "Exported the reviewed version."
              : "Recorded. Your caller can retrieve this decision.",
          );
        } catch (e) {
          notice("Not accepted: " + e.message);
          await refresh();
        }
      });
    return actionChain;
  }
  refresh();
  timer = setInterval(refresh, options.pollInterval ?? 2000);
  return {
    refresh,
    get snapshot() {
      return snapshot;
    },
    dispose() {
      disposed = true;
      clearInterval(timer);
      container.replaceChildren();
      if (surface)
        processor.processMessages([
          { version: "v0.9.1", deleteSurface: { surfaceId: surface.id } },
        ]);
      artifacts.clear();
      thumbnails.clear();
    },
  };
}
