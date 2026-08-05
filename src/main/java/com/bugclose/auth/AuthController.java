package com.bugclose.auth;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import jakarta.servlet.http.HttpServletRequest;

/**
 * 认证 REST API：登录、当前用户、登出
 */
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthService authService;

    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    /** 登录 */
    @PostMapping("/login")
    public AuthService.LoginResult login(@RequestBody LoginRequest req) {
        return authService.login(req.username(), req.password());
    }

    /** 当前登录用户信息（前端启动时校验 token 有效性） */
    @GetMapping("/me")
    public AuthService.LoginResult me() {
        return authService.currentUser();
    }

    /** 登出 */
    @PostMapping("/logout")
    public ResponseEntity<Void> logout(HttpServletRequest request) {
        authService.logout(AccessScope.extractBearer(request));
        return ResponseEntity.noContent().<Void>build();
    }

    public record LoginRequest(String username, String password) {
    }
}
