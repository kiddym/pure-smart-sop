# Parser Tuning Log

按 spec §4.3 一轮一行，每行强制写 trade-off 理由。
严强阈值：P_micro ≥ 0.98 / R_micro ≥ 0.85（无单份 R < 0.6）/ hierarchy ≥ 0.95 / cov ≥ 0.98。

主线 = Tier1 (5 style) + Tier2 (6 manual) = 11 份。Tier3 (24 ack/⚠️ + 1 directory) 仅作不退化约束。

| 轮 | 时间 (UTC) | 改动 | 改的文件 | mainline P_micro | R_micro | F1_micro | hier_micro | cov_micro | min_R 文档 | 备注 / trade-off |
|---|---|---|---|---:|---:|---:|---:|---:|---|---|
| 0 (baseline) | 2026-05-27 | 起点 | — | 0.6154 | 0.7579 | 0.6792 | 1.0000 | 0.9370 | 02记录(0.52) | 主要缺口：P 过低（heuristic over-promote）+ 长尾 R<0.6 |

## 失败模式画像（baseline 时）

- **高 FP**：危险源监控(FP=14, P=0.26) / 有限空间作业(FP=35, P=0.15) / 电厂管理巡视规定(FP=29, P=0.47)
  - 危险源：smart 误把 `1、电气设备配线...` `7、车间内严禁...` 列表项升 heading
  - 有限空间：封面"********有限空间作业" + 签名块 + `(一)落实...` list 误升
- **低 R**：02记录(R=0.52) / 05人力(R=0.59) / 04-质量目标(R=0.35) / 07-监测(R=0.25)
  - 主因：融合式 `N.N、xxx：正文` 子标题在 score_block 长段降权 → 不被 promote
- **hierarchy_micro = 1.0** ✓（已达标，因为 TP 上 level 全对）
- **content_cov 0.937**（差 0.043）：主要在零样式文档（cov 0.83-0.97），分散小问题

## 退出条件

- 达标：以上 5 项全 ✅ + §5 MCP 抽样过
- 停滞：连续 3 轮 micro Δ < 0.005

## 命令参考

```
# 一轮迭代
LAST=$(ls -td .eval-reports/* | grep -v baseline | grep -v _draft | head -1)
LAST_BASE=${LAST:-.eval-reports/baseline}
backend/.venv/bin/python scripts/eval_parser.py --baseline $LAST_BASE/summary.json
# 跑现有 parser 单测确保不退化
cd backend && backend/.venv/bin/python -m pytest tests/unit/parser/ -q
```
