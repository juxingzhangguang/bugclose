# -*- coding: utf-8 -*-
"""安全加固横切用例（限流、token、注入/XSS、信息泄露、强制改密）。"""
from ._base import C, COMMON_PRE

M = "安全加固"
A = "tests/test_security.py::"
PRE = COMMON_PRE + "；限流用例使用一次性账号 + 独立 X-Forwarded-For，锁定不影响真实用户"
RL_PRE = PRE + "；限流参数：窗口 10 分钟、阈值 5 次失败、锁定 10 分钟（内存级，重启清零）"

CASES = [
    # ---------------------------------------------------------------- 登录限流
    C("SEC-001", M, "连续失败达阈值后锁定", RL_PRE,
      "同一账号同一 IP 连续 5 次错误口令登录，再发起第 6 次",
      "前 5 次均 400「用户名或密码错误」；第 6 次 429，提示含「失败次数过多」与剩余分钟数",
      "P0", "安全", A + "test_rate_limit_locks_after_threshold"),
    C("SEC-002", M, "限流按用户名+IP 分桶", RL_PRE,
      "账号在 IP1 下失败 5 次被锁；换 IP2 用正确口令登录",
      "IP2 登录 200（不同来源互不影响）", "P0", "安全", A + "test_rate_limit_scoped_by_ip"),
    C("SEC-003", M, "限流用户名大小写不敏感", RL_PRE,
      "用小写用户名失败 5 次；再用同一用户名的大写形式 + 正确口令登录",
      "429（key 做了 toLowerCase，大小写变体无法绕过）", "P0", "安全", A + "test_rate_limit_username_case_insensitive"),
    C("SEC-004", M, "成功登录清空失败计数", RL_PRE,
      "失败 4 次 → 正确口令登录 → 再失败 1 次",
      "中间登录 200；最后一次 400 而非 429（计数已重置）", "P1", "安全", A + "test_success_clears_failure_counter"),
    C("SEC-005", M, "锁定期间正确口令也被拒绝", RL_PRE,
      "失败 5 次触发锁定后，用正确口令登录",
      "429（锁定优先于口令校验，防止锁定被正确口令绕过）", "P0", "安全", A + "test_locked_rejects_correct_password"),
    C("SEC-006", M, "伪造 X-Forwarded-For 可绕过限流（现状确认）", RL_PRE,
      "同一账号连续 10 次错误口令登录，每次伪造不同的 X-Forwarded-For",
      "10 次全部 400，始终不出现 429",
      "P0", "安全", A + "test_xff_spoofing_bypasses_rate_limit",
      "安全隐患：AuthController.clientIp 无条件信任 X-Forwarded-For 第一个值，"
      "攻击者逐次伪造即可让限流失效，仍可爆破口令。"
      "建议只在可信代理后解析 XFF，或改用 remoteAddr / 代理层真实 IP 透传"),
    C("SEC-007", M, "多值 XFF 取第一个值", RL_PRE,
      "用 \"IP1, IP2\" 失败 5 次；再分别用单值 IP1、单值 IP2 登录",
      "IP1 命中同一桶返回 429；IP2 不在该桶，正确口令登录 200",
      "P2", "边界", A + "test_xff_first_value_used"),
    C("SEC-008", M, "锁定不影响同 IP 的其他账号", RL_PRE,
      "账号甲在 IP1 下失败 5 次；账号乙在同一 IP1 用正确口令登录",
      "乙登录 200（限流 key 含用户名，不做纯 IP 封禁）", "P1", "安全", A + "test_rate_limit_does_not_affect_other_account"),
    # ---------------------------------------------------------------- token 强度
    C("SEC-009", M, "token 为 64 位随机 hex 且不重复", PRE,
      "同一账号连续登录两次，检查两个 token",
      "均匹配 ^[0-9a-f]{64}$（SecureRandom 32 字节）；两次 token 不同",
      "P0", "安全", A + "test_token_format_and_uniqueness"),
    C("SEC-010", M, "伪造 token 一律拒绝", "服务已启动",
      "GET /api/auth/me，Authorization 分别带 64 个 0、64 个 f、deadbeef、空串、64 个 x",
      "5 组均 401", "P0", "安全", A + "test_forged_token_rejected"),
    C("SEC-011", M, "非法 Authorization 头格式被拒绝", "已取得有效 token",
      "GET /api/auth/me，头依次为 Token abc、Bearer、Basic …、bearer abc（小写）、ABC",
      "5 组均 401（只接受 \"Bearer \" 前缀，大小写敏感）", "P0", "安全", A + "test_malformed_authorization_rejected"),
    C("SEC-012", M, "token 只认 Authorization 头", "已取得有效 token",
      "把有效 token 分别放进 X-Auth-Token、Token、Auth、Cookie 头后 GET /api/auth/me",
      "4 组均 401（不存在备用认证通道）", "P1", "安全", A + "test_token_not_accepted_via_other_headers"),
    # ---------------------------------------------------------------- 注入与 XSS
    C("SEC-013", M, "登录接口 SQL 注入无效", PRE,
      "POST /api/auth/login，username/password 依次传 ' OR '1'='1、admin'--、' UNION SELECT 1,2,3--、'; DROP TABLE users;--",
      "4 组均 400「用户名或密码错误」；响应不含 SQL/Exception 字样；users 表未被破坏",
      "P0", "安全", A + "test_login_sql_injection"),
    C("SEC-014", M, "搜索关键字 SQL 注入与通配符安全", PRE,
      "GET /api/bugs?keyword= 依次传 ' OR '1'='1、%、_、'; DROP TABLE bugs;--",
      "均 200 且返回列表；注入串不匹配任何数据（JPA 参数绑定 + LIKE 转义）",
      "P0", "安全", A + "test_search_keyword_sql_injection"),
    C("SEC-015", M, "存储型 XSS 载荷原样返回（现状确认）", PRE,
      "POST /api/bugs，title/description 传 <script>alert('xss')</script><img src=x onerror=alert(1)>；再 GET 详情",
      "201；字段原样存储与返回；响应 Content-Type 为 application/json 而非 text/html",
      "P1", "安全", A + "test_stored_xss_payload_not_executed_on_server",
      "现状确认：后端不做转义，防护责任在前端。若前端用 innerHTML 渲染标题/描述会形成存储型 XSS。"
      "建议前端统一文本节点渲染，或后端入库做白名单过滤，并补 X-Content-Type-Options: nosniff"),
    C("SEC-016", M, "查询参数路径穿越无效", PRE,
      "GET /api/bugs?keyword= 依次传 ../../application.properties、..\\..\\windows\\win.ini、/etc/passwd",
      "均 200；响应不含 spring.datasource 等配置内容（关键字只做 LIKE 匹配，不触碰文件系统）",
      "P1", "安全", A + "test_path_traversal_in_query"),
    # ---------------------------------------------------------------- 信息泄露
    C("SEC-017", M, "业务错误响应不泄露内部信息", PRE,
      "以用户 1 身份 GET 项目 B 下的缺陷详情，检查响应文本",
      "403；响应不含 Exception、at com.bugclose、java.、SQL、Hibernate、stackTrace",
      "P0", "安全", A + "test_error_body_has_no_stacktrace"),
    C("SEC-018", M, "框架错误体不含堆栈", PRE,
      "POST /api/uploads 用错误的部分名 image；再 GET /api/bugs?status=NOT_A_STATUS",
      "前者 400 且含 timestamp/status/error/path，不含 trace/exception；"
      "后者 400 业务错误体同样不含 trace",
      "P1", "安全", A + "test_framework_error_body_shape",
      "非法枚举被 GlobalExceptionHandler 的 IllegalArgumentException 分支接管，返回 {\"error\":...}；"
      "缺少 multipart 部分名走 Boot 默认错误体，两者形状不同但都不泄露堆栈"),
    C("SEC-019", M, "敏感字段永不出现在响应中", PRE,
      "GET /api/users、GET /api/users/{id}、POST /api/auth/login，检查响应字段",
      "用户视图不含 password/mustChangePassword；登录响应不含 password",
      "P0", "安全", A + "test_sensitive_fields_never_returned"),
    # ---------------------------------------------------------------- 强制改密
    C("SEC-020", M, "强制改密标记无服务端拦截（现状确认）", PRE,
      "创建口令为 admin123 的账号并登录（me.mustChangePassword=true）→ 直接 POST /api/bugs、GET /api/projects",
      "创建缺陷 201；读取项目 200（未改密也能正常操作业务接口）",
      "P0", "安全", A + "test_must_change_password_not_enforced_server_side",
      "安全隐患：mustChangePassword 只是返回给前端的标记，服务端不拦截。"
      "绕过前端直接调接口即可用默认口令长期操作数据。"
      "建议 AuthFilter 对 mustChangePassword=true 的用户只放行 me/change-password/logout"),
    C("SEC-021", M, "改密后旧 token 在全端点失效", PRE,
      "账号登录 → POST /api/auth/change-password → 用旧 token GET 6 个端点",
      "改密 204；6 组均 401（revokeByUser 吊销该用户全部会话，含当前会话）",
      "P0", "安全", A + "test_change_password_revokes_across_endpoints"),
    # ---------------------------------------------------------------- 协议健壮性
    C("SEC-022", M, "畸形 JSON 被拒绝且不泄露异常", PRE,
      "POST /api/bugs，Content-Type: application/json，body 为 {not json",
      "400；响应不含 Exception 字样", "P1", "异常", A + "test_malformed_json_rejected"),
    C("SEC-023", M, "非 JSON Content-Type 被拒绝", PRE,
      "POST /api/bugs，Content-Type: text/plain，body 为 title=x",
      "400 或 415", "P2", "异常", A + "test_wrong_content_type_rejected"),
    C("SEC-024", M, "方法覆盖头不生效", PRE,
      "PUT /api/projects/{id}，附带 X-HTTP-Method-Override: DELETE；再 GET /api/projects",
      "响应不是 204；项目仍存在（未启用 HiddenHttpMethodFilter，无法借头绕过方法级权限）",
      "P1", "安全", A + "test_method_override_header_ignored"),
    C("SEC-025", M, "登出后 token 不可复用", PRE,
      "账号登录 → POST /api/auth/logout → 用旧 token GET /api/auth/me → 再次 POST /api/auth/logout",
      "登出 204；旧 token 取 me 返回 401；重复登出也返回 401（登出接口本身受 AuthFilter 保护，非幂等）",
      "P0", "安全", A + "test_logout_token_cannot_be_reused"),
]