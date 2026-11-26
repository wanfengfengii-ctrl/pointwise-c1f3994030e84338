# 榆桥社区剧院无障碍提示服务

这是一个 Python 3.11 标准库实现的固定节目服务。导播登记素材、提交双席稿版、校样并发行。左右席使用独立 SQLite 库装入席件、办理发声或静默首执。工作台按实际首执核对收场并冻结复盘。

## 回归

```text
python3 -B check_project.py
```

## 演示

```text
python3 -B -m unittest tests.test_workday -v
```

## 服务入口

工作台可由 `python3 -m sessions.service --data-dir ./runtime --port 8765` 启动。服务使用 JSON HTTP，可处理素材、稿版、校样、发行、场次、装场、发轮、席端实播、查单、收场和复盘查询。两席数据库位于数据目录下的 `left.db` 和 `right.db`，工作台数据库为 `workstation.db`。

固定动作中的空值表示静默。静默仍需经过席端启播并写入首执，收场不会把计划静默当作已完成。

需要单独访问席端时，可用 `python3 -B -m desks.service --data-dir ./runtime --seat left --port 8766`。右席用 `--seat right --port 8767`。已装场的本席快照与本席首执都在对应席库。工作台的就绪路径为 `/health`。

## 报码联动约定

### 校样与发行

`POST /drafts` 的每项轮次保留 `number`、`lo`、`hi`。联动轮提供 `light_cases` 取代固定 `left` 和 `right`。同一稿内可以同时有固定轮和联动轮。每张灯况表至少一行，由 `left_light`、`right_light` 及非空 `allowed` 组成。每行灯号组合唯一，灯号是整数，布尔值不算。每席在该轮最多出现四种不同灯号。表只须列出可能发生的组合，现场以表内组合为约定。

`allowed` 的每项含 `left` 和 `right`。动作沿用原格式，`null` 为静默。每席本轮最多有两种不同的非空动作，以素材号、修订号和起拍区分。每个列出的动作对都须通过原拍窗和盖话校样。`GET /drafts/{id}/preview` 沿原轮序反映联动轮的校样问题，包括有非法播法或整表无法共同兑现的轮。结构非法返回 422。`POST /editions` 仍收 `draft_id`，有拍窗、盖话或整表无解问题时返回 409 且不生成发行。

每一合法灯况最终得到该行允许的一对动作。发送席凭本席灯号决定本席动作和 0 或 1 的报码。接收席凭本席灯号和实际收到的位值决定动作。采用无报码办法时，两席各凭本席灯号决定动作。多种办法均可行时，允许选任一种。联动轮在发行响应和 `GET /editions/{id}` 的 `rounds` 项中以 `sender` 表示固定方向，值为 `left`、`right` 或 `null`。`GET /editions/{id}?seat=left` 或 `?seat=right` 交付能独立执行的本席指令。调用方将席件原样装场，席件内部编码由实现决定。重领同一发行及席件时保留原指令、动作和素材修订。

### 现场办理与收场

沿用 `POST /sessions`、`POST /installations` 和 `POST /sessions/{session_id}/rounds`。以下路径中的 `id` 取发轮回包的 `packet_id`，请求体中的 `packet` 取同一个完整发轮回包。工作台 HTTP 和对应的席端 HTTP 都可办理联动请求。导播停用时，值班员可直接向已装场的席端交件。

- `POST /rounds/{id}/observe` 接收 `seat`、`request_id`、`packet`、`light`，记录该席本轮灯号。
- `POST /rounds/{id}/signal` 接收 `seat`、`request_id`、`packet`、`signal`，只交给本轮接收席。`signal` 是发送席首执中的 `signal` 原件，包含 `packet`、`from_seat`、`from_request_id`、`bit`。转发方只转发服务原件，可以欠送、错投、重送或丢失回包。席间交件无需接入鉴权服务。
- 未齐时返回 202 和 `{"status":"pending"}`。齐备时返回 200 和 `{"receipt": ...}`。首执沿原字段记录 `action`、`request_id`、`sequence` 和归属，增加 `light` 和 `signal`。本席 `request_id` 取记灯请求号。发送席的 `signal` 为本席出票，接收席的 `signal` 为本席实用原件，无报码时为 `null`。
- 已受理的记灯和收码分别按各自原请求号续办。条件已齐时，本席输入和它触发的首执须同次生效。已齐后重投任何一个原请求都返回同一固定首执。`GET /receipts/{request_id}?seat=left` 或 `?seat=right` 返回对应的待办或首执，直接查本席时可省略席位。未知请求返回 404。查询本身不可触发播出。
- 错场、错轮、错版或错发送席的报码件，本轮未定义的本席灯号，已受理输入的改参、同一输入换新号重办，均返回 409 且保留已受理结果。请求号按席判定。同一号改投另一操作也算改参。联动轮拒绝直接 `play`，固定轮继续使用原 `play`。

`POST /sessions/{session_id}/close` 仍以两席实际首执为准。尚缺本席灯号或报码造成未办时，收场继续报欠办。按返回的复盘号调用 `GET /reports/{id}`，逐轮的 `left` 和 `right` 均保留各自首执。联动轮按首执列出实际发声或静默、灯号、报码及出票请求出处，原号再收场或重开后领回的内容一致。普通轮继续使用原响应。

### 报码样例

先通过 `POST /clips` 依序登记文案「请留步」及片长 2、文案「前方进入安静场景」及片长 3。在空库中两者初始素材号为 1 和 2，修订号均为 1。若在已有库演练，改用登记回包的编号。下表的 S、L 分别表示对应素材在起拍 0 的固定动作，`—` 表示静默。两席任一方可播短句或长句时，四行允许表为：

| 左灯 | 右灯 | 可选播法（左，右） |
| --- | --- | --- |
| 0 | 0 | (S, —) 或 (—, S) |
| 0 | 1 | (L, —) 或 (—, L) |
| 1 | 0 | (L, —) 或 (—, L) |
| 1 | 1 | (S, —) 或 (—, S) |

只允许右席发声时，可直接提交以下稿版。

```json
{
  "rounds": [
    {
      "number": 1, "lo": 0, "hi": 3,
      "light_cases": [
        {"left_light": 0, "right_light": 0, "allowed": [{"left": null, "right": {"clip_id": 1, "revision": 1, "start": 0}}]},
        {"left_light": 0, "right_light": 1, "allowed": [{"left": null, "right": {"clip_id": 2, "revision": 1, "start": 0}}]},
        {"left_light": 1, "right_light": 0, "allowed": [{"left": null, "right": {"clip_id": 2, "revision": 1, "start": 0}}]},
        {"left_light": 1, "right_light": 1, "allowed": [{"left": null, "right": {"clip_id": 1, "revision": 1, "start": 0}}]}
      ]
    }
  ]
}
```

上述稿版只能由左席报码。把四行的发声统一改给左席后，只能由右席报码。若表中只有 00 允许两席静默、01 允许仅左席播 S、10 允许仅右席播 S，则各行单独都合法，但整轮拒发。另一个拒发例为右灯恒为 0，左灯 0、1、2 分别要求右席播 S、播 L、静默，左席全程静默。

用只准右席发声的发行开两个场。两场右灯都是 0，左灯分别为 0 和 1。第一场先让右席记灯，第二场先把左席报码件交右席。右席在 202 时没有实播首执。两场条件齐全后分别实播 S 和 L。把第一场原码投到第二场时应拒绝。可在第二场收码后、记灯前重开右席，把最终记灯响应视作失答，再用原号查回，确认左右各只有一条首执。收场前试查欠办，收场后按复盘号核对本席灯号和实际用码。

`.pointwise-runtime.json` 以版本 1 的 API 清单启动工作台，`setup` 为准备命令列表，`start`、`verify`、`demo` 各是一条 argv。本次交付让 `verify` 连同原回归核验灯况、到件顺序和实播事实，断言失败应退出非零。让 `demo` 展示上述右席灯号相同却兑现不同句子的场次及收场回读。
