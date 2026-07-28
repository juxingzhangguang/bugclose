package com.bugclose.bug;

import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;

/**
 * 修复 H2 identity 列默认预分配 32 个 ID、进程重启后跳号的问题：
 * 启动时对 bugs、projects 表关闭 ID 缓存，并把计数器对齐到当前最大 ID + 1，保证 ID 连续递增；
 * 同时为存量 Bug 回填项目内序号 seq（按 id 顺序在各自项目内从 1 编号，幂等）
 */
@Configuration
public class BugIdSequenceConfig {

    @Bean
    CommandLineRunner alignBugIdSequence(JdbcTemplate jdbc) {
        return args -> {
            for (String table : new String[] {"bugs", "projects"}) {
                jdbc.execute("ALTER TABLE " + table + " ALTER COLUMN id SET NO CACHE");
                Long maxId = jdbc.queryForObject("SELECT COALESCE(MAX(id), 0) FROM " + table, Long.class);
                jdbc.execute("ALTER TABLE " + table + " ALTER COLUMN id RESTART WITH " + (maxId + 1));
            }
            jdbc.update("UPDATE bugs b SET seq = ("
                    + "SELECT COUNT(*) FROM bugs b2 "
                    + "WHERE (b2.project_id = b.project_id OR (b2.project_id IS NULL AND b.project_id IS NULL)) "
                    + "AND b2.id <= b.id) "
                    + "WHERE b.seq IS NULL");
            // 存量项目回填默认编号 P+ID（可在编辑项目时修改）
            jdbc.update("UPDATE projects SET code = CONCAT('P', id) WHERE code IS NULL OR code = ''");
        };
    }
}
