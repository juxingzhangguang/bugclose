package com.bugclose.role;

import com.bugclose.auth.AuthContext;
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
 * 角色管理 REST API（列表登录即可见；增删改仅管理员）
 */
@RestController
@RequestMapping("/api/roles")
public class RoleController {

    private final RoleService roleService;

    public RoleController(RoleService roleService) {
        this.roleService = roleService;
    }

    /** 角色列表（含每个角色被引用数） */
    @GetMapping
    public List<RoleService.RoleView> list() {
        AuthContext.requireLoggedIn();
        return roleService.list();
    }

    /** 新增角色（管理员专用） */
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public RoleService.RoleView create(@RequestBody RoleRequest req) {
        AuthContext.requireAdmin();
        return roleService.create(req.code(), req.name(), req.description());
    }

    /** 编辑角色名称/描述（管理员专用） */
    @PutMapping("/{id}")
    public RoleService.RoleView update(@PathVariable Long id, @RequestBody RoleRequest req) {
        AuthContext.requireAdmin();
        return roleService.update(id, req.name(), req.description());
    }

    /** 删除角色（管理员专用；内置或已被引用时拒绝） */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        AuthContext.requireAdmin();
        roleService.delete(id);
        return ResponseEntity.noContent().build();
    }

    public record RoleRequest(String code, String name, String description) {
    }

    @ExceptionHandler(RoleService.RoleNotFoundException.class)
    public ResponseEntity<Map<String, String>> handleNotFound(RoleService.RoleNotFoundException e) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", e.getMessage()));
    }
}
