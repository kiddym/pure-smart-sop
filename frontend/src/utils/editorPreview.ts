import {
  clampWidth,
  resizePanel,
  sanitizePanel,
  type PanelConfig,
  type PanelState,
} from './collapsiblePanel'

/** 编辑器 Word 预览列的折叠态与宽度（像素）。 */
export type PreviewState = PanelState

/** 预览列宽度边界（像素）。 */
export const PREVIEW_MIN = 240
export const PREVIEW_MAX = 900

/** 预览列宽度配置（默认 460px）。 */
export const PREVIEW_CONFIG: PanelConfig = { defaultWidth: 460, min: PREVIEW_MIN, max: PREVIEW_MAX }

/** 默认：展开、460px。 */
export const PREVIEW_DEFAULTS: Readonly<PreviewState> = {
  collapsed: false,
  width: PREVIEW_CONFIG.defaultWidth,
}

/** 夹到 [MIN, MAX]；非有限值回默认宽度。 */
export function clampPreviewWidth(w: number): number {
  return clampWidth(w, PREVIEW_CONFIG)
}

/** 按像素增量调宽（夹紧），保持 collapsed。 */
export function resizePreview(start: PreviewState, deltaPx: number): PreviewState {
  return resizePanel(start, deltaPx, PREVIEW_CONFIG)
}

/** 校验持久化值：非对象/脏值回默认；宽度夹紧；collapsed 仅认 boolean。 */
export function sanitizePreview(v: unknown): PreviewState {
  return sanitizePanel(v, PREVIEW_CONFIG)
}
