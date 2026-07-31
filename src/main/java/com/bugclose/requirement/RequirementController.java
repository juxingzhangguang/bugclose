package com.bugclose.requirement;

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
 * 需求 REST API
 */
@RestController
@RequestMapping("/api/requirements")
public class RequirementController {

    private final RequirementService requirementService;

    public RequirementController(RequirementService requirementService) {
        this.requirementService = requirementService;
    }

    /** 列表查询（支持项目、状态、优先级、所属期筛选与关键字搜索） */
    @GetMapping
    public List<Requirement> list(@RequestParam(required = false) Long projectId,
                                   @RequestParam(required = false) Requirement.ReqStatus status,
                                   @RequestParam(required = false) Requirement.ReqPriority priority,
                                   @RequestParam(required = false) String period,
                                   @RequestParam(required = false) String keyword) {
        return requirementService.search(projectId, status, priority, period, keyword);
    }

    /** 详情 */
    @GetMapping("/{id}")
    public Requirement detail(@PathVariable Long id) {
        return requirementService.findById(id);
    }

    /** 新增 */
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Requirement create(@RequestBody Requirement requirement) {
        return requirementService.create(requirement);
    }

    /** 编辑 */
    @PutMapping("/{id}")
    public Requirement update(@PathVariable Long id, @RequestBody Requirement requirement) {
        return requirementService.update(id, requirement);
    }

    /** 删除 */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        requirementService.delete(id);
        return ResponseEntity.noContent().build();
    }

    @ExceptionHandler(RequirementService.RequirementNotFoundException.class)
    public ResponseEntity<Map<String, String>> handleNotFound(RequirementService.RequirementNotFoundException e) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", e.getMessage()));
    }

    @ExceptionHandler(IllegalArgumentException.class)
    public ResponseEntity<Map<String, String>> handleBadRequest(IllegalArgumentException e) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Map.of("error", e.getMessage()));
    }
}
