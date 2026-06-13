import { http } from './http'

// 步骤监护核查点 API 客户端（spec §6 编写侧、D2/D3）。
// 路径相对 http 实例 baseURL（/api/v1）；列表挂在 node 下，单条增改删用 checkId。

export interface NodeCheck {
  id: string
  node_id: string
  procedure_id: string
  check_type: 'ocr' | 'safety'
  modality: 'visual' | 'voice' | 'dual'
  severity: 'info' | 'warn' | 'critical'
  trigger: 'on_enter' | 'manual' | 'continuous'
  prompt: string
  keep_evidence: boolean
  confidence_threshold: number | null
  params: Record<string, unknown>
  sort_order: number
}

export type NodeCheckCreate = Omit<
  NodeCheck,
  'id' | 'node_id' | 'procedure_id' | 'sort_order'
> & {
  sort_order?: number
}

export const listChecks = async (nodeId: string): Promise<NodeCheck[]> =>
  (await http.get<NodeCheck[]>(`/nodes/${nodeId}/checks`)).data

export const createCheck = async (
  nodeId: string,
  body: NodeCheckCreate,
): Promise<NodeCheck> => (await http.post<NodeCheck>(`/nodes/${nodeId}/checks`, body)).data

export const patchCheck = async (
  checkId: string,
  body: Partial<NodeCheck>,
): Promise<NodeCheck> => (await http.patch<NodeCheck>(`/checks/${checkId}`, body)).data

export const deleteCheck = async (checkId: string): Promise<void> => {
  await http.delete(`/checks/${checkId}`)
}
