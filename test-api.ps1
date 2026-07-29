# BugClose API 冒烟测试脚本（执行后可删除）
$base = "http://localhost:8080"
$results = @()
$tmp = $env:TEMP

function Check($name, $expected, $actual, $note = "") {
  $ok = "$actual" -eq "$expected"
  $script:results += [pscustomobject]@{
    Result = if ($ok) { "PASS" } else { "FAIL" }
    Case = $name; Expected = $expected; Actual = $actual; Note = $note
  }
}

function Code($method, $url, $jsonFile = $null) {
  if ($jsonFile) {
    return curl.exe -s -o "$tmp\bc-resp.json" -w "%{http_code}" -X $method "$url" -H "Content-Type: application/json" --data "@$jsonFile"
  }
  return curl.exe -s -o "$tmp\bc-resp.json" -w "%{http_code}" -X $method "$url"
}
function Resp() { Get-Content "$tmp\bc-resp.json" -Raw }

# ============ 1. Bug 接口 ============
Check "GET /api/bugs 列表" 200 (Code GET "$base/api/bugs")

'{"title":"api-test-bug","projectId":1,"severity":"LOW","priority":"LOW","environment":"test-env","module":"login","reporter":"tester"}' | Out-File -Encoding utf8 "$tmp\bc-bug.json"
$c = Code POST "$base/api/bugs" "$tmp\bc-bug.json"
$bugJson = Resp
$bugId = if ($bugJson -match '"id":(\d+)') { $Matches[1] } else { 0 }
$seqOk = $bugJson -match '"seq":(\d+)'
Check "POST /api/bugs 创建" 201 $c "id=$bugId seq=$(if($seqOk){$Matches[1]})"
Check "创建返回含environment字段" True ($bugJson -match '"environment":"test-env"')
Check "创建返回含module字段" True ($bugJson -match '"module":"login"')

'{"title":"no-env","projectId":1,"module":"login"}' | Out-File -Encoding utf8 "$tmp\bc-noenv.json"
Check "POST 缺影响环境被拒绝" 400 (Code POST "$base/api/bugs" "$tmp\bc-noenv.json")
'{"title":"no-module","projectId":1,"environment":"test-env"}' | Out-File -Encoding utf8 "$tmp\bc-nomod.json"
Check "POST 缺影响模块被拒绝" 400 (Code POST "$base/api/bugs" "$tmp\bc-nomod.json")

Check "GET /api/bugs/{id} 详情" 200 (Code GET "$base/api/bugs/$bugId")

'{"title":"api-test-bug-upd","projectId":1,"severity":"HIGH","priority":"HIGH","environment":"prod-env","module":"pay","reporter":"tester"}' | Out-File -Encoding utf8 "$tmp\bc-bug2.json"
Check "PUT /api/bugs/{id} 更新" 200 (Code PUT "$base/api/bugs/$bugId" "$tmp\bc-bug2.json")

'{"status":"IN_PROGRESS","assignee":"dev1"}' | Out-File -Encoding utf8 "$tmp\bc-st1.json"
Check "PUT status 合法流转 NEW->IN_PROGRESS" 200 (Code PUT "$base/api/bugs/$bugId/status" "$tmp\bc-st1.json")

'{"status":"CLOSED"}' | Out-File -Encoding utf8 "$tmp\bc-st2.json"
'{"status":"NEW"}' | Out-File -Encoding utf8 "$tmp\bc-st3.json"
Check "PUT status 非法流转 IN_PROGRESS->NEW" 400 (Code PUT "$base/api/bugs/$bugId/status" "$tmp\bc-st3.json")

Check "GET 不存在的Bug" 404 (Code GET "$base/api/bugs/99999")
Check "GET /api/bugs?status=IN_PROGRESS 筛选" 200 (Code GET "$base/api/bugs?status=IN_PROGRESS&keyword=api-test")
Check "GET /api/bugs/statistics 统计" 200 (Code GET "$base/api/bugs/statistics")

# ============ 2. 项目接口 ============
Check "GET /api/projects 列表" 200 (Code GET "$base/api/projects")

'{"name":"api-test-proj","code":"apitest","description":"tmp"}' | Out-File -Encoding utf8 "$tmp\bc-proj.json"
$c = Code POST "$base/api/projects" "$tmp\bc-proj.json"
$projJson = Resp
$projId = if ($projJson -match '"id":(\d+)') { $Matches[1] } else { 0 }
Check "POST /api/projects 创建" 201 $c "id=$projId"
Check "编号自动转大写" True ($projJson -match '"code":"APITEST"')

'{"name":"api-test-proj2","code":"APITEST"}' | Out-File -Encoding utf8 "$tmp\bc-proj2.json"
Check "POST 重复编号被拒绝" 400 (Code POST "$base/api/projects" "$tmp\bc-proj2.json")

'{"name":"api-test-proj-upd","code":"APITEST","description":"upd"}' | Out-File -Encoding utf8 "$tmp\bc-proj3.json"
Check "PUT /api/projects/{id} 更新" 200 (Code PUT "$base/api/projects/$projId" "$tmp\bc-proj3.json")
Check "DELETE 有Bug的项目被拒绝" 400 (Code DELETE "$base/api/projects/1")

# ============ 3. 图片上传接口 ============
"fake-image-bytes" | Out-File -Encoding ascii "$tmp\bc-img.png"
$c = curl.exe -s -o "$tmp\bc-resp.json" -w "%{http_code}" -X POST "$base/api/uploads" -F "file=@$tmp\bc-img.png;type=image/png"
Check "POST /api/uploads 图片上传" 200 $c (Resp)

# ============ 4. 文档接口 ============
Check "GET /api/docs 列表" 200 (Code GET "$base/api/docs")

"doc content v1" | Out-File -Encoding ascii "$tmp\bc-doc.txt"
$c = curl.exe -s -o "$tmp\bc-resp.json" -w "%{http_code}" -X POST "$base/api/docs" -F "file=@$tmp\bc-doc.txt" -F "title=api-test-doc" -F "projectId=$projId" -F "uploader=tester"
$docJson = Resp
$docId = if ($docJson -match '"id":(\d+)') { $Matches[1] } else { 0 }
Check "POST /api/docs 上传文档" 201 $c "id=$docId"

"doc content v2" | Out-File -Encoding ascii "$tmp\bc-doc2.txt"
$c = curl.exe -s -o "$tmp\bc-resp.json" -w "%{http_code}" -X POST "$base/api/docs/$docId/versions" -F "file=@$tmp\bc-doc2.txt" -F "remark=v2" -F "uploader=tester"
Check "POST 上传新版本" 201 $c

$c = Code GET "$base/api/docs/$docId/versions"
$verJson = Resp
$verCount = ([regex]::Matches($verJson, '"versionNo"')).Count
$verId = if ($verJson -match '"id":(\d+)') { $Matches[1] } else { 0 }
Check "GET 版本历史(应2个版本)" 2 $verCount "http=$c"
Check "GET 下载指定版本" 200 (Code GET "$base/api/docs/$docId/versions/$verId/download")

'{"title":"api-test-doc-upd","description":"upd"}' | Out-File -Encoding utf8 "$tmp\bc-doc3.json"
Check "PUT /api/docs/{id} 编辑元信息" 200 (Code PUT "$base/api/docs/$docId" "$tmp\bc-doc3.json")
Check "GET 不存在文档的版本" 404 (Code GET "$base/api/docs/99999/versions")

# ============ 5. 清理测试数据 ============
Check "DELETE /api/docs/{id}" 204 (Code DELETE "$base/api/docs/$docId")
Check "DELETE /api/bugs/{id}" 204 (Code DELETE "$base/api/bugs/$bugId")
Check "DELETE /api/projects/{id}" 204 (Code DELETE "$base/api/projects/$projId")

# ============ 输出结果 ============
$results | Format-Table -AutoSize
$pass = ($results | Where-Object Result -eq "PASS").Count
$fail = ($results | Where-Object Result -eq "FAIL").Count
"总计: $($results.Count) | 通过: $pass | 失败: $fail"
Remove-Item "$tmp\bc-*.json", "$tmp\bc-*.txt", "$tmp\bc-img.png" -ErrorAction SilentlyContinue
