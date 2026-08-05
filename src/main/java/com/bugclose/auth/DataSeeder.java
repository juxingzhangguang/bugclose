package com.bugclose.auth;

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
 * 启动时种入默认管理员 admin / admin123（仅当 users 表为空），方便首次登录配置系统。
 */
@Configuration
public class DataSeeder {

    private static final Logger log = LoggerFactory.getLogger(DataSeeder.class);

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
            admin.setRole(User.Role.ADMIN);
            admin.setEnabled(true);
            admin.setCreatedAt(LocalDateTime.now());
            admin.setUpdatedAt(LocalDateTime.now());
            userRepository.save(admin);
            log.warn("已种入默认管理员：账号 admin / 密码 admin123，请尽快修改密码");
        };
    }
}
