# facenamematchskill

把 Photoplus Live 活动页的照片批量下载下来，对桌牌/名牌做 OCR 抽取“出现过的人名”，并生成“人名清单 + 对应照片”的文档。

## 你能得到什么
- 全量下载（默认：活动号所有展示图，带水印）
- OCR 提取桌牌/名牌文字 → 人名候选列表
- 每个名字挑一张“名字文字清晰可见”的对应照片
- 生成可打印的中文文档

## 重要限制（必须接受）
- **不做基于人脸的身份确认/跨照片人物匹配**。
- “对应照片”的含义是：该照片中出现了该姓名文本（桌牌/名牌）。
- OCR 有漏检/误识别风险。

## 使用方式（在这个工作区）
### 1) 生成“更全但更杂”的人名清单（宽松阈值）
```bash
python skills/facenamematchskill/run.py --activity 17226843 --mode loose
```

### 2) 生成“更准但可能漏人”的人名清单（严格阈值）
```bash
python skills/facenamematchskill/run.py --activity 17226843 --mode strict
```

## 参数说明
- `--activity`：活动号（例如 17226843）
- `--mode`：`loose` / `strict`
  - loose：宁可多误识别、尽量不漏人（默认阈值更低）
  - strict：更保守（阈值更高）
- `--out`：输出目录（默认：`photoplus_<activity>`）

## 输出目录结构
- `photoplus_<activity>/all_images/`：下载的展示图（通常为 avif）
- `photoplus_<activity>/ocr_name_best.json`：每个候选名字对应的“最佳置信度命中记录”
- `photoplus_<activity>/selected_people.json`：最终用于出文档的人名条目
- `photoplus_<activity>/selected_jpg/`：写入文档用的 jpg

