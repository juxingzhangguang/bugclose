package com.bugclose.auth;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import jakarta.servlet.http.HttpServletRequest;

import java.util.Map;

/**
 * 认证 REST API：登录、当前用户、登出
 */
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final AuthService authService;
    private final LoginRateLimiter rateLimiter;

    public AuthController(AuthService authService, LoginRateLimiter rateLimiter) {
        this.authService = authService;
        this.rateLimiter = rateLimiter;
    }

    /** 登录（带限流：同一用户名+IP 连续失败 5 次锁定 10 分钟） */
    @PostMapping("/login")
    public AuthService.LoginResult login(@RequestBody LoginRequest req, HttpServletRequest request) {
        String ip = clientIp(request);
        rateLimiter.checkAllowed(req.username(), ip);
        try {
            AuthService.LoginResult result = authService.login(req.username(), req.password());
            rateLimiter.onSuccess(req.username(), ip);
            return result;
        } catch (IllegalArgumentException e) {
            rateLimiter.onFailure(req.username(), ip);
            throw e;
        }
    }

    /** 当前用户修改自己的密码（含首次登录强制改密）；成功后返回新 token */
    @PostMapping("/change-password")
    public Map<String, String> changePassword(@RequestBody ChangePasswordRequest req) {
        String newToken = authService.changePassword(req.oldPassword(), req.newPassword());
        return Map.of("token", newToken);
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

    public record ChangePasswordRequest(String oldPassword, String newPassword) {
    }

    /** 取客户端 IP：优先 X-Forwarded-For 第一个值（反向代理场景），否则用 remoteAddr */
    private static String clientIp(HttpServletRequest request) {
        String forwarded = request.getHeader("X-Forwarded-For");
        if (forwarded != null && !forwarded.isBlank()) {
            return forwarded.split(",")[0].trim();
        }
        return request.getRemoteAddr();
    }
}
