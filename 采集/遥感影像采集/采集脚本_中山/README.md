# 中山市地理空间数据采集脚本与跑通结果（历史版本）

2026-10 中山试跑（项目遥感与空间部分的第一次端到端验证），
全部脚本与跑通产物归档于此；佛山版（采集脚本_佛山/）由本套脚本仿照而来。

## 脚本
- 01_download_sentinel2.py   哨兵二号 L2A 采集（Planetary Computer，场景硬编码为中山两瓦片）
- 05_download_landsat.py     Landsat C2 L2 采集（跨传感器验证）
- 06_landsat_validate.py     Landsat 影像可用性验证
- 04_extract_osm.py          OSM 路网/设施提取（辅助数据源）
- 02_process_zhongshan.py    处理管线：云掩膜→指数→建设用地变化→5km 网格面板
- 03_visualize.py            可读版可视化（变化图/网格图，镇街地名+比例尺）
- 08_preview_rasters.py      栅格预览图生成

## 跑通结果
- 跑通结果/*.png：建设用地 2019/2024、变化图、有效像元、NDVI、Landsat 建设用地预览
- 空间面板_中山_5km网格.csv / 含OSM密度.csv：网格级空间面板

## 验证记录
- 影像：S2 2019-12-11（QGE 1.1% / QGF 2.4%）、2024-12-19（0.05% / 0.008%），Landsat 2019/2024 各 1 景
- 处理：10m 公共网格，云/无效像元占比 2019/2024 见当时日志（日志与清单/质量日志.md）
