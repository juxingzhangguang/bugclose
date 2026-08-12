package com.bugclose.user;

import com.bugclose.auth.AccessScope;
import com.bugclose.auth.AuthContext;
import com.bugclose.project.Project;
import com.bugclose.project.ProjectRepository;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.HashSet;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 用户管理业务逻辑（管理员专用，权限校验在 controller 层入口完成）。
 */
@Service
@Transactional
public class UserService {

    private final UserRepository userRepository;
    private final ProjectRepository projectRepository;
    private final AccessScope accessScope;
    private final BCryptPasswordEncoder passwordEncoder;

    public UserService(UserRepository userRepository, ProjectRepository projectRepository,
                       AccessScope accessScope, BCryptPasswordEncoder passwordEncoder) {
        this.userRepository = userRepository;
        this.projectRepository = projectRepository;
        this.accessScope = accessScope;
        this.passwordEncoder = passwordEncoder;
    }

    /** 项目引用（绑定列表用） */
    public record ProjectRef(Long id, String name) {
    }

    /** 用户视图：含绑定的项目列表，不含密码 */
    public record UserView(Long id, String username, String displayName,
                           String role, boolean enabled,
                           LocalDateTime createdAt, List<ProjectRef> projects) {
    }

    /**
     * 用户列表（按当前用户权限范围）：
     * 管理员看到全部用户；普通用户只看到与自己共用项目的非管理员协作成员。
     */
    @Transactional(readOnly = true)
    public List<UserView> list() {
        List<User> users;
        if (accessScope.isAllAccess()) {
            users = userRepository.findAll();
        } else {
            Set<Long> visible = accessScope.visibleProjectIds();
            users = visible == null || visible.isEmpty()
                    ? List.of()
                    : userRepository.findCollaborators(User.ROLE_ADMIN, visible);
        }
        return users.stream()
                .sorted((a, b) -> a.getId().compareTo(b.getId()))
                .map(this::toView)
                .toList();
    }

    @Transactional(readOnly = true)
    public UserView detail(Long id) {
        AuthContext.CurrentUser current = AuthContext.requireLoggedIn();
        User user = findById(id);
        // 普通用户只能查看协作成员（非管理员）的详情；管理员不限
        if (!current.isAdmin()) {
            if (User.ROLE_ADMIN.equals(user.getRole())) {
                throw new UserNotFoundException(id);
            }
            Set<Long> mine = accessScope.visibleProjectIds();
            boolean shared = user.getProjects().stream()
                    .anyMatch(p -> mine != null && mine.contains(p.getId()));
            if (!shared) {
                throw new UserNotFoundException(id);
            }
        }
        return toView(user);
    }

    public UserView create(User user, String rawPassword, Set<Long> projectIds) {
        if (user.getUsername() == null || user.getUsername().isBlank()) {
            throw new IllegalArgumentException("用户名不能为空");
        }
        String username = user.getUsername().trim();
        if (userRepository.existsByUsername(username)) {
            throw new IllegalArgumentException("用户名已存在: " + username);
        }
        if (rawPassword == null || rawPassword.length() < 4) {
            throw new IllegalArgumentException("密码不能为空且至少 4 位");
        }
        user.setId(null);
        user.setUsername(username);
        user.setPassword(passwordEncoder.encode(rawPassword));
        if (user.getRole() == null) {
            user.setRole(User.ROLE_USER);
        }
        if (user.getDisplayName() == null || user.getDisplayName().isBlank()) {
            user.setDisplayName(username);
        } else {
            user.setDisplayName(user.getDisplayName().trim());
        }
        user.setEnabled(true);
        user.setCreatedAt(LocalDateTime.now());
        user.setUpdatedAt(LocalDateTime.now());
        user.setProjects(resolveProjects(projectIds));
        return toView(userRepository.save(user));
    }

    public UserView update(Long id, User changes, String rawPassword, Set<Long> projectIds) {
        User user = findById(id);
        if (changes.getUsername() == null || changes.getUsername().isBlank()) {
            throw new IllegalArgumentException("用户名不能为空");
        }
        String username = changes.getUsername().trim();
        if (userRepository.existsByUsernameAndIdNot(username, id)) {
            throw new IllegalArgumentException("用户名已存在: " + username);
        }
        user.setUsername(username);
        if (changes.getDisplayName() == null || changes.getDisplayName().isBlank()) {
            user.setDisplayName(username);
        } else {
            user.setDisplayName(changes.getDisplayName().trim());
        }
        String newRole = changes.getRole() != null ? changes.getRole() : user.getRole();
        boolean newEnabled = changes.isEnabled();
        guardLastAdmin(user, newRole, newEnabled);
        user.setRole(newRole);
        user.setEnabled(newEnabled);
        if (rawPassword != null && !rawPassword.isBlank()) {
            if (rawPassword.length() < 4) {
                throw new IllegalArgumentException("密码至少 4 位");
            }
            user.setPassword(passwordEncoder.encode(rawPassword));
        }
        user.setProjects(resolveProjects(projectIds));
        user.setUpdatedAt(LocalDateTime.now());
        return toView(userRepository.save(user));
    }

    public void delete(Long id) {
        if (id == null) {
            throw new IllegalArgumentException("用户 id 不能为空");
        }
        Long currentId = AuthContext.getCurrentUserId();
        if (id.equals(currentId)) {
            throw new IllegalArgumentException("不能删除当前登录用户");
        }
        User user = findById(id);
        if (User.ROLE_ADMIN.equals(user.getRole()) && user.isEnabled()
                && userRepository.countByRoleAndEnabledTrue(User.ROLE_ADMIN) <= 1) {
            throw new IllegalArgumentException("不能删除最后一个启用的管理员");
        }
        userRepository.delete(user);
    }

    private User findById(Long id) {
        return userRepository.findById(id)
                .orElseThrow(() -> new UserNotFoundException(id));
    }

    /** 解析项目 ID 集合为实体集合（忽略不存在的 id） */
    private Set<Project> resolveProjects(Set<Long> projectIds) {
        if (projectIds == null || projectIds.isEmpty()) {
            return new HashSet<>();
        }
        return new LinkedHashSet<>(projectRepository.findAllById(projectIds));
    }

    /** 保护最后一个启用的管理员不被降级或禁用，避免无人可管 */
    private void guardLastAdmin(User user, String newRole, boolean newEnabled) {
        if (User.ROLE_ADMIN.equals(user.getRole()) && user.isEnabled()
                && (!User.ROLE_ADMIN.equals(newRole) || !newEnabled)
                && userRepository.countByRoleAndEnabledTrue(User.ROLE_ADMIN) <= 1) {
            throw new IllegalArgumentException("不能禁用或降级最后一个启用的管理员");
        }
    }

    private UserView toView(User user) {
        List<ProjectRef> refs = user.getProjects().stream()
                .sorted((a, b) -> a.getId().compareTo(b.getId()))
                .map(p -> new ProjectRef(p.getId(), p.getName()))
                .collect(Collectors.toList());
        return new UserView(user.getId(), user.getUsername(), user.getDisplayName(),
                user.getRole(), user.isEnabled(), user.getCreatedAt(), refs);
    }

    /** 用户不存在异常 */
    public static class UserNotFoundException extends RuntimeException {
        public UserNotFoundException(Long id) {
            super("用户不存在: id=" + id);
        }
    }
}
