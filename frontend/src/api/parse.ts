import type { AxiosProgressEvent } from 'axios'
import { http } from './http'
import type {
  AssetUploadResult,
  ImportRequest,
  ParseMethod,
  ParseMode,
  ParseResponse,
  UploadResult,
} from '@/types/parse'
import type { ProcedureMeta } from '@/types/procedure'

const MULTIPART = { headers: { 'Content-Type': 'multipart/form-data' } }

// 上传 docx 到临时区（multipart），返回 upload_token（纯文件系统，Q341）。
export const uploadDocx = async (
  file: File,
  onProgress?: (e: AxiosProgressEvent) => void,
): Promise<UploadResult> => {
  const form = new FormData()
  form.append('file', file)
  return (
    await http.post<UploadResult>('/uploads', form, {
      ...MULTIPART,
      onUploadProgress: onProgress,
    })
  ).data
}

export const fetchParseMethods = async (): Promise<ParseMethod[]> =>
  (await http.get<ParseMethod[]>('/parse/methods')).data

// 解析临时 docx（不落库，两步式 §9.1）。客户端超时放宽到 45s，让后端 30s 线程超时
// （PARSE_TIMEOUT 504，Q345）先于 axios 默认 30s abort 到达，得到精确错误码。
export const parseDocx = async (
  uploadToken: string,
  parseMode: ParseMode,
): Promise<ParseResponse> =>
  (
    await http.post<ParseResponse>(
      '/parse',
      { upload_token: uploadToken, parse_mode: parseMode },
      { timeout: 45_000 },
    )
  ).data

// 导入解析结果创建新程序（向导 step5）。
export const importProcedure = async (payload: ImportRequest): Promise<ProcedureMeta> =>
  (await http.post<ProcedureMeta>('/procedures/import', payload)).data

export type ImportStage = 'uploading' | 'parsing' | 'creating'

// 上传 + 解析（不落库）。triage 在调用方按 warnings.severity 决定是否强确认。
export const uploadAndParse = async (
  file: File,
  onStage?: (stage: ImportStage, uploadPct?: number) => void,
): Promise<{ uploadToken: string; parsed: ParseResponse }> => {
  onStage?.('uploading', 0)
  const up = await uploadDocx(file, (e) => {
    if (e.total) onStage?.('uploading', Math.round((e.loaded / e.total) * 100))
  })
  onStage?.('parsing')
  const parsed = await parseDocx(up.upload_token, 'smart')
  return { uploadToken: up.upload_token, parsed }
}

// 用审查后的 chapters + 全量 warnings 快照落库创建草稿。
export const importParsed = async (
  args: {
    uploadToken: string
    folderId: string
    name: string
    chapters: ParseResponse['chapters']
    importNotes: ParseResponse['warnings']
  },
  onStage?: (stage: ImportStage) => void,
): Promise<ProcedureMeta> => {
  onStage?.('creating')
  return importProcedure({
    name: args.name,
    folder_id: args.folderId,
    upload_token: args.uploadToken,
    chapters: args.chapters,
    import_notes: args.importNotes,
  })
}

// 编辑器图片直传（Q214）：sha256 去重即时入库，返回永久 asset URL。
export const uploadAsset = async (
  procedureId: string,
  file: File,
): Promise<AssetUploadResult> => {
  const form = new FormData()
  form.append('file', file)
  return (
    await http.post<AssetUploadResult>(`/procedures/${procedureId}/assets`, form, MULTIPART)
  ).data
}
