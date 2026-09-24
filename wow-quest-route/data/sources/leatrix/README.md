# Leatrix Plus 原始数据源

`Leatrix_Plus.zip` 是本项目当前待接入的系统飞行时间原始插件包，属于人工提供的源文件，不是脚本生成产物。

- 规范本地路径：`data/sources/leatrix/Leatrix_Plus.zip`
- 当前版本：toc `3.80.12`，内部构建号 `548699`
- SHA-256：`0516c2f75c64a4bc4504a477794e0b8c094389c2db362650279395cdf96665b2`
- 用途：由`scripts/import_leatrix_flight_times.py`解析阵营飞行表，生成项目自己的版本化Timing输入。
- 生命周期：接入和验收完成前保留；派生数据能够独立重建并验证后，原始ZIP不再使用，应移入废纸篓。
- Git：ZIP只保留在本地工作区，不提交；README记录其位置、用途和清理条件。
