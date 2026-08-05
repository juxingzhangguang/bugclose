package com.bugclose.auth;

/**
 * 访问被拒绝（越权访问不可见项目的数据），统一映射为 403
 */
public class AccessDeniedException extends RuntimeException {
    public AccessDeniedException(String message) {
        super(message);
    }
}
