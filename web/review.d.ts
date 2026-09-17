export interface ReviewAction {
  readonly action: {
    readonly name: string;
    readonly context?: Readonly<Record<string, unknown>>;
  };
  readonly request_id: string;
  readonly reviewer_id: string;
  readonly sequence: number;
}
export interface MountReviewOptions {
  reviewerId?: string;
  initialView?: Readonly<Record<string, unknown>>;
  pollInterval?: number;
  loadSurface(view: Readonly<Record<string, unknown>>): Promise<unknown>;
  loadArtifact(id: string): Promise<{ html: string }>;
  loadThumbnail(id: string): Promise<{ thumbnail: unknown }>;
  sendAction(action: ReviewAction): Promise<unknown>;
  onNotice?(text: string): void;
  onSaveStatus?(text: string): void;
  onDiscuss?(context: Readonly<Record<string, unknown>>): void;
  onSnapshot?(surface: unknown): void;
  onExport?(value: {
    format: string;
    body: string;
    revisionId: string;
  }): void | Promise<void>;
}
export function mountReview(
  container: HTMLElement,
  options: MountReviewOptions,
): {
  refresh(): Promise<void>;
  dispose(): void;
  readonly snapshot: unknown;
};
