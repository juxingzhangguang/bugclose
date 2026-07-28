package com.bugclose.bug;

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
 * Bug REST API
 */
@RestController
@RequestMapping("/api/bugs")
public class BugController {

    private final BugService bugService;

    public BugController(BugService bugService) {
        this.bugService = bugService;
    }

    /** 列表查询（支持筛选与关键字搜索） */
    @GetMapping
    public List<Bug> list(@RequestParam(required = false) Bug.BugStatus status,
                          @RequestParam(required = false) Bug.Severity severity,
                          @RequestParam(required = false) Bug.Priority priority,
                          @RequestParam(required = false) String assignee,
                          @RequestParam(required = false) String keyword) {
        return bugService.search(status, severity, priority, assignee, keyword);
    }

    /** 详情 */
    @GetMapping("/{id}")
    public Bug detail(@PathVariable Long id) {
        return bugService.findById(id);
    }

    /** 新增 */
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Bug create(@RequestBody Bug bug) {
        return bugService.create(bug);
    }

    /** 编辑 */
    @PutMapping("/{id}")
    public Bug update(@PathVariable Long id, @RequestBody Bug bug) {
        return bugService.update(id, bug);
    }

    /** 状态流转（可同时指派处理人） */
    @PutMapping("/{id}/status")
    public Bug transition(@PathVariable Long id, @RequestBody TransitionRequest request) {
        return bugService.transition(id, request.status(), request.assignee());
    }

    /** 删除 */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        bugService.delete(id);
        return ResponseEntity.noContent().build();
    }

    /** 统计看板数据 */
    @GetMapping("/statistics")
    public Map<String, Object> statistics() {
        return bugService.statistics();
    }

    /** 状态流转请求体 */
    public record TransitionRequest(Bug.BugStatus status, String assignee) {
    }

    @ExceptionHandler(BugService.BugNotFoundException.class)
    public ResponseEntity<Map<String, String>> handleNotFound(BugService.BugNotFoundException e) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", e.getMessage()));
    }

    @ExceptionHandler(IllegalStateException.class)
    public ResponseEntity<Map<String, String>> handleIllegalState(IllegalStateException e) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Map.of("error", e.getMessage()));
    }
}
