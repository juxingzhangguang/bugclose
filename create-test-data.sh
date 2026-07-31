#!/bin/bash
# BugClose 测试数据创建脚本
# 保留已有数据，追加创建 10 个项目 + 10 Bug + 10 测试用例 + 10 文档

BASE_URL="http://localhost:8080"

echo "=========================================="
echo "  BugClose 测试数据创建脚本"
echo "=========================================="

# -------------------------------------------
# 第零步：清理上次失败的遗留数据（projectId 为 null 的文档）
# -------------------------------------------
echo ""
echo "[0/7] 清理遗留数据..."
ORPHAN_DOCS=$(curl -s "$BASE_URL/api/docs" | jq -r '.[] | select(.projectId == null) | .id')
for did in $ORPHAN_DOCS; do
  curl -s -X DELETE "$BASE_URL/api/docs/$did" > /dev/null
done
ORPHAN_COUNT=$(echo "$ORPHAN_DOCS" | grep -c '[0-9]' || true)
echo "  已清理 ${ORPHAN_COUNT} 条遗留文档"

# -------------------------------------------
# 第一步：创建 10 个项目
# -------------------------------------------
echo ""
echo "[1/7] 创建 10 个项目..."

create_project() {
  curl -s -X POST "$BASE_URL/api/projects" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$1\",\"code\":\"$2\",\"description\":\"$3\"}"
}

P1=$(create_project "支付中心" "PAY" "统一支付平台，支持多渠道支付接入")
P2=$(create_project "客户关系管理" "CRM" "客户信息管理与跟进系统")
P3=$(create_project "电商平台" "MALL" "B2C在线商城，支持商品浏览与下单")
P4=$(create_project "办公自动化" "OA" "内部审批考勤与流程管理")
P5=$(create_project "数据中台" "DATA" "数据采集、清洗与报表分析平台")
P6=$(create_project "物流管理" "WMS" "仓储出入库与库存管理系统")
P7=$(create_project "人力资源" "HRM" "招聘、薪酬与绩效管理平台")
P8=$(create_project "在线教育" "EDU" "课程管理与直播授课平台")
P9=$(create_project "社交媒体" "SNS" "动态发布、关注与评论系统")
P10=$(create_project "预约挂号" "HOSP" "医院在线挂号与就诊管理")

ID1=$(echo "$P1" | jq -r '.id')
ID2=$(echo "$P2" | jq -r '.id')
ID3=$(echo "$P3" | jq -r '.id')
ID4=$(echo "$P4" | jq -r '.id')
ID5=$(echo "$P5" | jq -r '.id')
ID6=$(echo "$P6" | jq -r '.id')
ID7=$(echo "$P7" | jq -r '.id')
ID8=$(echo "$P8" | jq -r '.id')
ID9=$(echo "$P9" | jq -r '.id')
ID10=$(echo "$P10" | jq -r '.id')

echo "  项目ID: $ID1, $ID2, $ID3, $ID4, $ID5, $ID6, $ID7, $ID8, $ID9, $ID10"

if [ -z "$ID1" ] || [ "$ID1" = "null" ]; then
  echo "  ❌ 项目创建失败！响应: $P1"
  exit 1
fi
echo "  ✅ 10 个项目创建成功"

# -------------------------------------------
# 第二步：创建 10 个 Bug（先创建为 NEW，后续流转状态）
# -------------------------------------------
echo ""
echo "[2/7] 创建 10 个 Bug..."

create_bug() {
  curl -s -X POST "$BASE_URL/api/bugs" \
    -H "Content-Type: application/json" \
    -d "{\"projectId\":$1,\"title\":\"$2\",\"description\":\"$3\",\"severity\":\"$4\",\"priority\":\"$5\",\"assignee\":\"$6\",\"environment\":\"$7\",\"module\":\"$8\",\"reporter\":\"$9\"}"
}

B1=$(create_bug "$ID1" "微信支付回调超时导致订单状态不一致" "用户完成微信支付后回调接口超时导致订单仍显示未支付" "CRITICAL" "URGENT" "张伟" "生产环境" "支付网关" "李明")
B2=$(create_bug "$ID2" "客户导出Excel时中文乱码" "导出超过1000条客户数据时Excel中中文姓名出现乱码" "HIGH" "HIGH" "王芳" "测试环境" "客户管理" "赵强")
B3=$(create_bug "$ID3" "购物车商品数量为0时仍可提交订单" "前端未校验数量为0的场景后端也缺少拦截导致生成金额为0的异常订单" "HIGH" "URGENT" "刘洋" "测试环境" "购物车" "陈静")
B4=$(create_bug "$ID4" "审批流程中审批人离职后流程卡住" "当审批流程中的某一审批人已离职流程无法自动跳过导致后续审批无法进行" "MEDIUM" "HIGH" "孙丽" "生产环境" "审批流程" "周杰")
B5=$(create_bug "$ID5" "日报数据聚合时内存溢出" "当数据量超过50万条时日报聚合任务OOM导致服务重启" "CRITICAL" "URGENT" "吴磊" "生产环境" "数据报表" "郑华")
B6=$(create_bug "$ID6" "扫码入库时条码重复未提示" "仓库扫码入库时如果条码已存在系统未给出任何提示直接覆盖原记录" "MEDIUM" "MEDIUM" "马超" "仓库环境" "入库管理" "黄涛")
B7=$(create_bug "$ID7" "薪资计算未考虑社保基数年度调整" "7月份社保基数调整后系统仍使用旧基数计算导致薪资不准确" "HIGH" "HIGH" "林婷" "生产环境" "薪酬模块" "何敏")
B8=$(create_bug "$ID8" "直播课程在Safari浏览器无法播放" "Safari 17上HLS直播流无法播放Chrome正常疑似编码格式兼容问题" "MEDIUM" "MEDIUM" "杨帆" "测试环境" "直播模块" "徐亮")
B9=$(create_bug "$ID9" "动态评论数显示与实际不符" "帖子详情页评论数缓存未更新显示数量比实际多刷新后恢复" "LOW" "LOW" "韩雪" "生产环境" "社区动态" "曹阳")
B10=$(create_bug "$ID10" "挂号成功后短信通知延迟超过30分钟" "用户完成挂号后确认短信延迟严重部分用户反馈超过30分钟才收到" "LOW" "MEDIUM" "谢楠" "生产环境" "挂号服务" "冯娟")

BID1=$(echo "$B1" | jq -r '.id')
BID2=$(echo "$B2" | jq -r '.id')
BID3=$(echo "$B3" | jq -r '.id')
BID4=$(echo "$B4" | jq -r '.id')
BID5=$(echo "$B5" | jq -r '.id')
BID6=$(echo "$B6" | jq -r '.id')
BID7=$(echo "$B7" | jq -r '.id')
BID8=$(echo "$B8" | jq -r '.id')
BID9=$(echo "$B9" | jq -r '.id')
BID10=$(echo "$B10" | jq -r '.id')

echo "  Bug ID: $BID1, $BID2, $BID3, $BID4, $BID5, $BID6, $BID7, $BID8, $BID9, $BID10"

# -------------------------------------------
# 第三步：流转 Bug 状态到目标值
# -------------------------------------------
echo ""
echo "[3/7] 流转 Bug 状态..."

# Bug 状态流转规则: NEW→IN_PROGRESS, IN_PROGRESS→RESOLVED, RESOLVED→CLOSED, NEW→CLOSED
transition_bug() {
  curl -s -X PUT "$BASE_URL/api/bugs/$1/status" \
    -H "Content-Type: application/json" \
    -d "{\"status\":\"$2\",\"assignee\":\"$3\"}" > /dev/null
}

# B1: 目标 NEW（已是 NEW，无需操作）
# B2: 目标 IN_PROGRESS（NEW→IN_PROGRESS）
transition_bug "$BID2" "IN_PROGRESS" "王芳"
# B3: 目标 NEW（已是 NEW，无需操作）
# B4: 目标 IN_PROGRESS（NEW→IN_PROGRESS）
transition_bug "$BID4" "IN_PROGRESS" "孙丽"
# B5: 目标 RESOLVED（NEW→IN_PROGRESS→RESOLVED）
transition_bug "$BID5" "IN_PROGRESS" "吴磊"
transition_bug "$BID5" "RESOLVED" "吴磊"
# B6: 目标 NEW（已是 NEW，无需操作）
# B7: 目标 CLOSED（NEW→CLOSED）
transition_bug "$BID7" "CLOSED" "林婷"
# B8: 目标 IN_PROGRESS（NEW→IN_PROGRESS）
transition_bug "$BID8" "IN_PROGRESS" "杨帆"
# B9: 目标 RESOLVED（NEW→IN_PROGRESS→RESOLVED）
transition_bug "$BID9" "IN_PROGRESS" "韩雪"
transition_bug "$BID9" "RESOLVED" "韩雪"
# B10: 目标 NEW（已是 NEW，无需操作）

echo "  ✅ Bug 状态流转完成"

# -------------------------------------------
# 第四步：创建 10 个测试用例（先创建为 NOT_RUN，后续执行）
# -------------------------------------------
echo ""
echo "[4/7] 创建 10 个测试用例..."

create_tc() {
  curl -s -X POST "$BASE_URL/api/testcases" \
    -H "Content-Type: application/json" \
    -d "{\"projectId\":$1,\"title\":\"$2\",\"module\":\"$3\",\"priority\":\"$4\",\"precondition\":\"$5\",\"steps\":\"$6\",\"expectedResult\":\"$7\",\"designer\":\"$8\"}"
}

TC1=$(create_tc "$ID1" "验证支付宝支付成功后订单状态更新" "支付网关" "P0" "用户已登录且订单已创建" "1.选择支付宝支付 2.完成支付 3.查看订单状态" "订单状态变为已支付" "张伟")
TC2=$(create_tc "$ID2" "验证客户信息批量导入功能" "客户管理" "P1" "准备标准CSV模板文件" "1.进入客户导入页面 2.上传CSV文件 3.确认导入" "所有客户数据正确导入且无乱码" "王芳")
TC3=$(create_tc "$ID3" "验证购物车金额计算准确性" "购物车" "P0" "购物车中有多件不同价格商品" "1.添加3件商品到购物车 2.修改数量 3.查看总金额" "总金额等于单价乘数量之和精确到分" "刘洋")
TC4=$(create_tc "$ID4" "验证多级审批流程正常流转" "审批流程" "P0" "已配置三级审批流程" "1.提交请假申请 2.一级审批通过 3.二级审批通过 4.三级审批通过" "流程正常结束申请人收到通知" "孙丽")
TC5=$(create_tc "$ID5" "验证大数据量报表导出性能" "数据报表" "P1" "数据库中有100万条记录" "1.选择日报导出 2.选择日期范围 3.点击导出" "报表在60秒内生成并下载完成" "吴磊")
TC6=$(create_tc "$ID6" "验证扫码入库重复条码拦截" "入库管理" "P1" "仓库中已有条码A001的商品" "1.扫描条码A001 2.输入入库数量 3.确认入库" "系统提示条码已存在拒绝重复入库" "马超")
TC7=$(create_tc "$ID7" "验证薪资计算含社保公积金扣除" "薪酬模块" "P0" "员工薪资与社保基数已配置" "1.运行月度薪资计算 2.查看薪资明细" "应发减社保减公积金减个税等于实发计算准确" "林婷")
TC8=$(create_tc "$ID8" "验证直播课程在不同浏览器兼容性" "直播模块" "P2" "直播课程已创建且未开始" "1.分别用Chrome和Firefox和Safari打开 2.进入直播间 3.播放直播" "三种浏览器均可正常播放音视频" "杨帆")
TC9=$(create_tc "$ID9" "验证动态评论实时计数准确性" "社区动态" "P2" "帖子已有5条评论" "1.新增一条评论 2.查看评论数 3.删除一条评论 4.再查看评论数" "评论数实时增减与数据库一致" "韩雪")
TC10=$(create_tc "$ID10" "验证挂号成功后短信通知及时性" "挂号服务" "P1" "用户已完成挂号并绑定手机号" "1.完成挂号操作 2.等待短信通知" "30秒内收到挂号成功确认短信" "谢楠")

TCID1=$(echo "$TC1" | jq -r '.id')
TCID2=$(echo "$TC2" | jq -r '.id')
TCID3=$(echo "$TC3" | jq -r '.id')
TCID4=$(echo "$TC4" | jq -r '.id')
TCID5=$(echo "$TC5" | jq -r '.id')
TCID6=$(echo "$TC6" | jq -r '.id')
TCID7=$(echo "$TC7" | jq -r '.id')
TCID8=$(echo "$TC8" | jq -r '.id')
TCID9=$(echo "$TC9" | jq -r '.id')
TCID10=$(echo "$TC10" | jq -r '.id')

echo "  测试用例ID: $TCID1, $TCID2, $TCID3, $TCID4, $TCID5, $TCID6, $TCID7, $TCID8, $TCID9, $TCID10"

# -------------------------------------------
# 第五步：执行测试用例，设置目标状态
# -------------------------------------------
echo ""
echo "[5/7] 设置测试用例执行状态..."

execute_tc() {
  curl -s -X PUT "$BASE_URL/api/testcases/$1/execute" \
    -H "Content-Type: application/json" \
    -d "{\"status\":\"$2\",\"actualResult\":\"$3\",\"executor\":\"$4\"}" > /dev/null
}

# TC1: PASS
execute_tc "$TCID1" "PASS" "符合预期，支付回调正常" "张伟"
# TC2: PASS
execute_tc "$TCID2" "PASS" "导入成功，数据完整" "王芳"
# TC3: PASS
execute_tc "$TCID3" "PASS" "金额计算正确，精确到分" "刘洋"
# TC4: FAIL
execute_tc "$TCID4" "FAIL" "三级审批通过后页面白屏" "孙丽"
# TC5: NOT_RUN（不执行）
# TC6: PASS
execute_tc "$TCID6" "PASS" "重复条码正确拦截" "马超"
# TC7: PASS
execute_tc "$TCID7" "PASS" "薪资计算准确无误" "林婷"
# TC8: BLOCKED
execute_tc "$TCID8" "BLOCKED" "Safari环境暂不可用" "杨帆"
# TC9: PASS
execute_tc "$TCID9" "PASS" "评论数实时更新正确" "韩雪"
# TC10: NOT_RUN（不执行）

echo "  ✅ 测试用例状态设置完成"

# -------------------------------------------
# 第六步：创建临时文件并上传 10 个文档
# -------------------------------------------
echo ""
echo "[6/7] 创建临时文件并上传 10 个文档..."

for i in $(seq 1 10); do
  echo "这是第${i}号测试文档的内容，用于BugClose系统文档管理模块测试。" > /tmp/test-doc-${i}.txt
done

create_doc() {
  curl -s -X POST "$BASE_URL/api/docs" \
    -F "file=@${6}" \
    -F "title=${1}" \
    -F "category=${2}" \
    -F "projectId=${3}" \
    -F "description=${4}" \
    -F "uploader=${5}"
}

D1=$(create_doc "支付中心接口文档v2.0" "DESIGN" "$ID1" "支付网关API接口设计说明文档" "张伟" "/tmp/test-doc-1.txt")
D2=$(create_doc "CRM需求规格说明书" "REQUIREMENT" "$ID2" "客户关系管理系统完整需求文档" "王芳" "/tmp/test-doc-2.txt")
D3=$(create_doc "电商平台测试报告" "TEST" "$ID3" "V3.0版本系统测试报告" "刘洋" "/tmp/test-doc-3.txt")
D4=$(create_doc "OA系统用户操作手册" "MANUAL" "$ID4" "办公自动化系统使用指南" "孙丽" "/tmp/test-doc-4.txt")
D5=$(create_doc "数据中台技术方案评审纪要" "MEETING" "$ID5" "2026年7月技术方案评审会议记录" "吴磊" "/tmp/test-doc-5.txt")
D6=$(create_doc "WMS仓储管理规范" "OTHER" "$ID6" "仓库出入库操作规范与管理制度" "马超" "/tmp/test-doc-6.txt")
D7=$(create_doc "HRM薪酬模块设计文档" "DESIGN" "$ID7" "薪酬计算模块详细设计说明" "林婷" "/tmp/test-doc-7.txt")
D8=$(create_doc "在线教育平台需求文档" "REQUIREMENT" "$ID8" "课程管理与直播功能需求说明" "杨帆" "/tmp/test-doc-8.txt")
D9=$(create_doc "SNS社区运营测试用例集" "TEST" "$ID9" "社交模块全量测试用例" "韩雪" "/tmp/test-doc-9.txt")
D10=$(create_doc "医院挂号系统操作手册" "MANUAL" "$ID10" "挂号系统与就诊流程操作指南" "谢楠" "/tmp/test-doc-10.txt")

rm -f /tmp/test-doc-*.txt

DID1=$(echo "$D1" | jq -r '.id')
echo "  文档ID: $DID1, $(echo "$D2" | jq -r '.id'), $(echo "$D3" | jq -r '.id'), $(echo "$D4" | jq -r '.id'), $(echo "$D5" | jq -r '.id'), $(echo "$D6" | jq -r '.id'), $(echo "$D7" | jq -r '.id'), $(echo "$D8" | jq -r '.id'), $(echo "$D9" | jq -r '.id'), $(echo "$D10" | jq -r '.id')"

if [ -z "$DID1" ] || [ "$DID1" = "null" ]; then
  echo "  ⚠️  部分文档可能上传失败"
else
  echo "  ✅ 10 个文档上传成功"
fi

# -------------------------------------------
# 第七步：验证数据
# -------------------------------------------
echo ""
echo "[7/7] 验证数据..."

PROJ_COUNT=$(curl -s "$BASE_URL/api/projects" | jq 'length')
BUG_COUNT=$(curl -s "$BASE_URL/api/bugs" | jq 'length')
TC_COUNT=$(curl -s "$BASE_URL/api/testcases" | jq 'length')
DOC_COUNT=$(curl -s "$BASE_URL/api/docs" | jq 'length')

echo ""
echo "=========================================="
echo "  数据验证结果"
echo "=========================================="
echo "  项目:     ${PROJ_COUNT} 条"
echo "  Bug:      ${BUG_COUNT} 条"
echo "  测试用例: ${TC_COUNT} 条"
echo "  文档:     ${DOC_COUNT} 条"
echo "=========================================="

if [ "$PROJ_COUNT" -ge 10 ] && [ "$BUG_COUNT" -ge 10 ] && [ "$TC_COUNT" -ge 10 ] && [ "$DOC_COUNT" -ge 10 ]; then
  echo "  ✅ 测试数据创建完成！"
else
  echo "  ⚠️  数据条数不符合预期，请检查！"
fi
echo "=========================================="
