# BugClose 接口自动化测试套件

基于 **pytest + requests** 的接口测试框架，覆盖 BugClose 全部 12 个业务模块，含权限数据隔离与安全加固专项。
用例文档（Excel / Markdown）与自动化脚本共用同一份登记表，编号一一对应。

## 一、当前状态

| 项 | 值 |
| --- | --- |
| 用例总数 | **440**（自动化 435 + 手工 5） |
| 最近一次执行 | **573 passed / 11 xfailed / 0 failed** |
| 通过率 | **100.0%** |
| 耗时 | 39.52s |
| 被测环境 | `http://localhost:8080`（Spring Boot `local` profile + MySQL 8） |

11 条 `xfailed` 是已确认的后端缺陷，用 `xfail(strict=True)` 固化，详见 [缺陷与风险清单](cases/缺陷与风险清单.md)。

## 二、目录结构

```
api-tests/
├── config.py               全局配置（服务地址、账号、前缀、字段长度、DB 连接）
├── conftest.py             全局夹具：身份 / 项目 / 数据工厂 / 清理 / 失败现场
├── pytest.ini              pytest 配置（报告、标记、告警过滤）
├── requirements.txt        依赖清单
├── core/
│   ├── client.py           ApiClient：Bearer + X-Forwarded-For 注入、调用轨迹
│   ├── assertions.py       断言库：ok / created / no_content / rejected / keys / same_time ...
│   ├── data.py             请求体与文件构造工厂（唯一命名、最小合法文件、边界值）
│   ├── db.py               直连 MySQL：建/删套件管理员、落库校验
│   └── tracker.py          资源登记与清理 + 历史遗留清扫
├── tests/                  12 个模块的测试脚本
│   ├── test_auth.py        认证（AUTH-001~028）
│   ├── test_project.py     项目管理（PROJ-001~029）
│   ├── test_requirement.py 需求管理（REQ-001~044）
│   ├── test_testcase.py    测试用例（TC-001~055）
│   ├── test_bug.py         缺陷管理（BUG-001~051）
│   ├── test_doc.py         文档库（DOC-001~052）
│   ├── test_user.py        用户管理（USER-001~046 + M01~M03）
│   ├── test_role.py        角色管理（ROLE-001~031）
│   ├── test_upload.py      图片上传（UP-001~028）
│   ├── test_dashboard.py   统计看板（DASH-001~024）
│   ├── test_permission.py  权限与数据隔离（PERM-001~024）
│   └── test_security.py    安全加固（SEC-001~025）
├── tools/
│   ├── cases/              用例登记表（唯一数据源，每模块一个文件）
│   ├── gen_cases.py        生成 Excel + Markdown 用例文档
│   └── check_coverage.py   校验用例编号与脚本标记一一对应
├── cases/                  生成物：接口测试用例.xlsx / .md / 缺陷与风险清单.md
└── reports/                生成物：report.html / junit.xml
```

## 三、快速开始

### 1. 准备环境

```bash
# 启动被测服务（项目根目录，local profile 提供明文 DB 口令）
mvn spring-boot:run -Dspring-boot.run.profiles=local

# 安装测试依赖
cd api-tests
python -m pip install -r requirements.txt
```

依赖：`requests` `pytest` `pytest-html` `openpyxl` `PyMySQL` `bcrypt`（Python 3.11 实测通过）。

### 2. 跑全量

```bash
cd api-tests
python -m pytest -q
```

Windows 控制台中文乱码时加 `PYTHONIOENCODING=utf-8`（Git Bash）或 `chcp 65001`（cmd）。

### 3. 常用跑法

```bash
python -m pytest tests/test_bug.py -q          # 单模块
python -m pytest -m "case" -q                  # 全部带用例编号的节点
python -m pytest -k "over_length" -q           # 按函数名筛选
python -m pytest -m "not slow" -q              # 跳过并发/大文件等耗时用例
python -m pytest -q -p no:cacheprovider        # 不写 .pytest_cache
python -m pytest -q --lf                       # 只跑上次失败的
```

### 4. 生成 / 更新用例文档

```bash
python tools/gen_cases.py                      # 生成 xlsx + md（执行结果留空）
python tools/gen_cases.py --results            # 回填 reports/junit.xml 的执行结果
python tools/gen_cases.py --md-only            # 只生成 Markdown
python tools/check_coverage.py                 # 校验编号与脚本对齐，退出码非 0 即有缺口
```

> 改用例请改 `tools/cases/<模块>.py` 里的登记表，再重新生成文档。**不要直接编辑 `cases/` 下的生成物。**

### 5. 查看报告

- HTML：`reports/report.html`（自包含单文件，失败用例附最近 5 次 HTTP 调用轨迹）
- JUnit：`reports/junit.xml`（供 CI 消费）
- 终端汇总：`total / passed / failed / skipped / error / pass_rate / run_id`

## 四、配置项（全部可用环境变量覆盖）

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `BUGCLOSE_BASE_URL` | `http://localhost:8080` | 被测服务地址 |
| `BUGCLOSE_TIMEOUT` | `30` | 单请求超时（秒） |
| `BUGCLOSE_ADMIN_USER` | `at_bot_admin` | 套件管理员用户名 |
| `BUGCLOSE_ADMIN_PASSWORD` | `AtBot#2026Pwd` | 套件管理员口令 |
| `BUGCLOSE_AUTO_BOOTSTRAP` | `1` | 登录失败时是否直连 DB 自动创建套件管理员 |
| `BUGCLOSE_KEEP_DATA` | `0` | `1`=保留本次测试数据不清理（排查用） |
| `BUGCLOSE_DB_HOST/PORT/NAME/USER` | 取自 `application*.properties` | DB 连接覆盖 |

DB 口令始终从 `src/main/resources/application-local.properties` 读取（该文件已给出明文）；只有当配置里是 `${ENV}` 占位符时才回退到环境变量。

切换被测环境示例：

```bash
BUGCLOSE_BASE_URL=http://192.168.1.50:8080 \
BUGCLOSE_ADMIN_USER=qa_admin BUGCLOSE_ADMIN_PASSWORD='xxx' \
BUGCLOSE_AUTO_BOOTSTRAP=0 python -m pytest -q
```

## 五、设计要点

### 1. 不碰真实 admin

套件默认使用专用管理员 `at_bot_admin`。登录失败时通过 `core/db.py` 直连 MySQL 建号（bcrypt 哈希），会话结束后删除。
**全程不读取、不修改、不重置真实 `admin` 的口令。** 若要用已有管理员跑，设 `BUGCLOSE_AUTO_BOOTSTRAP=0` 并显式提供账号。

### 2. 数据隔离与清理

- 所有测试数据带保留前缀：项目/角色 `AT_`、用户 `at_bot_`、业务数据标题 `AT...`，并带本次 `RUN_ID`。
- 会话开始时 `sweep_leftovers()` 清扫上次崩溃遗留的同前缀数据。
- 会话结束时 `Tracker.cleanup()` 按「先子后父」回收：**用户 → 业务数据 → 角色 → 项目 → 上传文件**；同类按登记逆序删除，删除失败只记录不抛错。
- `factory.project()` 额外登记一个 purge 动作，兜住「用例直接发请求创建、未走工厂登记」的子资源，避免项目删除守卫导致清理失败。
- 实测跑完后业务库计数与跑前完全一致（projects 11 / bugs 10 / test_cases 10 / documents 10 / users 1 / roles 2），`uploads/` 0 文件、`docs/` 10 文件。

### 3. 限流不互相干扰

后端登录限流按 `用户名 + IP` 分桶（窗口 10 分钟、5 次失败、锁定 10 分钟）。
每个身份绑定独立 `X-Forwarded-For`（管理员 `10.199.0.1`、user1 `.2`、user2 `.3`、无绑定用户 `.4`），负向登录用例从 `ip_pool()` 取 `10.199.1.N` 递增 IP。
**限流用例只用一次性账号，不会锁到真实用户，也不会影响你在浏览器里的登录。**

### 4. 用例编号双向绑定

脚本用 `@pytest.mark.case("BUG-010")` 标注，登记表「自动化脚本」列写 `tests/test_bug.py::test_title_over_length`。
`tools/check_coverage.py` 三向校验：编号有标记、标记有登记、登记指向的函数真实存在。模块级 `pytestmark = pytest.mark.case("BUG")` 只用于分组，不参与编号校验。

### 5. 缺陷用 xfail(strict) 固化

已确认的后端缺陷写成「正向期望 + `xfail(strict=True, reason=...)`」。缺陷未修时套件保持绿色；后端修好后用例变 **XPASS 失败**，强制提醒把断言改回正向。
安全隐患与「现状确认」类不 xfail —— 它们断言的是真实行为，备注里写明风险与建议。

### 6. 断言库的几个坑（写新用例必读）

- `ok(resp)` / `created(resp)` / `rejected(resp)` **返回的是响应体**（`body(resp)`），不是 response 对象。二进制/空响应体返回 `None`，此时必须保留 `resp` 再单独 `status(resp, 200)`。
- 时间戳不要用字符串相等比较：MySQL `DATETIME(6)` 会把纳秒 rounding 到微秒（`.4582397` → `.45824`）。用 `same_time(a, b, hint)`（只比前 19 位）。
- 后端 `Set.of(...)` 的迭代顺序是 JVM 随机化的，**不要断言「仅支持图片格式: [...]」里方括号内的列表内容**。
- 看板是全局统计、无项目参数，断言必须写成「快照 → 操作 → 快照」的增量比较。
- Java `Math.round` 是四舍五入，Python `round` 是银行家舍入，算 `passRate` 期望值用 `math.floor(x + 0.5)`。
- 编辑用户时若带上 `password` 字段，`UserService.update` 会 rehash 并 `revokeByUser`，旧 token 全部失效 → 后续权限断言会变成 401 而不是 403。只改属性时请把 `password` 从请求体里去掉。

## 六、覆盖范围

| 模块 | 用例数 | 重点 |
| --- | --- | --- |
| 认证 | 28 | 登录/登出/me/改密、token 格式与失效、限流、强制改密标记、Bearer 解析 |
| 项目管理 | 29 | CRUD、编号唯一、删除守卫（缺陷/需求/用例/文档）、分页筛选 |
| 需求管理 | 44 | CRUD、状态流转、优先级/所属期筛选、批量导入、字段边界 |
| 测试用例 | 55 | CRUD、执行状态、批量导入导出、模块/优先级筛选、项目存在性 |
| 缺陷管理 | 51 | CRUD、状态流转与指派、序号分配、统计维度、并发创建、字段边界 |
| 文档库 | 52 | 上传/版本历史/下载/删除、分类筛选、扩展名与大小限制 |
| 用户管理 | 49 | CRUD、启用禁用、项目绑定、角色变更、改密吊销 token、最后一个管理员守卫 |
| 角色管理 | 31 | CRUD、内置角色守卫、编码唯一、引用计数 |
| 图片上传 | 28 | 扩展名白名单、5MB 上限、UUID 命名、物理落盘、鉴权访问 |
| 统计看板 | 24 | 四维度计数、状态分布、通过率算法、数据隔离下的可见范围 |
| 权限与数据隔离 | 24 | 管理员全量 vs 普通用户绑定项目、跨项目读写越权、空 projectId 口径 |
| 安全加固 | 25 | 未授权/伪造 token/过期 token、限流绕过、XSS 载荷、错误体信息泄露、越权枚举 |

## 七、已知限制

- 5 条手工用例不纳入自动化：AUTH-027（12 小时 TTL）、AUTH-028（重启失效）、USER-M01~M03（最后一个管理员守卫，需禁用其他管理员，会影响真实环境）。
- token 存储是内存级，**服务重启后所有 token 失效**，套件需重新登录（夹具会自动处理）。
- 限流计数同样是内存级，重启清零。
- 并发用例（BUG-051）标记 `slow`，对数据库压力较大，CI 上可用 `-m "not slow"` 跳过。
- 套件依赖直连 MySQL 建/删专用管理员；若 DB 不可达，请改用 `BUGCLOSE_AUTO_BOOTSTRAP=0` + 现成管理员账号。