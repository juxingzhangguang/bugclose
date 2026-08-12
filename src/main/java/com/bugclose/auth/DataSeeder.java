package com.bugclose.auth;

import com.bugclose.role.Role;
import com.bugclose.role.RoleRepository;
import com.bugclose.user.User;
import com.bugclose.user.UserRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

import java.time.LocalDateTime;

/**
 * 启动时种入默认数据（幂等）：
 * 1. roles 表为空时种入内置角色 ADMIN/USER；
 * 2. users 表为空时种入默认管理员 admin / admin123，方便首次登录配置系统。
 */
@Configuration
public class DataSeeder {

    private static final Logger log = LoggerFactory.getLogger(DataSeeder.class);

    @Bean
    CommandLineRunner seedDefaultRoles(RoleRepository roleRepository) {
        return args -> {
            if (roleRepository.count() > 0) {
                return;
            }
            LocalDateTime now = LocalDateTime.now();
            Role admin = new Role();
            admin.setCode(User.ROLE_ADMIN);
            admin.setName("管理员");
            admin.setDescription("系统内置角色：拥有全部权限");
            admin.setBuiltin(true);
            admin.setCreatedAt(now);
            admin.setUpdatedAt(now);
            roleRepository.save(admin);

            Role user = new Role();
            user.setCode(User.ROLE_USER);
            user.setName("普通用户");
            user.setDescription("系统内置角色：仅可访问绑定项目的数据");
            user.setBuiltin(true);
            user.setCreatedAt(now);
            user.setUpdatedAt(now);
            roleRepository.save(user);
            log.warn("已种入内置角色：ADMIN / USER");
        };
    }

    @Bean
    CommandLineRunner seedDefaultAdmin(UserRepository userRepository,
                                       BCryptPasswordEncoder encoder) {
        return args -> {
            if (userRepository.count() > 0) {
                return;
            }
            User admin = new User();
            admin.setUsername("admin");
            admin.setPassword(encoder.encode("admin123"));
            admin.setDisplayName("管理员");
            admin.setRole(User.ROLE_ADMIN);
            admin.setEnabled(true);
            admin.setCreatedAt(LocalDateTime.now());
            admin.setUpdatedAt(LocalDateTime.now());
            userRepository.save(admin);
            log.warn("已种入默认管理员：账号 admin / 密码 admin123，请尽快修改密码");
        };
    }
}
