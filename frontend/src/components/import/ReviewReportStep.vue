<script setup lang="ts">
import { computed } from 'vue'
import type { ParseMode, ParseResponse, ValidationReport } from '@/types/parse'

// step3：解析中 spinner / 解析失败（含 standard 模板报告）/ 解析成功概览（含 review 预告）。
const props = defineProps<{
  parsing: boolean
  parseResult: ParseResponse | null
  parseMode: ParseMode
  errorMessage: string
  errorValidation: ValidationReport | null
  reviewCount: number
}>()

const RULE_TAG = { pass: 'success', warning: 'warning', error: 'danger' } as const
function ruleTag(level: string): 'success' | 'warning' | 'danger' {
  return RULE_TAG[level as keyof typeof RULE_TAG] ?? 'info'
}

const meta = computed(() => props.parseResult?.metadata ?? null)
const warnings = computed(() => props.parseResult?.warnings ?? [])
const validation = computed(() => props.parseResult?.validation ?? null)
const DETECT_LABEL: Record<string, string> = {
  first_styled_heading: '首个样式标题',
  toc_field_end: '目录域结束处',
  heuristic_heading: '启发式首标题',
  cover_skip: '跳过封面',
}
</script>

<template>
  <div class="report-step">
    <!-- 解析中 -->
    <div v-if="parsing" v-loading="true" class="parsing" element-loading-text="正在解析文档，请稍候…">
      <p class="parsing-text">大文档可能需要十几秒；超过 30 秒将自动超时提示。</p>
    </div>

    <!-- 解析失败 -->
    <template v-else-if="errorMessage">
      <el-alert type="error" :title="errorMessage" :closable="false" show-icon class="block" />
      <el-card v-if="errorValidation" shadow="never" class="block">
        <template #header>模板校验报告 · {{ errorValidation.summary }}</template>
        <ul class="rules">
          <li v-for="r in errorValidation.rules" :key="r.code">
            <el-tag size="small" :type="ruleTag(r.level)">{{ r.code }}</el-tag>
            <span class="rmsg">{{ r.message }}</span>
          </li>
        </ul>
      </el-card>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="block"
        title="提示：可返回上一步改用「智能模式」，对零样式 / 不规范文档更宽容。"
      />
    </template>

    <!-- 解析成功 -->
    <template v-else-if="parseResult && meta">
      <el-descriptions :column="3" border class="block">
        <el-descriptions-item label="识别章节数">{{ meta.total_chapters }}</el-descriptions-item>
        <el-descriptions-item label="图片">{{ meta.image_count }}</el-descriptions-item>
        <el-descriptions-item label="表格">{{ meta.table_count }}</el-descriptions-item>
        <el-descriptions-item label="正文起点判定">
          {{ DETECT_LABEL[meta.body_start_detected_by] ?? meta.body_start_detected_by }}
        </el-descriptions-item>
        <el-descriptions-item label="解析模式">{{ parseMode }}</el-descriptions-item>
        <el-descriptions-item label="耗时">{{ meta.parse_time_ms }} ms</el-descriptions-item>
      </el-descriptions>

      <el-alert
        v-if="reviewCount > 0"
        type="warning"
        :closable="false"
        show-icon
        class="block"
        :title="`智能模式识别出 ${reviewCount} 个低置信度节点，将在下一步以黄色标出供你确认。`"
      />

      <el-card v-if="validation && validation.rules.length" shadow="never" class="block">
        <template #header>模板校验 · {{ validation.summary }}</template>
        <ul class="rules">
          <li v-for="r in validation.rules" :key="r.code">
            <el-tag size="small" :type="ruleTag(r.level)">{{ r.code }}</el-tag>
            <span class="rmsg">{{ r.message }}</span>
          </li>
        </ul>
      </el-card>

      <el-card v-if="warnings.length" shadow="never" class="block">
        <template #header>解析提示（{{ warnings.length }}）</template>
        <ul class="warns">
          <li v-for="(w, i) in warnings" :key="i"><b>[{{ w.stage }}]</b> {{ w.message }}</li>
        </ul>
      </el-card>
    </template>

    <el-empty v-else description="尚无解析结果" />
  </div>
</template>

<style scoped>
.report-step {
  padding: 8px 0;
}
.block {
  margin-bottom: 14px;
}
.parsing {
  min-height: 160px;
}
.parsing-text {
  text-align: center;
  color: #909399;
  padding-top: 80px;
}
.rules,
.warns {
  margin: 0;
  padding-left: 4px;
  list-style: none;
}
.rules li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}
.warns li {
  padding: 4px 0;
  color: #606266;
}
.rmsg {
  color: #606266;
  font-size: 13px;
}
</style>
