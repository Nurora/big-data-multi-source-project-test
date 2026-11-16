# 佛山市地理空间数据采集脚本（可复现）

本目录包含三个可复现脚本，用于采集并处理佛山市的卫星遥感影像
（广东省土地违法行政处罚与司法响应项目·遥感与空间部分）。

## 数据源

| 数据 | 来源 | 许可 |
|---|---|---|
| Sentinel-2 L2A 影像 | 微软 Planetary Computer STAC API（sentinel-2-l2a） | CC BY 4.0 |
| Landsat C2 L2 影像 | 微软 Planetary Computer STAC API（landsat-c2-l2） | USGS，公开 |
| 行政区划边界 | 原始数据/行政区划/guangdong_440000_full.json（高德/省界整理） | 项目内 |

## 采集口径

- 范围：佛山市（adcode=440600，bbox 112.39–113.39°E，22.64–23.57°N）
- 窗口：2019 年冬（2019-11-20 ~ 12-31）与 2024 年冬（2024-11-20 ~ 12-31），
  与中山市试跑口径一致，用于建设用地变化对比
- 选景：按瓦片自动选取云量最低的一景（云量上限 20%）
- 瓦片：核心瓦片 T49QFF（三水/高明）+ T49QGF（禅城/南海/顺德），
  与佛山重叠面积分别约 2,861 km² 与 2,311 km²；边角瓦片 T49QFG/T49QGG 可选
- 波段：Sentinel-2 取 SCL/B02/B03/B04/B08/B11/B12；
  Landsat 取 blue/green/red/nir08/swir16/swir22/qa_pixel
- 下载方式：签名 URL + 8 线程分块下载 + 断点续传（.part 文件续传）
- 产物：原始影像入库 原始数据/哨兵2号影像/、原始数据/Landsat影像/，
  并输出 download_manifest_foshan.json 下载清单（场景、波段、字节数、URL）

## 运行方式

    python 01_download_sentinel2_foshan.py                 # 哨兵：两年全部核心瓦片
    python 01_download_sentinel2_foshan.py --year 2019     # 只下 2019
    python 01_download_sentinel2_foshan.py --dry-run       # 只检索不下载
    python 05_download_landsat_foshan.py                   # Landsat：每年云量最低 2 景
    python 02_process_foshan.py                            # 处理：云掩膜→指数→建设用地变化→5km 网格面板

## 验证记录（2026-11-11）

- 两脚本 --dry-run 检索通过：自动选出的场景云量均低于 3%
  （S2 2019：QFF 1.26% / QGF 2.39%；S2 2024：QFF 0.002% / QGF 0.008%）
- 实际下载与处理管线端到端跑通见 日志与清单/佛山采集验证.md
