package com.bugclose.auth;

import com.bugclose.user.User;

import java.util.Set;

/**
 * 当前登录用户的请求级快照。AuthFilter 在请求开始时绑定，结束时清理。
 * 不直接持有 User 实体（projects 是懒加载集合，open-in-view=false 下请求中访问会抛 LIE），
 * 而是持有解析好的角色与可见项目 ID 集合。
 */
public final class AuthContext {

    /** 当前用户快照：role=ADMIN 时 boundProjectIds 忽略（代表全部可见） */
    public record CurrentUser(Long id, String username, String displayName,
                              User.Role role, Set<Long> boundProjectIds) {
        public boolean isAdmin() {
            return role == User.Role.ADMIN;
        }
    }

    private static final ThreadLocal<CurrentUser> CURRENT = new ThreadLocal<>();

    private AuthContext() {
    }

    public static void set(CurrentUser user) {
        CURRENT.set(user);
    }

    public static void clear() {
        CURRENT.remove();
    }

    public static CurrentUser getCurrent() {
        return CURRENT.get();
    }

    public static Long getCurrentUserId() {
        CurrentUser u = CURRENT.get();
        return u == null ? null : u.id();
    }

    public static CurrentUser requireLoggedIn() {
        CurrentUser u = CURRENT.get();
        if (u == null) {
            throw new AccessDeniedException("未登录");
        }
        return u;
    }

    public static CurrentUser requireAdmin() {
        CurrentUser u = requireLoggedIn();
        if (!u.isAdmin()) {
            throw new AccessDeniedException("需要管理员权限");
        }
        return u;
    }
}
