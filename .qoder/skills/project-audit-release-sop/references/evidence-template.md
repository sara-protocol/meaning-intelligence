# 证据与复盘模板

复制后按项目删减。所有 `<...>` 必须替换；不使用的项写 `not-applicable` 并说明原因。

## 1. 需求到证据 checklist

| ID | 明确需求 | 交付物/命令 | 验收标准 | 证据路径/URL/哈希 | 状态 | 备注 |
|---|---|---|---|---|---|---|
| R01 | `<REQUIREMENT>` | `<ARTIFACT_OR_COMMAND>` | `<CRITERION>` | `<EVIDENCE>` | pass/fail/skipped/blocked/pending-human | `<NOTE>` |

## 2. 审查发现

```text
ID：
领域：delivery / engineering / release / content / security
严重度：blocker / high / medium / low
状态：confirmed / inferred / unknown
用户影响：
证据：<ABSOLUTE_PATH:LINE_OR_COMMAND_OR_JSON_KEY>
根因假设：
修复范围：
验收命令与预期：
人工门：
```

## 3. 修复记录

| 发现 ID | 修改文件 | 生成物 | 执行命令 | 结果 | 回归范围 | 回滚点 |
|---|---|---|---|---|---|---|
| `<ID>` | `<FILES>` | `<GENERATED>` | `<COMMAND>` | pass/fail | `<TESTS>` | `<TARGET>` |

## 4. 发布清单

```text
授权范围：
发布目标：
分支/目录/构建类型：
发布前 HEAD：
包路径/字节数/SHA-256：
staged 文件：
秘密扫描结果：
人工批准记录：
回滚目标与方法：
```

## 5. 发布回执

```text
发布时间：
commit：
build/deployment ID：
公网 URL：
发布结果：
平台限制：
```

## 6. 在线验收

| 检查 | 预期 | 实际 | 状态 | 证据 |
|---|---|---|---|---|
| HTTPS/首页 | `<EXPECTED>` | `<ACTUAL>` | pass/fail/blocked | `<URL_OR_LOG>` |
| 双语/移动端/交互 | `<EXPECTED>` | `<ACTUAL>` | pass/fail | `<REPORT>` |
| 下载/哈希 | `<EXPECTED>` | `<ACTUAL>` | pass/fail | `<MANIFEST>` |
| 媒体/字幕 | `<EXPECTED>` | `<ACTUAL>` | pass/fail | `<PROBE>` |
| API/MCP | `<EXPECTED>` | `<ACTUAL>` | pass/fail/blocked | `<HTTP_TRACE>` |

## 7. 人工签署

| 评审项 | 材料版本/哈希 | 自动检查 | 风险 | 决定 | 时间/方式 |
|---|---|---|---|---|---|
| `<ITEM>` | `<VERSION>` | `<RESULT>` | `<RISK>` | approved/rejected/pending | `<RECORD>` |

## 8. 完成审计

```text
目标是否完整保留：是/否
明确需求数：
pass 数：
fail 数：
skipped 数：
blocked 数：
pending-human 数：
缺失或弱证据：
结论：完成 / 部分完成 / 阻塞
```

## 9. 复盘

```text
有效做法：
返工根因：
覆盖不足的绿色检查：
应自动化步骤：
必须人工保留判断：
下次更早失败门：
可迁移规则：
项目专属事实：
剩余待办与负责人：
```
