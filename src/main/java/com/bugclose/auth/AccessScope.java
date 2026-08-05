package com.bugclose.auth;

import com.bugclose.user.User;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.stereotype.Component;

import java.util.Set;

/**
 * 数据隔离助手：从 AuthContext 取当前用户，判断可见项目范围、校验越权访问。
 * <ul>
 *   <li>管理员：isAllAccess=true，所有项目可见，未关联项目的数据也可见</li>
 *   <li>普通用户：只能访问绑定项目内的数据；projectId 为空的资源不可见、不可创建</li>
 * </ul>
 */
@Component
public class AccessScope {

    /** 当前是否全量可见（管理员） */
    public boolean isAllAccess() {
        return AuthContext.requireLoggedIn().isAdmin();
    }

    /** 当前用户可见的项目 ID 集合；管理员返回 null（代表全部） */
    public Set<Long> visibleProjectIds() {
        AuthContext.CurrentUser u = AuthContext.requireLoggedIn();
        return u.isAdmin() ? null : u.boundProjectIds();
    }

    /**
     * 校验当前用户可见该项目。projectId 为空（未关联项目）时仅管理员通过，否则抛 AccessDeniedException；
     * 普通用户的 projectId 不在绑定集合内也抛。
     */
    public void requireVisible(Long projectId) {
        AuthContext.CurrentUser u = AuthContext.requireLoggedIn();
        if (u.isAdmin()) {
            return;
        }
        if (projectId == null) {
            // 未关联项目的数据仅管理员可见；对外统一 403
            throw new AccessDeniedException("无权访问该资源");
        }
        if (!u.boundProjectIds().contains(projectId)) {
            throw new AccessDeniedException("无权访问该资源");
        }
    }

    /**
     * 创建/更新时校验目标项目可见。普通用户 projectId 为空 → 拒绝（需选项目）。
     * 与 {@link #requireVisible} 的区别：这里对空 projectId 抛 400 而非 403。
     */
    public void requireProjectOnWrite(Long projectId) {
        AuthContext.CurrentUser u = AuthContext.requireLoggedIn();
        if (u.isAdmin()) {
            return;
        }
        if (projectId == null) {
            throw new IllegalArgumentException("请选择所属项目");
        }
        if (!u.boundProjectIds().contains(projectId)) {
            throw new AccessDeniedException("无权操作该项目的数据");
        }
    }

    /** 取请求头中的 Bearer token，方便 AuthFilter 使用 */
    public static String extractBearer(HttpServletRequest request) {
        String header = request.getHeader("Authorization");
        if (header != null && header.startsWith("Bearer ")) {
            return header.substring(7).trim();
        }
        return null;
    }
}
