package com.bugclose.bug;

import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;

/**
 * 启动时对齐各表自增主键：MySQL 的 AUTO_INCREMENT 设置为当前最大 ID + 1，保证 ID 连续递增；
 * 同时为存量 Bug 回填项目内序号 seq（按 id 顺序在各自项目内从 1 编号，幂等）
 */
@Configuration
public class BugIdSequenceConfig {

    @Bean
    CommandLineRunner alignBugIdSequence(JdbcTemplate jdbc) {
        return args -> {
            for (String table : new String[] {"bugs", "projects", "test_cases", "requirements"}) {
                Long maxId = jdbc.queryForObject("SELECT COALESCE(MAX(id), 0) FROM " + table, Long.class);
                jdbc.execute("ALTER TABLE " + table + " AUTO_INCREMENT = " + (maxId + 1));
            }
            // 存量 Bug 回填项目内序号 seq（按 id 顺序在各自项目内从 1 编号，幂等）。
            // MySQL 不允许 UPDATE 目标表出现在 FROM 子查询中（错误 1093），改为派生表自连接计数；
            // 不用 ROW_NUMBER() 窗口函数，兼容 MySQL 5.7。
            jdbc.update("UPDATE bugs b JOIN ("
                    + "SELECT b1.id AS id, COUNT(b2.id) AS rn FROM bugs b1 "
                    + "LEFT JOIN bugs b2 ON (b2.project_id = b1.project_id "
                    + "OR (b2.project_id IS NULL AND b1.project_id IS NULL)) AND b2.id <= b1.id "
                    + "GROUP BY b1.id"
                    + ") t ON b.id = t.id "
                    + "SET b.seq = t.rn WHERE b.seq IS NULL");
            // 存量项目回填默认编号 P+ID（可在编辑项目时修改）
            jdbc.update("UPDATE projects SET code = CONCAT('P', id) WHERE code IS NULL OR code = ''");
        };
    }
}
