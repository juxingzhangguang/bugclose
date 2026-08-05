package com.bugclose.auth;

import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

/**
 * 认证配置：BCrypt 编码器 Bean、AuthFilter 注册（仅作用于 /api/**）。
 * 静态资源、/h2-console、/uploads/** 不经过 filter，行为保持不变。
 */
@Configuration
public class AuthConfig {

    @Bean
    public BCryptPasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    public AuthFilter authFilter(TokenStore tokenStore, AuthService authService) {
        return new AuthFilter(tokenStore, authService);
    }

    @Bean
    public FilterRegistrationBean<AuthFilter> authFilterRegistration(AuthFilter authFilter) {
        FilterRegistrationBean<AuthFilter> reg = new FilterRegistrationBean<>(authFilter);
        reg.addUrlPatterns("/api/*");
        reg.setOrder(1);
        return reg;
    }
}
