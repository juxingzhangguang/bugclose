package com.bugclose.auth;

import com.bugclose.user.User;
import com.bugclose.user.UserRepository;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.Set;

/**
 * 认证业务：登录校验、签发 token、查询当前登录用户信息
 */
@Service
public class AuthService {

    private final UserRepository userRepository;
    private final TokenStore tokenStore;
    private final BCryptPasswordEncoder passwordEncoder;

    public AuthService(UserRepository userRepository, TokenStore tokenStore,
                       BCryptPasswordEncoder passwordEncoder) {
        this.userRepository = userRepository;
        this.tokenStore = tokenStore;
        this.passwordEncoder = passwordEncoder;
    }

    @Transactional
    public LoginResult login(String username, String password) {
        User user = userRepository.findByUsername(username)
                .orElseThrow(() -> new IllegalArgumentException("用户名或密码错误"));
        if (!user.isEnabled()) {
            throw new IllegalArgumentException("账号已被禁用，请联系管理员");
        }
        if (!passwordEncoder.matches(password, user.getPassword())) {
            throw new IllegalArgumentException("用户名或密码错误");
        }
        boolean mustChange = user.isMustChangePassword();
        // 口令校验已通过，此时明文等于内置默认口令 ⇒ 库里存的就是默认口令。
        // 登录时即时打标，避免「启动后才把密码改回默认值」漏掉强制改密。
        if (!mustChange && DataSeeder.DEFAULT_ADMIN_PASSWORD.equals(password)) {
            user.setMustChangePassword(true);
            user.setUpdatedAt(java.time.LocalDateTime.now());
            userRepository.save(user);
            mustChange = true;
        }
        String token = tokenStore.issue(user.getId());
        Set<Long> bound = User.ROLE_ADMIN.equals(user.getRole())
                ? Set.of() : userRepository.findBoundProjectIds(user.getId());
        return new LoginResult(token, user.getId(), user.getUsername(),
                user.getDisplayName(), user.getRole(),
                User.ROLE_ADMIN.equals(user.getRole()), bound, mustChange);
    }

    public void logout(String token) {
        tokenStore.revoke(token);
    }

    /** 解析用户快照（含绑定项目 ID），供 AuthFilter 在请求开始时绑定。用户不存在或禁用返回 null。 */
    @Transactional(readOnly = true)
    public AuthContext.CurrentUser loadSnapshot(Long userId) {
        User user = userRepository.findById(userId).orElse(null);
        if (user == null || !user.isEnabled()) {
            return null;
        }
        Set<Long> bound = userRepository.findBoundProjectIds(userId);
        return new AuthContext.CurrentUser(user.getId(), user.getUsername(), user.getDisplayName(),
                user.getRole(), bound);
    }

    @Transactional(readOnly = true)
    public LoginResult currentUser() {
        AuthContext.CurrentUser u = AuthContext.requireLoggedIn();
        User user = userRepository.findById(u.id())
                .orElseThrow(() -> new AccessDeniedException("用户不存在"));
        Set<Long> bound = User.ROLE_ADMIN.equals(user.getRole())
                ? Set.of() : userRepository.findBoundProjectIds(user.getId());
        return new LoginResult(null, user.getId(), user.getUsername(),
                user.getDisplayName(), user.getRole(),
                User.ROLE_ADMIN.equals(user.getRole()), bound, user.isMustChangePassword());
    }

    /**
     * 当前用户修改自己的密码：校验原密码，更新后吊销该用户全部 token（含本次请求的 token）。
     * 同时清除「必须修改密码」标记（首次登录强制改密流程用）。
     * <p>改密后不续签 token，前端必须退出并用新密码重新登录。
     */
    @Transactional
    public void changePassword(String oldPassword, String newPassword) {
        AuthContext.CurrentUser u = AuthContext.requireLoggedIn();
        User user = userRepository.findById(u.id())
                .orElseThrow(() -> new AccessDeniedException("用户不存在"));
        if (!passwordEncoder.matches(oldPassword == null ? "" : oldPassword, user.getPassword())) {
            throw new IllegalArgumentException("原密码错误");
        }
        if (newPassword == null || newPassword.length() < 6) {
            throw new IllegalArgumentException("新密码至少 6 位");
        }
        if (passwordEncoder.matches(newPassword, user.getPassword())) {
            throw new IllegalArgumentException("新密码不能与原密码相同");
        }
        user.setPassword(passwordEncoder.encode(newPassword));
        // 改成的仍是内置默认口令 ⇒ 保持强制改密，下次登录继续要求修改
        user.setMustChangePassword(DataSeeder.DEFAULT_ADMIN_PASSWORD.equals(newPassword));
        user.setUpdatedAt(java.time.LocalDateTime.now());
        userRepository.save(user);
        // 全部旧 token 失效（含可能泄露的与当前会话），要求重新登录
        tokenStore.revokeByUser(user.getId());
    }

    /** 登录/当前用户返回体 */
    public record LoginResult(String token, Long id, String username, String displayName,
                              String role, boolean allProjects, Set<Long> allowedProjectIds,
                              boolean mustChangePassword) {
    }
}
