package com.bugclose.auth;

import com.bugclose.user.User;
import com.bugclose.user.UserRepository;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.HttpStatus;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;

/**
 * 认证过滤器：作用于 /api/** 和 /uploads/**（注册时限定 URL 模式）。
 * 跳过 /api/auth/login；其余请求读 Bearer token，解析当前用户并绑定到 AuthContext。
 * 无 token 或失效 → 401，不进入下游。
 * <p>特殊：/uploads/** 由 &lt;img&gt; 标签加载，无法携带 Authorization 头，
 * 允许通过 ?token= 查询参数传递（仅限该路径，避免 API 把 token 写进 URL 日志）。
 * <p>不标 @Component，避免被 Spring Boot 自动注册两次；统一由 AuthConfig 的 FilterRegistrationBean 注册。
 * 用户与绑定项目的解析交给 AuthService（@Transactional），避免本类自调用事务失效。
 */
public class AuthFilter extends OncePerRequestFilter {

    private static final String LOGIN_PATH = "/api/auth/login";
    private static final String UPLOADS_PREFIX = "/uploads/";

    private final TokenStore tokenStore;
    private final AuthService authService;

    public AuthFilter(TokenStore tokenStore, AuthService authService) {
        this.tokenStore = tokenStore;
        this.authService = authService;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                                     FilterChain chain) throws ServletException, IOException {
        String path = request.getRequestURI();
        if (LOGIN_PATH.equals(path)) {
            chain.doFilter(request, response);
            return;
        }

        String token = AccessScope.extractBearer(request);
        if ((token == null || token.isBlank()) && path.startsWith(UPLOADS_PREFIX)) {
            // <img src> 场景：从查询参数取 token
            token = request.getParameter("token");
        }
        Long userId = tokenStore.resolve(token);
        if (userId == null) {
            writeUnauthorized(response);
            return;
        }

        AuthContext.CurrentUser snapshot = authService.loadSnapshot(userId);
        if (snapshot == null) {
            writeUnauthorized(response);
            return;
        }

        AuthContext.set(snapshot);
        try {
            chain.doFilter(request, response);
        } finally {
            AuthContext.clear();
        }
    }

    private void writeUnauthorized(HttpServletResponse response) throws IOException {
        response.setStatus(HttpStatus.UNAUTHORIZED.value());
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write("{\"error\":\"未登录或登录已过期\"}");
    }
}
