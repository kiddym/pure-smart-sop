"""后台清理任务（§53）。

独立 ``scheduler`` 进程（replicas=1，APScheduler，无 broker）承载周期任务；
每个任务亦是 CLI 入口 ``python -m app.tasks.<name> --once``（调度器调用 + 运维手动
触发共用，Q331/Q334）。任务皆状态驱动 + 幂等 + 逐项提交 + 文件先删（Q332）。
"""
