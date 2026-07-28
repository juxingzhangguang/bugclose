package com.bugclose.project;

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
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

/**
 * 项目 REST API
 */
@RestController
@RequestMapping("/api/projects")
public class ProjectController {

    private final ProjectService projectService;

    public ProjectController(ProjectService projectService) {
        this.projectService = projectService;
    }

    /** 项目列表（含关联 Bug 数量） */
    @GetMapping
    public List<ProjectService.ProjectView> list() {
        return projectService.listWithBugCount();
    }

    /** 新增 */
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public Project create(@RequestBody Project project) {
        return projectService.create(project);
    }

    /** 编辑 */
    @PutMapping("/{id}")
    public Project update(@PathVariable Long id, @RequestBody Project project) {
        return projectService.update(id, project);
    }

    /** 删除（有关联 Bug 时拒绝） */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        projectService.delete(id);
        return ResponseEntity.noContent().build();
    }

    @ExceptionHandler(ProjectService.ProjectNotFoundException.class)
    public ResponseEntity<Map<String, String>> handleNotFound(ProjectService.ProjectNotFoundException e) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", e.getMessage()));
    }

    @ExceptionHandler(IllegalStateException.class)
    public ResponseEntity<Map<String, String>> handleIllegalState(IllegalStateException e) {
        return ResponseEntity.status(HttpStatus.BAD_REQUEST).body(Map.of("error", e.getMessage()));
    }
}
