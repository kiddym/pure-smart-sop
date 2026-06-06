<script setup lang="ts">
import { computed } from 'vue'
import ImportSideRail from '@/components/shared/ImportSideRail.vue'
import { useCollapsiblePanel } from '@/composables/useCollapsiblePanel'
import { RAIL_PX, type PanelConfig } from '@/utils/collapsiblePanel'

const props = defineProps<{
  label: string
  side: 'left' | 'right'
  storageKey: string
  config: PanelConfig
}>()

const { state, everShown, onDragStart, resetWidth, collapse, expand } = useCollapsiblePanel(
  props.storageKey,
  props.config,
  props.side,
)

// 折叠按钮朝该列收起方向：left → «，right → »（与 rail 展开箭头相反）。
const collapseArrow = computed(() => (props.side === 'left' ? '«' : '»'))
</script>

<template>
  <div
    class="panel-col"
    :class="side === 'left' ? 'panel-col-left' : 'panel-col-right'"
    :style="{ width: (state.collapsed ? RAIL_PX : state.width) + 'px' }"
  >
    <ImportSideRail v-if="state.collapsed" :label="label" :side="side" @expand="expand" />
    <template v-else>
      <div v-if="everShown" class="panel-body"><slot /></div>
      <div
        class="panel-splitter"
        :class="side === 'left' ? 'splitter-right' : 'splitter-left'"
        title="拖拽调宽，双击重置"
        @pointerdown="onDragStart"
        @dblclick="resetWidth"
      >
        <button
          class="collapse-btn"
          :title="`折叠${label}`"
          @click.stop="collapse"
          @pointerdown.stop
        >{{ collapseArrow }}</button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.panel-col {
  flex: none;
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.panel-col-left { border-right: 1px solid var(--el-border-color-lighter); }
.panel-col-right { border-left: 1px solid var(--el-border-color-lighter); }
.panel-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.panel-splitter {
  position: absolute;
  top: 0;
  width: 6px;
  height: 100%;
  cursor: col-resize;
  z-index: 2;
  touch-action: none;
}
.splitter-right { right: -3px; }
.splitter-left { left: -3px; }
.collapse-btn {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 18px;
  height: 36px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--el-border-color);
  border-radius: 4px;
  background: var(--bg-elevated);
  color: var(--text-tertiary);
  font-size: 12px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s, border-color 0.15s;
}
.panel-splitter:hover .collapse-btn { opacity: 1; }
.collapse-btn:hover { color: var(--el-color-primary); border-color: var(--el-color-primary); }
</style>
