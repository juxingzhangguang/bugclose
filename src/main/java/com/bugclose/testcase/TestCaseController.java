package com.bugclose.testcase;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * 测试用例 REST API
 */
@RestController
@RequestMapping("/api/testcases")
public class TestCaseController {

    private final TestCaseService testCaseService;

    public TestCaseController(TestCaseService testCaseService) {
        this.testCaseService = testCaseService;
    }

    /** 列表查询（支持项目、执行状态、优先级筛选与关键字搜索） */
    @GetMapping
    public List<TestCase> list(@RequestParam(required = false) Long projectId,
                               @RequestParam(required = false) TestCase.ExecStatus status,
                               @RequestParam(required = false) TestCase.CasePriority priority,
                               @RequestParam(required = false) String keyword) {
        return testCaseService.search(projectId, status, priority, keyword);
    }

    /** 详情 */
    @GetMapping("/{id}")
    public TestCase detail(@PathVariable Long id) {
        return testCaseService.findById(id);
    }

    /** 新增 */
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public TestCase create(@RequestBody TestCase testCase) {
        return testCaseService.create(testCase);
    }

    /** 批量导入（CSV 解析在前端完成，这里接收 JSON 数组） */
    @PostMapping("/import")
    public Map<String, Object> importBatch(@RequestBody List<TestCase> testCases) {
        return testCaseService.importBatch(testCases);
    }

    /** 编辑 */
    @PutMapping("/{id}")
    public TestCase update(@PathVariable Long id, @RequestBody TestCase testCase) {
        return testCaseService.update(id, testCase);
    }

    /** 记录执行结果 */
    @PutMapping("/{id}/execute")
    public TestCase execute(@PathVariable Long id, @RequestBody ExecuteRequest request) {
        return testCaseService.execute(id, request.status(), request.actualResult(), request.executor());
    }

    /** 删除 */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        testCaseService.delete(id);
        return ResponseEntity.noContent().build();
    }

    /** 执行结果请求体 */
    public record ExecuteRequest(TestCase.ExecStatus status, String actualResult, String executor) {
    }

    @ExceptionHandler(TestCaseService.TestCaseNotFoundException.class)
    public ResponseEntity<Map<String, String>> handleNotFound(TestCaseService.TestCaseNotFoundException e) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", e.getMessage()));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, String>> handleBadRequest(IllegalArgumentException e) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Map.of("error", e.getMessage()));
    }
}
