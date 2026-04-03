# Skill: facenamematchskill

## 目的
给定 Photoplus Live 活动号或链接：
1) 拉取活动照片列表并批量下载（展示图、带水印）
2) 对桌牌/名牌区域做 OCR，提取疑似人名文本
3) 输出“人名清单 + 每人一张对应照片”的文档

## 输入
- activityNo（优先）：例如 `17226843`
- 或活动页 URL：例如 `https://live.photoplus.cn/live/pc/17226843/#/live`
- mode：
  - `loose`：宁可多一点误识别、也别漏人（更低阈值）
  - `strict`：更少误识别，但可能漏人

## 输出
- 下载的全量图片
- OCR 中间结果 JSON
- 人名清单 JSON
- 文档：包含人名、对应照片、置信度与原始识别文本、汇总表

## 关键实现要点
- 通过 `GET https://live.photoplus.cn/pic/list` 获取图片列表，需要参数签名：
  - `_t` = 毫秒时间戳
  - `_s` = md5( sorted_query_string_without_quotes + "laxiaoheiwu" )
  - sorted_query_string 的构造：对参数 key 字典序排序；value 使用 JSON stringify；拼成 `k=v&...` 后移除双引号。
- 图片多为 AVIF，需要解码/转存用于文档。
- OCR：优先关注图片下半区域（桌牌/名牌常出现在画面下方）；必要时可以额外扫描中下区域。
- 人名过滤：
  - loose：降低置信度阈值，扩大候选集；允许更多 2-4 字中文串。
  - strict：提高阈值，强过滤常见非人名词（如“签到处/工区/领航者/研修班”等）。
- 安全与合规：不得进行人脸识别身份确认；“匹配”仅限于“照片中出现该姓名文本”。

## 默认阈值建议
- strict：conf >= 0.85
- loose：conf >= 0.35（更激进）

