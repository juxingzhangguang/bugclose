package com.bugclose.user;

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
import java.util.Set;

/**
 * 用户管理 REST API（管理员专用）
 */
@RestController
@RequestMapping("/api/users")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    /** 用户列表（管理员看全部；普通用户看共用项目的协作成员） */
    @GetMapping
    public List<UserService.UserView> list() {
        AuthContext.requireLoggedIn();
        return userService.list();
    }

    /** 用户详情 */
    @GetMapping("/{id}")
    public UserService.UserView detail(@PathVariable Long id) {
        AuthContext.requireLoggedIn();
        return userService.detail(id);
    }

    /** 新增（管理员专用） */
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public UserService.UserView create(@RequestBody CreateUserRequest req) {
        AuthContext.requireAdmin();
        User draft = new User();
        draft.setUsername(req.username());
        draft.setDisplayName(req.displayName());
        draft.setRole(req.role());
        draft.setEnabled(req.enabled() == null || req.enabled());
        return userService.create(draft, req.password(), req.projectIds());
    }

    /** 编辑（管理员专用） */
    @PutMapping("/{id}")
    public UserService.UserView update(@PathVariable Long id, @RequestBody UpdateUserRequest req) {
        AuthContext.requireAdmin();
        User draft = new User();
        draft.setUsername(req.username());
        draft.setDisplayName(req.displayName());
        draft.setRole(req.role());
        draft.setEnabled(req.enabled() == null || req.enabled());
        return userService.update(id, draft, req.password(), req.projectIds());
    }

    /** 删除（管理员专用） */
    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable Long id) {
        AuthContext.requireAdmin();
        userService.delete(id);
        return ResponseEntity.noContent().build();
    }

    public record CreateUserRequest(String username, String password, String displayName,
                                    String role, Boolean enabled, Set<Long> projectIds) {
    }

    public record UpdateUserRequest(String username, String password, String displayName,
                                    String role, Boolean enabled, Set<Long> projectIds) {
    }

    @ExceptionHandler(UserService.UserNotFoundException.class)
    public ResponseEntity<Map<String, String>> handleNotFound(UserService.UserNotFoundException e) {
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body(Map.of("error", e.getMessage()));
    }
}
