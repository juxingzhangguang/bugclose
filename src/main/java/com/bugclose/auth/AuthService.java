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

    @Transactional(readOnly = true)
    public LoginResult login(String username, String password) {
        User user = userRepository.findByUsername(username)
                .orElseThrow(() -> new IllegalArgumentException("用户名或密码错误"));
        if (!user.isEnabled()) {
            throw new IllegalArgumentException("账号已被禁用，请联系管理员");
        }
        if (!passwordEncoder.matches(password, user.getPassword())) {
            throw new IllegalArgumentException("用户名或密码错误");
        }
        String token = tokenStore.issue(user.getId());
        Set<Long> bound = user.getRole() == User.Role.ADMIN
                ? Set.of() : userRepository.findBoundProjectIds(user.getId());
        return new LoginResult(token, user.getId(), user.getUsername(),
                user.getDisplayName(), user.getRole(),
                user.getRole() == User.Role.ADMIN, bound);
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
        Set<Long> bound = user.getRole() == User.Role.ADMIN
                ? Set.of() : userRepository.findBoundProjectIds(user.getId());
        return new LoginResult(null, user.getId(), user.getUsername(),
                user.getDisplayName(), user.getRole(),
                user.getRole() == User.Role.ADMIN, bound);
    }

    /** 登录/当前用户返回体 */
    public record LoginResult(String token, Long id, String username, String displayName,
                              User.Role role, boolean allProjects, Set<Long> allowedProjectIds) {
    }
}
