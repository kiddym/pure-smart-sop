// frontend/src/api/references.ts
import { http } from './http'

// SOP 参考关系 API 客户端（spec D22）。路径相对 http 实例 baseURL（/api/v1）。

export type RelationType = 'authoring_ref' | 'exec_ref' | 'upstream' | 'downstream' | 'related'

export interface ProcedureReference {
  id: string
  source_procedure_id: string
  target_procedure_group_id: string
  relation_type: RelationType
  note: string
  sort_order: number
  target_procedure_id: string | null
  target_code: string | null
  target_name: string | null
  target_version: number | null
}

export interface ReferenceCreate {
  target_procedure_group_id: string
  relation_type: RelationType
  note?: string
  sort_order?: number
}

export const listReferences = async (procedureId: string): Promise<ProcedureReference[]> =>
  (await http.get<ProcedureReference[]>(`/procedures/${procedureId}/references`)).data

export const createReference = async (
  procedureId: string,
  body: ReferenceCreate,
): Promise<ProcedureReference> =>
  (await http.post<ProcedureReference>(`/procedures/${procedureId}/references`, body)).data

export const patchReference = async (
  referenceId: string,
  body: Partial<Pick<ProcedureReference, 'relation_type' | 'note' | 'sort_order'>>,
): Promise<ProcedureReference> =>
  (await http.patch<ProcedureReference>(`/references/${referenceId}`, body)).data

export const deleteReference = async (referenceId: string): Promise<void> => {
  await http.delete(`/references/${referenceId}`)
}
