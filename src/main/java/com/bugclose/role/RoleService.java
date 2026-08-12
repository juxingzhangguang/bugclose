package com.bugclose.role;

import com.bugclose.user.UserRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.Comparator;
import java.util.List;

/**
 * 角色管理业务逻辑：内置角色（ADMIN/USER）不可删除，被用户引用的角色不可删除。
 */
@Service
@Transactional
public class RoleService {

    /** 内置角色编码常量，与 User 模块保持一致 */
    public static final String ROLE_ADMIN = "ADMIN";
    public static final String ROLE_USER = "USER";

    private final RoleRepository roleRepository;
    private final UserRepository userRepository;

    public RoleService(RoleRepository roleRepository, UserRepository userRepository) {
        this.roleRepository = roleRepository;
        this.userRepository = userRepository;
    }

    /** 角色视图 */
    public record RoleView(Long id, String code, String name, String description,
                           boolean builtin, long userCount, LocalDateTime createdAt) {
    }

    @Transactional(readOnly = true)
    public List<RoleView> list() {
        return roleRepository.findAll().stream()
                .sorted(Comparator.comparing(Role::getId))
                .map(r -> new RoleView(r.getId(), r.getCode(), r.getName(), r.getDescription(),
                        r.isBuiltin(), countUsers(r.getCode()), r.getCreatedAt()))
                .toList();
    }

    public RoleView create(String code, String name, String description) {
        if (code == null || code.isBlank()) {
            throw new IllegalArgumentException("角色编码不能为空");
        }
        String normalized = code.trim().toUpperCase();
        if (!normalized.matches("[A-Z][A-Z0-9_]{0,19}")) {
            throw new IllegalArgumentException("角色编码须为 1-20 位大写字母/数字/下划线，且以字母开头");
        }
        if (roleRepository.existsByCode(normalized)) {
            throw new IllegalArgumentException("角色编码已存在: " + normalized);
        }
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("角色名称不能为空");
        }
        Role role = new Role();
        role.setCode(normalized);
        role.setName(name.trim());
        role.setDescription(description == null ? null : description.trim());
        role.setBuiltin(false);
        role.setCreatedAt(LocalDateTime.now());
        role.setUpdatedAt(LocalDateTime.now());
        return toView(roleRepository.save(role), 0L);
    }

    public RoleView update(Long id, String name, String description) {
        Role role = findById(id);
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("角色名称不能为空");
        }
        role.setName(name.trim());
        role.setDescription(description == null ? null : description.trim());
        role.setUpdatedAt(LocalDateTime.now());
        return toView(roleRepository.save(role), countUsers(role.getCode()));
    }

    public void delete(Long id) {
        Role role = findById(id);
        if (role.isBuiltin()) {
            throw new IllegalArgumentException("内置角色不可删除");
        }
        long refs = countUsers(role.getCode());
        if (refs > 0) {
            throw new IllegalArgumentException("该角色已被 " + refs + " 个用户使用，无法删除");
        }
        roleRepository.delete(role);
    }

    private Role findById(Long id) {
        return roleRepository.findById(id)
                .orElseThrow(() -> new RoleNotFoundException(id));
    }

    private long countUsers(String code) {
        return userRepository.countByRoleCode(code);
    }

    private RoleView toView(Role role, long userCount) {
        return new RoleView(role.getId(), role.getCode(), role.getName(), role.getDescription(),
                role.isBuiltin(), userCount, role.getCreatedAt());
    }

    /** 角色不存在异常 */
    public static class RoleNotFoundException extends RuntimeException {
        public RoleNotFoundException(Long id) {
            super("角色不存在: id=" + id);
        }
    }
}
